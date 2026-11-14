"""Tablematch eval harness.

    python evals/run_evals.py                      # every offline suite, all splits
    python evals/run_evals.py --suite brief rank   # chosen suites
    python evals/run_evals.py --split held_out     # only the held-out cases
    python evals/run_evals.py --live               # also run model suites (needs ANTHROPIC_API_KEY)
    python evals/run_evals.py --compare evals/baseline/summary.json

Writes evals/results/<run id>/{results.jsonl, summary.json, summary.md} and exits 1 when a must-have
threshold in evals/thresholds.json fails, so CI can block the change.
"""
import argparse
import base64
import io
import json
import os
import random
import re
import sys
import tempfile
import time
from datetime import date, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
EVALS = ROOT / "evals"
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(EVALS))

_tmp = tempfile.mkdtemp()
os.environ.setdefault("HL_DB", str(Path(_tmp) / "eval.db"))
os.environ.setdefault("HL_UPLOADS", str(Path(_tmp) / "up"))
os.environ["HL_VERIFY"] = "demo"

from PIL import Image  # noqa: E402

import graders as G  # noqa: E402
import images  # noqa: E402
from app import evidence, matching, verify  # noqa: E402

OFFLINE = ["brief", "rank", "host", "photo", "routing", "routing_props", "privacy"]
LIVE = ["vision", "messages"]


def load(name, split):
    rows = [json.loads(line) for line in open(EVALS / "datasets" / name)]
    return [r for r in rows if split == "all" or r.get("split", "dev") == split]


def app_state():
    """Fresh seeded app, read through the same API the product uses."""
    from fastapi.testclient import TestClient
    from app.main import app
    c = TestClient(app)
    c.__enter__()
    c.post("/api/reset")
    return c, c.get("/api/events").json(), c.get("/api/meta").json()["sponsors"]


def timed(fn, *a, **k):
    t = time.perf_counter()
    out = fn(*a, **k)
    return out, round((time.perf_counter() - t) * 1000, 2)


# ------------------------------------------------------------------ suites
def suite_brief(split, **_):
    rows = []
    for case in load("brief_parsing.jsonl", split):
        out, ms = timed(matching.parse_brief, case["input"])
        score, notes = G.grade_brief(case, out)
        rows.append({"suite": "brief", "id": case["id"], "tags": case["tags"], "split": case["split"],
                     "input": case["input"], "output": out, "score": score, "notes": notes, "ms": ms,
                     "pass": score["exact"]})
    return rows


def suite_rank(split, events, sponsors, **_):
    rows = []
    by_name = {s["name"]: s for s in sponsors}
    for case in load("event_ranking.jsonl", split):
        inp = case["input"]
        sp = by_name[inp["sponsor"]] if inp["sponsor"] else None  # KeyError = dataset bug, fail loudly
        (results, parsed, hidden), ms = timed(matching.rank_events, events, inp["query"], sp, inp["budget"],
                                              inp["slot_type"], inp["filters"])
        for r in results:
            r["_parsed_budget"] = parsed["budget"]
        score, notes = G.grade_event_ranking(case, results, sp)
        rows.append({"suite": "rank", "id": case["id"], "tags": case["tags"], "split": case["split"], "input": inp,
                     "output": {"top": [(r["event"]["title"], r["score"]) for r in results[:5]], "hidden": hidden},
                     "score": score, "notes": notes, "ms": ms,
                     "pass": score["violations"] == 0 and score["hit_at_3"]})
    return rows


def suite_host(split, client, events, sponsors, **_):
    rows = []
    by_title = {e["title"]: e for e in events}
    for case in load("host_ranking.jsonl", split):
        inp = case["input"]
        ev = by_title[inp["event"]]
        assert all(n in {s["name"] for s in sponsors} for n in case["expected"]["relevant"]), case["id"]
        t = time.perf_counter()
        res = client.post("/api/search/sponsors", json={"event_id": ev["id"], "guests": inp["guests"],
                                                         "funding_needed": inp["funding"], "notes": inp["notes"]}).json()
        ms = round((time.perf_counter() - t) * 1000, 2)
        score, notes = G.grade_host_ranking(case, res["results"], res["package"], ev)
        rows.append({"suite": "host", "id": case["id"], "tags": case["tags"], "split": case["split"], "input": inp,
                     "output": {"top": [(r["sponsor"]["name"], r["score"]) for r in res["results"][:5]],
                                "package": res["package"]["items"]},
                     "score": score, "notes": notes, "ms": ms,
                     "pass": score["violations"] == 0 and score["hit_at_3"]})
    return rows


