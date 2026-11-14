"""Graders. Each takes (case, output) and returns a dict of named scores plus a list of failure notes.

Code graders only. LLM-judge rubrics live in evals/judges/ and are applied by run_evals.py when a model is
available (they need an API key and a calibrated judge; see judges/README.md).
"""
import math
from datetime import date

FIELDS = ["vibes", "audiences", "interests", "places", "slot_types"]


# ------------------------------------------------------------------ brief parsing
def grade_brief(case, out):
    exp, allow = case["expected"], case.get("allow", {})
    counts, notes = {}, []
    for f in FIELDS:
        want, got = set(exp[f]), set(out[f])
        ok_extra = set(allow.get(f, []))
        tp = len(want & got)
        fp = len(got - want - ok_extra)
        fn = len(want - got)
        counts[f] = (tp, fp, fn)
        if fn:
            notes.append(f"missed {f}: {sorted(want - got)}")
        if fp:
            notes.append(f"wrong {f}: {sorted(got - want - ok_extra)}")
    b_ok = (exp["budget"] is None and out["budget"] is None) or (
        exp["budget"] is not None and out["budget"] is not None and abs(exp["budget"] - out["budget"]) < 0.5)
    if not b_ok:
        notes.append(f"budget: expected {exp['budget']}, got {out['budget']}")
    exact = b_ok and all(c[1] == 0 and c[2] == 0 for c in counts.values())
    return {"exact": exact, "budget_ok": b_ok, "counts": counts}, notes


def prf(tp, fp, fn):
    p = tp / (tp + fp) if tp + fp else 1.0
    r = tp / (tp + fn) if tp + fn else 1.0
    f = 2 * p * r / (p + r) if p + r else 0.0
    return p, r, f


# ------------------------------------------------------------------ ranking
def ndcg_at_k(ranked_names, relevance, k=3):
    gains = [relevance.get(n, 0) for n in ranked_names[:k]]
    dcg = sum((2 ** g - 1) / math.log2(i + 2) for i, g in enumerate(gains))
    ideal = sorted(relevance.values(), reverse=True)[:k]
    idcg = sum((2 ** g - 1) / math.log2(i + 2) for i, g in enumerate(ideal))
    return dcg / idcg if idcg else 1.0


def grade_event_ranking(case, results, sponsor, today=None):
    """results: list of {event, matching_slot_ids, score}. Checks hard constraints, then relevance."""
    today = today or date.today()
    inp, notes, violations = case["input"], [], 0
    budget = inp.get("budget")
    for r in results:
        ev = r["event"]
        open_slots = [s for s in ev["slots"] if s["status"] == "open"]
        if inp.get("slot_type"):
            open_slots = [s for s in open_slots if s["type"] == inp["slot_type"]]
        if not open_slots:
            violations += 1
            notes.append(f"VIOLATION {ev['title']}: no open slot of the requested type")
        b = budget if budget is not None else r.get("_parsed_budget")
        if b is not None and not any(s["price"] <= b for s in open_slots):
            violations += 1
            notes.append(f"VIOLATION {ev['title']}: nothing within budget {b}")
        if sponsor:
            dens = ev.get("density") or {}
            here = sponsor["id"] in dens.get("sponsor_ids", [])
            if sponsor["cat"] in (ev.get("excluded_cats") or []):
                violations += 1
                notes.append(f"VIOLATION {ev['title']}: host excludes {sponsor['cat']}")
            if not here and sponsor["cat"] in dens.get("taken_cats", []):
                violations += 1
                notes.append(f"VIOLATION {ev['title']}: category {sponsor['cat']} already taken")
        f = inp.get("filters") or {}
        if f.get("borough") and ev["borough"].lower() != f["borough"].lower():
            violations += 1
            notes.append(f"VIOLATION {ev['title']}: outside borough filter")
        if f.get("kind") and ev.get("kind") != f["kind"]:
            violations += 1
            notes.append(f"VIOLATION {ev['title']}: wrong kind")
        if date.fromisoformat(ev["date"]) < today:
            violations += 1
            notes.append(f"VIOLATION {ev['title']}: event already happened")
        if not (0 <= r["score"] <= 100):
            violations += 1
            notes.append(f"VIOLATION {ev['title']}: score out of range")
        if not r.get("reasons"):
            violations += 1
            notes.append(f"VIOLATION {ev['title']}: no explanation shown")
    names = [r["event"]["title"] for r in results]
    rel = {k: v for k, v in case["expected"]["relevant"].items()}
    best = [k for k, v in rel.items() if v == max(rel.values())] if rel else []
    hit3 = any(n in best for n in names[:3]) if best else True
    rr = next((1 / (i + 1) for i, n in enumerate(names) if rel.get(n, 0) >= 1), 0.0)
    nd = ndcg_at_k(names, rel)
    if not hit3:
        notes.append(f"top 3 = {names[:3]}; expected one of {best}")
    return {"violations": violations, "hit_at_3": hit3, "mrr": rr, "ndcg_at_3": nd, "n_results": len(results)}, notes


