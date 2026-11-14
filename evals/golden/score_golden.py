"""Scores a model run of the golden set and writes the results into the submission files.

    python evals/golden/score_golden.py               # latest real run + evals/golden/team_scores.csv
    python evals/golden/score_golden.py --run <dir>   # a specific run

Outputs:
  evals/golden/results/<run>/summary.json   every number below, machine-readable
  submission/04_eval_pack.md                results block between the RESULTS markers is regenerated
  submission/05_unit_economics.md           results block between the RESULTS markers is regenerated
Nothing is invented: a number that cannot be computed yet (for example team scores not filled) is shown as
"pending" with what is missing.
"""
import argparse
import csv
import json
import re
import statistics
import sys
from collections import Counter, defaultdict
from pathlib import Path

HERE = Path(__file__).parent
ROOT = HERE.parents[1]
SUB = ROOT / "submission"
GENERIC = {"photo", "drawn", "common"}
PATTERN = {
    "wrong-brand": "Wrong brand not caught", "lookalike": "Look-alike brand name accepted",
    "injection": "Followed or was swayed by text written inside the photo",
    "no-logo": "Claimed a logo where none is visible", "unclear": "Judged a photo too blurred to read",
    "occluded": "Judged a logo that is covered", "wrong-placement": "Accepted the wrong placement type",
    "dark": "Rejected a dim but readable photo", "common": "Did not verify a clear, correct placement",
}


def rows(path):
    return [json.loads(line) for line in open(path)] if path.exists() else []


def auto_score(o):
    exp, raw = o["expected"], o.get("raw") or {}
    route_ok = o["route"] == exp["route"]
    fields = {k: raw.get(k) == v for k, v in exp.items() if k != "route" and v is not None}
    return {"route_ok": route_ok, "fields_ok": all(fields.values()) if fields else True,
            "false_verify": o["route"] == "verified" and exp["route"] != "verified",
            "over_strict": exp["route"] == "verified" and o["route"] != "verified"}


def pct(x):
    return f"{round(100 * x)}%" if x is not None else "pending"


def kappa(a, b):
    n = len(a)
    if not n:
        return None
    po = sum(x == y for x, y in zip(a, b)) / n
    labels = set(a) | set(b)
    pe = sum((a.count(l) / n) * (b.count(l) / n) for l in labels)
    return round((po - pe) / (1 - pe), 2) if pe < 1 else 1.0


def tier_stats(outs):
    sc = [auto_score(o) for o in outs]
    lat = sorted(o["latency_ms"] for o in outs)
    cost = [o["cost_usd"] for o in outs]
    return {"model": outs[0]["model"], "calls": len(outs),
            "route_accuracy": round(sum(s["route_ok"] for s in sc) / len(sc), 3),
            "field_accuracy": round(sum(s["fields_ok"] for s in sc) / len(sc), 3),
            "false_verifies": sum(s["false_verify"] for s in sc),
            "over_strict": sum(s["over_strict"] for s in sc),
            "parse_failures": sum(1 for o in outs if o.get("raw") is None),
            "latency_p50_ms": int(statistics.median(lat)),
            "latency_p95_ms": int(lat[min(len(lat) - 1, round(0.95 * (len(lat) - 1)))]),
            "cost_per_call_usd": round(sum(cost) / len(cost), 6),
            "cost_per_100_runs_usd": round(100 * sum(cost) / len(cost), 4),
            "mean_input_tokens": int(sum(o["input_tokens"] for o in outs) / len(outs)),
            "mean_output_tokens": int(sum(o["output_tokens"] for o in outs) / len(outs))}


def failure_patterns(outs_a, outs_b, team):
    counts, examples = Counter(), defaultdict(list)
    for o in outs_a + outs_b:
        if not auto_score(o)["route_ok"]:
            tag = next((t for t in o["tags"] if t not in GENERIC), "common")
            key = PATTERN.get(tag, tag)
            counts[key] += 1
            examples[key].append(f"{o['case_id']} ({o['model'].replace('claude-', '')}): expected {o['expected']['route']}, got {o['route']}")
    for r in team:
        if r.get("team_score", "").upper() == "FAIL" and r.get("comment"):
            key = "Team: " + r["comment"].strip()[:80]
            counts[key] += 1
            examples[key].append(r["case_id"])
    return [{"pattern": k, "count": c, "examples": examples[k][:4]} for k, c in counts.most_common(3)]