def suite_photo(split, **_):
    rows = []
    for case in load("photo_quality.jsonl", split):
        img, data, mime = images.render(case["input"])
        (checks, ok), ms = timed(verify._quality, [img])
        score, notes = G.grade_photo(case, ok)
        rows.append({"suite": "photo", "id": case["id"], "tags": case["tags"], "split": case["split"],
                     "input": case["input"], "output": {"passed": ok, "sharpness": round(verify.sharpness(img), 1),
                                                        "size": list(img.size)},
                     "score": score, "notes": notes, "ms": ms, "pass": score["correct"]})
    return rows


def _route(factors=None, scenario=None, triggers=None):
    """Runs the real risk() and decide() code on a factor vector."""
    key = scenario
    if scenario is None:
        key = "_eval"
        evidence.SCENARIOS[key] = {"label": "eval", "factors": factors or {}, "triggers": triggers or []}
    try:
        score, band, parts, trig = evidence.risk(key, [{"kind": "photo"}], {"photos_required": 1})
        decision, status, _ = evidence.decide(band, key)
    finally:
        evidence.SCENARIOS.pop("_eval", None)
    return score, band, decision


def suite_routing(split, **_):
    rows = []
    for case in load("risk_routing.jsonl", split):
        inp = case["input"]
        (score_, band, decision), ms = timed(_route, inp.get("factors"), inp.get("scenario"))
        score, notes = G.grade_route(case, band, decision, score_)
        rows.append({"suite": "routing", "id": case["id"], "tags": case["tags"], "split": case["split"], "input": inp,
                     "output": {"score": score_, "band": band, "decision": decision},
                     "score": score, "notes": notes, "ms": ms, "pass": score["correct"]})
    return rows


def suite_routing_props(split, n=2000, **_):
    """Property checks over random factor vectors. These are policy invariants, not sampled labels."""
    rnd = random.Random(20261114)
    keys = list(evidence.RISK_WEIGHTS)
    fails = {"bounded": 0, "monotonic": 0, "trigger_forces_review": 0, "never_rejects": 0,
             "strong_fraud_signal_reviewed": 0}
    examples = {k: [] for k in fails}
    for _ in range(n):
        f = {k: round(rnd.random() ** 2, 2) for k in keys if rnd.random() < 0.6}
        s, b, d = _route(f)
        if not 0 <= s <= 100:
            fails["bounded"] += 1
        k = rnd.choice(keys)
        g = dict(f)
        g[k] = min(1.0, g.get(k, 0) + 0.2)
        s2, _, _ = _route(g)
        if s2 < s:
            fails["monotonic"] += 1
            examples["monotonic"].append(f)
        st, bt, dt = _route(f, triggers=["eval trigger"])
        if bt != "high" or st < 70 or dt != "needs_review":
            fails["trigger_forces_review"] += 1
        if d == "rejected" or dt == "rejected":
            fails["never_rejects"] += 1
        # a single strong fraud signal (duplicate or AI-generated >= 0.8) must never be auto-verified
        if (f.get("duplicate", 0) >= 0.8 or f.get("synthetic", 0) >= 0.8) and d == "verified":
            fails["strong_fraud_signal_reviewed"] += 1
            if len(examples["strong_fraud_signal_reviewed"]) < 3:
                examples["strong_fraud_signal_reviewed"].append({"factors": f, "score": s})
    rows = []
    for name, c in fails.items():
        rows.append({"suite": "routing_props", "id": f"prop-{name}", "tags": ["property"], "split": "all",
                     "input": {"samples": n}, "output": {"violations": c, "examples": examples[name][:3]},
                     "score": {"violation_rate": c / n}, "notes": [] if c == 0 else [f"{c} of {n} samples broke {name}"],
                     "ms": 0, "pass": c == 0})
    return rows


