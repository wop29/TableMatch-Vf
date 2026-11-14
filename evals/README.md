# Tablematch evals

A repeatable eval suite for every place Tablematch's AI or automated rules make a decision that
affects money or trust. Built with the eval workflow: scope, define good, error analysis first, cheapest
reliable method per criterion, versioned datasets, graders, judge calibration, harness, baseline, CI.

## What is tested

| Suite | Code under test | Cases | Method | Runs offline |
|---|---|---|---|---|
| `brief` | `app/matching.py` `parse_brief` | 40 | Per-field P/R/F1 against hand labels | yes |
| `rank` | `matching.rank_events` | 20 | Hard-constraint checks on every result + hit@3, MRR, nDCG@3 | yes |
| `host` | `matching.rank_sponsors` (via `/api/search/sponsors`) | 8 | Constraint + package checks + hit@3, nDCG@3 | yes |
| `photo` | `app/verify.py` `_quality` | 48 images | Pass/reject vs human judgment of rendered images | yes |
| `routing` | `app/evidence.py` `risk` + `decide` | 12 | Expected band and decision; unsafe auto-verify count | yes |
| `routing_props` | same | 2,000 random samples | 5 policy invariants (property tests, fixed seed) | yes |
| `privacy` | `evidence.ingest` | 2 | Original intact, hash, no GPS in shared copy, blur | yes |
| `vision` | `verify._claude` prompt | 24 images x 3 runs | Schema, fields, decision, false-verify rate | needs `ANTHROPIC_API_KEY` |
| `messages` | not built yet | 6 | LLM judge rubric | not runnable yet |

## Run

```bash
pip install -r requirements.txt pytest httpx
python -m pytest -q                                          # 29 app tests + 5 grader tests
python evals/run_evals.py                                    # all offline suites (~3 s, no network)
python evals/run_evals.py --suite brief photo --split held_out
python evals/run_evals.py --compare evals/baseline/summary.json --gate regression
ANTHROPIC_API_KEY=... python evals/run_evals.py --suite vision --runs 3
```

Output: `evals/results/<run>/results.jsonl` (per case: input, output, scores, notes),
`summary.json`, `summary.md`. Exit code 1 when a must-have threshold fails (`--gate thresholds`, default)
or when a must-have metric is worse than the baseline (`--gate regression`).

## Baseline (14 Nov 2026, commit f78e944)

105 of 135 offline cases pass. Must-haves: 3 of 5 runnable pass; 2 not run (vision).

| Must-have | Baseline | Target |
|---|---|---|
| Constraint violations, brand side | 0 | 0 |
| Constraint violations, host side | 0 | 0 |
| Unsafe auto-verifies | **2** | 0 |
| Routing invariants | 100% | 100% |
| Privacy checks | **50%** | 100% |
| Vision false-verify rate | not run | <= 1% |

Full numbers: `evals/baseline/summary.md`. Known failures and their root causes:

1. Unclear proof (placement not shown + missing evidence; setting + metadata mismatch) is auto-verified, because
   "more evidence" and must-review triggers are keyed on demo scenario names, not on the signals.
2. When face blur is off, the copy shared with sponsors is the original file, GPS included.
3. Brief reading misses negation, budgets without "$", ranges, slang and typos (places F1 0.71).
4. The photo gate rejects readable photos under 640 px and passes a blank frame.

## Files

- `build_datasets.py` writes `datasets/*.jsonl` (version in `datasets/VERSION`). Gold labels are hand-written.
- `images.py` renders the synthetic photo cases. `graders.py` code graders. `run_evals.py` harness.
- `thresholds.json` must-have / should targets. `judges/` LLM judge rubrics. `calibration/` labeling sheet
  and agreement script (judges are trusted only at kappa >= 0.7).
- `baseline/` the committed baseline run. `results/` new runs (git-ignored).

## Limits

One labeler; small datasets; synthetic photos; the prototype's provenance and vision findings are simulated,
so routing is tested on chosen signal levels; no model or judge results yet; no AI-image detector suite.
