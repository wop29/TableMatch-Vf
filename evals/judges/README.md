# LLM judges

Used only where a code check cannot decide: the wording of the vision model's notes and drafted messages.
Rules (from the eval plan):

- One criterion per judge call. Each rubric file below is one criterion.
- Pass / fail, with one to two sentences of reasoning written BEFORE the verdict.
- Give the judge the reference facts (the agreement, the expected decision) whenever they exist.
- Judge model: a different model family or tier from the system under test, to limit self-preference.
- Verbosity bias: rubrics say length is not a reason to pass.

## Calibration (required before any judge result is trusted)

1. Two people hand-label 30 outputs per rubric using `calibration/labeling_sheet.csv`.
2. Resolve disagreements; rewrite the rubric where the disagreement came from unclear wording.
3. Run the judge on the same 30. Report agreement and Cohen's kappa against the resolved human labels.
4. Trust the judge only at kappa >= 0.7 and at least 90% agreement on the FAIL class. Otherwise revise and repeat.

Status: no judge has been calibrated yet. Judge-based scores are therefore not part of the baseline.