def grade_host_ranking(case, results, package, event):
    notes, violations = [], 0
    dens = event.get("density") or {}
    open_ids = {s["id"]: s for s in event["slots"] if s["status"] == "open"}
    for r in results:
        sp = r["sponsor"]
        here = sp["id"] in dens.get("sponsor_ids", [])
        if sp["cat"] in (event.get("excluded_cats") or []):
            violations += 1
            notes.append(f"VIOLATION {sp['name']}: excluded category shown")
        if not here and sp["cat"] in dens.get("taken_cats", []):
            violations += 1
            notes.append(f"VIOLATION {sp['name']}: category already taken")
    by_name = {r["sponsor"]["name"]: r["sponsor"] for r in results}
    cats, used = set(), set()
    room = package.get("room", 99)
    if len(package["items"]) > room:
        violations += 1
        notes.append(f"VIOLATION package has {len(package['items'])} brands, room for {room}")
    for it in package["items"]:
        sp = by_name.get(it["sponsor"])
        if sp is None:
            violations += 1
            notes.append(f"VIOLATION package names a hidden brand {it['sponsor']}")
            continue
        if sp["cat"] in cats:
            violations += 1
            notes.append(f"VIOLATION two brands in category {sp['cat']}")
        cats.add(sp["cat"])
        if it["price"] > sp["budget_max"]:
            violations += 1
            notes.append(f"VIOLATION {sp['name']} suggested above its budget")
        slot = next((s for s in open_ids.values() if s["title"] == it["slot"] and s["price"] == it["price"]), None)
        if slot is None or (slot["id"] in used):
            violations += 1
            notes.append(f"VIOLATION package slot {it['slot']} not open or used twice")
        else:
            used.add(slot["id"])
    names = [r["sponsor"]["name"] for r in results]
    rel = case["expected"]["relevant"]
    best = [k for k, v in rel.items() if v == max(rel.values())]
    hit3 = any(n in best for n in names[:3])
    if not hit3:
        notes.append(f"top 3 = {names[:3]}; expected one of {best}")
    return {"violations": violations, "hit_at_3": hit3, "ndcg_at_3": ndcg_at_k(names, rel)}, notes


# ------------------------------------------------------------------ photo quality gate
def grade_photo(case, passed):
    exp = case["expected"]["pass"]
    kind = "tp" if exp and passed else "tn" if not exp and not passed else "fn" if exp else "fp"
    notes = []
    if kind == "fp":
        notes.append("gate let through a photo a person could not judge")
    if kind == "fn":
        notes.append("gate rejected a usable photo (host must retake)")
    return {"outcome": kind, "correct": kind in ("tp", "tn")}, notes


# ------------------------------------------------------------------ risk routing
def grade_route(case, band, decision, score):
    exp, notes = case["expected"], []
    ok = True
    if "band" in exp and band != exp["band"]:
        ok = False
        notes.append(f"band {band}, expected {exp['band']}")
    if "band_in" in exp and band not in exp["band_in"]:
        ok = False
        notes.append(f"band {band}, expected one of {exp['band_in']}")
    if "decision" in exp and decision != exp["decision"]:
        ok = False
        notes.append(f"decision {decision}, expected {exp['decision']}")
    if "decision_in" in exp and decision not in exp["decision_in"]:
        ok = False
        notes.append(f"decision {decision}, expected one of {exp['decision_in']}")
    unsafe = decision == "verified" and exp.get("decision", exp.get("decision_in", ["verified"])) not in ("verified", ["verified"])
    if unsafe:
        notes.append(f"UNSAFE: auto-verified (score {score}) where a person or more evidence was needed")
    return {"correct": ok, "unsafe_auto_verify": unsafe}, notes


# ------------------------------------------------------------------ vision check (model output)
VISION_KEYS = {"logo_visible": bool, "brand_matches": bool, "placement_matches": bool, "confidence": (int, float), "notes": str}


def grade_vision(case, raw, decision):
    """raw: parsed JSON from the model (or None). decision: verified | rejected | needs_review."""
    notes = []
    schema_ok = isinstance(raw, dict) and all(isinstance(raw.get(k), t) for k, t in VISION_KEYS.items())
    if not schema_ok:
        notes.append("output did not match the JSON schema")
    exp = case["expected"]
    field_ok = all(raw.get(k) == v for k, v in exp.items() if k in VISION_KEYS) if schema_ok else False
    if schema_ok and not field_ok:
        notes.append("field mismatch: " + ", ".join(f"{k}={raw.get(k)} (want {v})" for k, v in exp.items()
                                                  if k in VISION_KEYS and raw.get(k) != v))
    want_verified = exp["decision"] == "verified"
    false_verify = decision == "verified" and not want_verified
    missed = want_verified and decision != "verified"
    if false_verify:
        notes.append("FALSE VERIFY: money would be released for a placement that was not shown")
    return {"schema_ok": schema_ok, "fields_ok": field_ok, "false_verify": false_verify, "missed_verify": missed,
            "decision_ok": (decision == "verified") == want_verified}, notes