def replace_block(path, text):
    s = path.read_text()
    text = re.sub(r"(?<!\\)\$", r"\\$", text)  # escape dollars so GitHub does not render them as math
    new = re.sub(r"(<!-- RESULTS:START -->).*?(<!-- RESULTS:END -->)", lambda m: m.group(1) + "\n" + text + "\n" + m.group(2), s, flags=re.S)
    path.write_text(new)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--run", default=None)
    ap.add_argument("--team", default=str(HERE / "team_scores.csv"))
    ap.add_argument("--no-write", action="store_true", help="compute only; do not touch submission files")
    a = ap.parse_args()
    run_dir = Path(a.run) if a.run else HERE / "results" / (HERE / "results" / "LATEST").read_text().strip()
    meta = json.load(open(run_dir / "meta.json"))
    if meta["dry_run"] and not a.no_write:
        sys.exit("This is a dry run. Use --no-write to test scoring; dry-run numbers never go into the submission.")
    A, B, J = rows(run_dir / "tier_a_outputs.jsonl"), rows(run_dir / "tier_b_outputs.jsonl"), rows(run_dir / "judge.jsonl")
    team = list(csv.DictReader(open(a.team))) if Path(a.team).exists() else []
    tier_ids = {o["case_id"] for o in B}
    A10 = [o for o in A if o["case_id"] in tier_ids]

    # team scores
    filled = [r for r in team if r.get("team_score", "").strip().upper() in ("PASS", "FAIL")]
    both = [r for r in team if r.get("scorer_1", "").strip() and r.get("scorer_2", "").strip()]
    team_res = {"cases_scored": len(filled),
                "pass_rate": round(sum(r["team_score"].upper() == "PASS" for r in filled) / len(filled), 3) if filled else None,
                "scorer_agreement": round(sum(r["scorer_1"].upper() == r["scorer_2"].upper() for r in both) / len(both), 3) if both else None}

    # judge agreement with team, on the judged 10
    tmap = {r["case_id"]: r["team_score"].strip().upper() for r in filled}
    pairs = [(v["verdict"], tmap[v["case_id"]]) for v in J if v["verdict"] and v["case_id"] in tmap]
    judge_res = {"judge_model": meta["judge"], "system_model": meta["tier_a"], "cases": len(J),
                 "verdicts": dict(Counter(v["verdict"] for v in J)),
                 "agreement_with_team": round(sum(x == y for x, y in pairs) / len(pairs), 3) if len(pairs) == len(J) else None,
                 "kappa_with_team": kappa([p[0] for p in pairs], [p[1] for p in pairs]) if len(pairs) == len(J) else None,
                 "pairs_compared": len(pairs)}
    auto10 = {o["case_id"]: ("PASS" if auto_score(o)["route_ok"] else "FAIL") for o in A10}
    jp = [(v["verdict"], auto10[v["case_id"]]) for v in J if v["verdict"]]
    judge_res["agreement_with_expected"] = round(sum(x == y for x, y in jp) / len(jp), 3) if jp else None

    sA20, sA10, sB10 = tier_stats(A), tier_stats(A10), tier_stats(B)
    patterns = failure_patterns(A, B, filled)
    summary = {"run": meta["run"], "date": meta["date"], "knowledge_version": meta["knowledge_version"],
               "total_cost_usd": meta["total_cost_usd"], "tier_a_all_20": sA20, "tier_a_same_10": sA10,
               "tier_b_same_10": sB10, "team": team_res, "judge": judge_res, "top_failure_patterns": patterns}
    json.dump(summary, open(run_dir / "summary.json", "w"), indent=2)
    print(json.dumps(summary, indent=2))
    if a.no_write:
        return

    # ---- eval pack block
    L = [f"Run `{meta['run']}` on {meta['date'][:10]}; knowledge version `{meta['knowledge_version']}`; "
         f"total model cost ${meta['total_cost_usd']:.2f}. Raw outputs: `evals/golden/results/{meta['run']}/`.", "",
         "| Measure | Result |", "| --- | --- |",
         f"| Golden cases run (system: {sA20['model']}) | 20 |",
         f"| Route matches expected output | {round(sA20['route_accuracy'] * 20)}/20 ({pct(sA20['route_accuracy'])}) |",
         f"| All flags match expected output | {round(sA20['field_accuracy'] * 20)}/20 |",
         f"| False verifies (money would be released wrongly) | {sA20['false_verifies']} |",
         f"| Team score: outputs the team marked PASS | " + (f"{round(team_res['pass_rate'] * team_res['cases_scored'])}/{team_res['cases_scored']} ({pct(team_res['pass_rate'])})" if team_res["pass_rate"] is not None else "pending: fill evals/golden/team_scores.csv") + " |",
         f"| Agreement between the two team scorers | {pct(team_res['scorer_agreement'])} |",
         f"| Cross-model judge ({meta['judge']}) on 10 outputs: verdicts | {judge_res['verdicts']} |",
         f"| Judge agreement with team scores | " + (f"{pct(judge_res['agreement_with_team'])} (kappa {judge_res['kappa_with_team']})" if judge_res["agreement_with_team"] is not None else "pending: needs team scores for g01-g10") + " |",
         f"| Judge agreement with expected outputs | {pct(judge_res['agreement_with_expected'])} |", "",
         "### Top three failure patterns", ""]
    if patterns:
        for i, p in enumerate(patterns, 1):
            L.append(f"{i}. **{p['pattern']}** ({p['count']} case{'s' if p['count'] != 1 else ''}): " + "; ".join(p["examples"]))
    else:
        L.append("No failures in this run. The golden set should get harder cases; see the limits below.")
    replace_block(SUB / "04_eval_pack.md", "\n".join(L))

    # ---- unit economics block
    def row(name, s):
        return (f"| {name} | {s['model']} | {pct(s['route_accuracy'])} | {s['false_verifies']} | {s['over_strict']} | "
                f"{s['latency_p50_ms']:,} / {s['latency_p95_ms']:,} | ${s['cost_per_100_runs_usd']:.2f} | "
                f"{s['mean_input_tokens']:,} / {s['mean_output_tokens']} |")
    cheaper, better = (sB10, sA10) if sB10["cost_per_100_runs_usd"] <= sA10["cost_per_100_runs_usd"] else (sA10, sB10)
    safe = cheaper["false_verifies"] == 0 and cheaper["route_accuracy"] >= better["route_accuracy"] - 0.10
    choice = cheaper if safe else better
    U = [f"Same 10 tasks (g01-g10), same prompt, same knowledge context, run `{meta['run']}` on {meta['date'][:10]}. "
         "Cost uses list prices per million tokens: " + ", ".join(f"{k} ${v[0]}/${v[1]}" for k, v in meta["prices_per_million"].items() if k != meta["judge"]) + ".", "",
         "| Tier | Model | Quality: route right | False verifies | Over-strict | Latency p50 / p95 (ms) | Cost per 100 runs | Tokens in / out per run |",
         "| --- | --- | --- | --- | --- | --- | --- | --- |",
         row("A (default)", sA10), row("B (cheaper)", sB10), "",
         f"**Rule applied:** use the cheaper tier only if it has zero false verifies and is within 10 points of the better tier's quality. "
         f"Result: **{choice['model']}**. Cost difference: ${abs(sA10['cost_per_100_runs_usd'] - sB10['cost_per_100_runs_usd']):.2f} per 100 runs; "
         f"quality difference: {round(100 * abs(sA10['route_accuracy'] - sB10['route_accuracy']))} points."]
    replace_block(SUB / "05_unit_economics.md", "\n".join(U))
    print("Updated submission/04_eval_pack.md and submission/05_unit_economics.md")


if __name__ == "__main__":
    main()