def _gps_image():
    im, _, _ = images.render({"slot": "menu"})
    im = im.convert("RGB")
    ex = im.getexif()
    ex[0x010F] = "Apple"
    gps = ex.get_ifd(0x8825)
    gps.update({1: "N", 2: (40.0, 44.0, 55.0), 3: "W", 4: (73.0, 59.0, 0.0)})
    buf = io.BytesIO()
    im.save(buf, "JPEG", exif=ex, quality=90)
    return buf.getvalue()


def suite_privacy(split, **_):
    """Evidence handling: originals kept intact, shared copies carry no location, faces softened when asked."""
    import hashlib
    from app import db
    rows = []
    data = _gps_image()
    for i, blur in enumerate((True, False), 1):
        recs = evidence.ingest({"id": 9000 + i}, [("dinner.jpg", data, "image/jpeg")], "eval", blur_faces=blur)
        r = recs[0]
        orig = (db.UPLOADS / r["original"].split("/uploads/")[1]).read_bytes()
        shared = Image.open(db.UPLOADS / r["shared"].split("/uploads/")[1])
        gps_left = bool(shared.getexif().get_ifd(0x8825))
        checks = {"original_untouched": hashlib.sha256(orig).hexdigest() == hashlib.sha256(data).hexdigest(),
                  "hash_recorded": r["sha256"] == hashlib.sha256(data).hexdigest(),
                  "shared_has_no_gps": not gps_left,
                  "blur_applied_when_asked": r["blurred"] == blur}
        notes = [f"FAILED {k}" for k, v in checks.items() if not v]
        rows.append({"suite": "privacy", "id": f"privacy-00{i}", "tags": ["blur_on" if blur else "blur_off"],
                     "split": "all", "input": {"blur_faces": blur, "photo_has_gps": True},
                     "output": checks, "score": checks, "notes": notes, "ms": 0, "pass": all(checks.values())})
    return rows


# ------------------------------------------------------------------ model suites (need an API key)
VISION_PROMPT = verify.__doc__  # reference only; the live prompt below mirrors verify._claude


def _vision_call(client, model, data, mime, brand, slot_title, specs):
    content = [{"type": "image", "source": {"type": "base64", "media_type": mime, "data": base64.b64encode(data).decode()}},
               {"type": "text", "text": (
                   f"A supper club host says they displayed the sponsor '{brand}' at a dinner. "
                   f"The purchased placement is '{slot_title}': {specs}\n"
                   "Look at the photos and answer with JSON only, no other text:\n"
                   '{"logo_visible": true|false, "brand_matches": true|false, "placement_matches": true|false, '
                   '"confidence": 0.0-1.0, "notes": "one or two plain sentences"}')}]
    msg = client.messages.create(model=model, max_tokens=400, messages=[{"role": "user", "content": content}])
    text = "".join(b.text for b in msg.content if getattr(b, "type", "") == "text")
    m = re.search(r"\{.*\}", text, re.S)
    raw = json.loads(m.group(0)) if m else None
    return raw, msg.usage.input_tokens, msg.usage.output_tokens


SLOT_TEXT = {"menu": ("Logo on the printed menu", "Brand name printed at the top of each menu card."),
             "display": ("Logo on the screen", "Brand logo shown on the TV screen during the dinner."),
             "table": ("Table card", "A branded card on the table.")}


def suite_vision(split, runs=1, model=None, **_):
    if not os.environ.get("ANTHROPIC_API_KEY"):
        return [{"suite": "vision", "id": "vision-*", "tags": ["skipped"], "split": split, "input": {},
                 "output": None, "score": {}, "notes": ["NOT RUN: set ANTHROPIC_API_KEY to run the vision suite"],
                 "ms": 0, "pass": None}]
    import anthropic
    client = anthropic.Anthropic()
    model = model or os.environ.get("HL_VERIFY_MODEL", "claude-sonnet-5-5")
    rows = []
    for case in load("vision_check.jsonl", split):
        rec = case["input"]
        claim = rec.get("claim_slot", rec["slot"])
        _, data, mime = images.render(rec)
        for run in range(runs):
            t = time.perf_counter()
            try:
                raw, tin, tout = _vision_call(client, model, data, mime, images.BRAND, *SLOT_TEXT[claim])
            except Exception as e:  # the product sends these to a person; the eval records them
                raw, tin, tout = None, 0, 0
            ms = round((time.perf_counter() - t) * 1000)
            ok = bool(raw) and all(raw.get(k) for k in ("logo_visible", "brand_matches", "placement_matches"))
            conf = float(raw.get("confidence", 0)) if raw else 0.0
            decision = "verified" if ok and conf >= 0.8 else "not_verified"
            score, notes = G.grade_vision(case, raw, decision)
            rows.append({"suite": "vision", "id": case["id"], "run": run, "tags": case["tags"], "split": case["split"],
                         "input": rec, "output": {"raw": raw, "decision": decision}, "score": score, "notes": notes,
                         "ms": ms, "tokens": [tin, tout], "pass": score["decision_ok"] and score["schema_ok"]})
    return rows


