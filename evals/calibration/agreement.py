"""Agreement between a judge and resolved human labels. Usage: python evals/calibration/agreement.py sheet.csv"""
import csv
import sys

rows = [r for r in csv.DictReader(open(sys.argv[1])) if r["resolved"] and r["judge_verdict"]]
if not rows:
    sys.exit("No rows with both a resolved human label and a judge verdict yet.")
n = len(rows)
agree = sum(r["resolved"] == r["judge_verdict"] for r in rows) / n
labels = sorted({r["resolved"] for r in rows} | {r["judge_verdict"] for r in rows})
pe = sum((sum(r["resolved"] == l for r in rows) / n) * (sum(r["judge_verdict"] == l for r in rows) / n) for l in labels)
kappa = (agree - pe) / (1 - pe) if pe < 1 else 1.0
fails = [r for r in rows if r["resolved"] == "FAIL"]
fail_recall = sum(r["judge_verdict"] == "FAIL" for r in fails) / len(fails) if fails else None
print(f"n={n} agreement={agree:.2f} kappa={kappa:.2f} fail_recall={fail_recall}")
print("TRUST" if kappa >= 0.7 and (fail_recall or 0) >= 0.9 else "DO NOT TRUST YET: revise the rubric")