def suite_messages(split, **_):
    return [{"suite": "messages", "id": "msg-*", "tags": ["skipped"], "split": split, "input": {}, "output": None,
             "score": {}, "notes": ["NOT RUN: message drafting is not built yet; rubric in judges/message_drafts.md"],
             "ms": 0, "pass": None}]


# ------------------------------------------------------------------ summary
def summarize(rows):
    S = {}
    for suite in dict.fromkeys(r["suite"] for r in rows):
        rs = [r for r in rows if r["suite"] == suite]
        ran = [r for r in rs if r["pass"] is not None]
        s = {"cases": len(ran), "passed": sum(1 for r in ran if r["pass"]), "ran": bool(ran)}
        if ran:
            s["pass_rate"] = round(s["passed"] / len(ran), 3)
            s["median_ms"] = sorted(r["ms"] for r in ran)[len(ran) // 2]
        if suite == "brief" and ran:
            tot = {f: [0, 0, 0] for f in G.FIELDS}
            for r in ran:
                for f, c in r["score"]["counts"].items():
                    for j in range(3):
                        tot[f][j] += c[j]
            s["per_field"] = {f: dict(zip(("precision", "recall", "f1"), (round(x, 3) for x in G.prf(*c))))
                              for f, c in tot.items()}
            alltp = [sum(c[j] for c in tot.values()) for j in range(3)]
            s["micro"] = dict(zip(("precision", "recall", "f1"), (round(x, 3) for x in G.prf(*alltp))))
            s["budget_accuracy"] = round(sum(r["score"]["budget_ok"] for r in ran) / len(ran), 3)
        if suite in ("rank", "host") and ran:
            s["constraint_violations"] = sum(r["score"]["violations"] for r in ran)
            s["hit_at_3"] = round(sum(r["score"]["hit_at_3"] for r in ran) / len(ran), 3)
            s["ndcg_at_3"] = round(sum(r["score"]["ndcg_at_3"] for r in ran) / len(ran), 3)
            if suite == "rank":
                s["mrr"] = round(sum(r["score"]["mrr"] for r in ran) / len(ran), 3)
        if suite == "photo" and ran:
            c = {k: sum(1 for r in ran if r["score"]["outcome"] == k) for k in ("tp", "tn", "fp", "fn")}
            s["confusion"] = c
            s["accuracy"] = round((c["tp"] + c["tn"]) / len(ran), 3)
            s["bad_photo_catch_rate"] = round(c["tn"] / (c["tn"] + c["fp"]), 3) if c["tn"] + c["fp"] else None
            s["good_photo_pass_rate"] = round(c["tp"] / (c["tp"] + c["fn"]), 3) if c["tp"] + c["fn"] else None
        if suite == "routing" and ran:
            s["unsafe_auto_verify"] = sum(r["score"]["unsafe_auto_verify"] for r in ran)
        if suite == "vision" and ran:
            s["false_verify_rate"] = round(sum(r["score"]["false_verify"] for r in ran) / len(ran), 3)
            s["schema_ok_rate"] = round(sum(r["score"]["schema_ok"] for r in ran) / len(ran), 3)
            s["tokens_in"] = sum(r["tokens"][0] for r in ran)
            s["tokens_out"] = sum(r["tokens"][1] for r in ran)
        # per-slice pass rate
        sl = {}
        for r in ran:
            for t in r["tags"]:
                a = sl.setdefault(t, [0, 0])
                a[0] += bool(r["pass"])
                a[1] += 1
        s["slices"] = {t: f"{a[0]}/{a[1]}" for t, a in sorted(sl.items())}
        S[suite] = s
    return S


def get(d, path):
    for p in path.split("."):
        if d is None:
            return None
        d = d.get(p)
    return d


def check_thresholds(S):
    T = json.load(open(EVALS / "thresholds.json"))
    out = []
    for t in T:
        v = get(S, t["metric"])
        if v is None:
            out.append({**t, "value": None, "status": "not run"})
            continue
        ok = v >= t["min"] if "min" in t else v <= t["max"]
        out.append({**t, "value": v, "status": "pass" if ok else "FAIL"})
    return out


def write_md(S, checks, rows, path, compare=None):
    L = [f"# Tablematch eval run {path.parent.name}", "", f"Dataset version {open(EVALS / 'datasets' / 'VERSION').read().strip()}", ""]
    L += ["## Thresholds", "", "| Level | Metric | Value | Target | Status |", "|---|---|---|---|---|"]
    for c in checks:
        tgt = f">= {c['min']}" if "min" in c else f"<= {c['max']}"
        L.append(f"| {c['level']} | {c['metric']} | {c['value']} | {tgt} | {c['status']} |")
    L += ["", "## Suites", "", "| Suite | Cases | Passed | Pass rate |" + (" Baseline |" if compare else ""),
          "|---|---|---|---|" + ("---|" if compare else "")]
    for k, s in S.items():
        base = f" {compare.get(k, {}).get('pass_rate', '')} |" if compare else ""
        L.append(f"| {k} | {s['cases']} | {s['passed']} | {s.get('pass_rate', 'not run')} |" + base)
    L += ["", "## Failures", ""]
    for r in rows:
        if r["pass"] is False:
            L.append(f"- **{r['id']}** ({', '.join(r['tags'])}): " + "; ".join(r["notes"]))
    skipped = [r for r in rows if r["pass"] is None]
    if skipped:
        L += ["", "## Not run", ""] + [f"- **{r['suite']}**: " + "; ".join(r["notes"]) for r in skipped]
    path.write_text("\n".join(L) + "\n")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--suite", nargs="*", default=None)
    ap.add_argument("--split", default="all", choices=["all", "dev", "held_out"])
    ap.add_argument("--live", action="store_true")
    ap.add_argument("--runs", type=int, default=3, help="repeats per case for model suites")
    ap.add_argument("--model", default=None)
    ap.add_argument("--compare", default=None)
    ap.add_argument("--out", default=None)
    ap.add_argument("--gate", default="thresholds", choices=["thresholds", "regression"],
                    help="thresholds: fail on any must-have below target. regression: fail only if a must-have "
                         "metric is worse than --compare (a ratchet while known failures are being fixed)")
    a = ap.parse_args()
    suites = a.suite or (OFFLINE + (LIVE if a.live else []))
    client, events, sponsors = app_state()
    ctx = {"client": client, "events": events, "sponsors": sponsors, "runs": a.runs, "model": a.model}
    rows = []
    for s in suites:
        rows += globals()["suite_" + s](a.split, **ctx)
    S = summarize(rows)
    checks = check_thresholds(S)
    run_id = a.out or datetime.now().strftime("%Y%m%d-%H%M%S")
    out = EVALS / "results" / run_id
    out.mkdir(parents=True, exist_ok=True)
    with open(out / "results.jsonl", "w") as f:
        for r in rows:
            f.write(json.dumps(r, default=str) + "\n")
    json.dump({"run": run_id, "date": date.today().isoformat(), "split": a.split, "suites": S, "thresholds": checks},
              open(out / "summary.json", "w"), indent=2)
    compare = json.load(open(a.compare))["suites"] if a.compare else None
    write_md(S, checks, rows, out / "summary.md", compare)
    print(open(out / "summary.md").read())
    if a.gate == "regression":
        if not a.compare:
            sys.exit("--gate regression needs --compare <baseline summary.json>")
        base = {c["metric"]: c for c in json.load(open(a.compare))["thresholds"]}
        failed = []
        for c in checks:
            b = base.get(c["metric"], {}).get("value")
            if c["level"] != "must" or c["value"] is None or b is None:
                continue
            worse = c["value"] < b if "min" in c else c["value"] > b
            if worse:
                failed.append(c)
                print(f"REGRESSION {c['metric']}: {b} -> {c['value']}")
    else:
        failed = [c for c in checks if c["level"] == "must" and c["status"] == "FAIL"]
    sys.exit(1 if failed else 0)


if __name__ == "__main__":
    main()
