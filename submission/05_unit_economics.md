# Tablematch — Deliverable 5: Unit economics

**Claim.** Tablematch's AI step is compared on **the same 10 tasks on two model tiers**, Claude Sonnet 5.5
(default) and Claude Haiku 5.5 (cheaper), measuring **latency**, **cost per 100 runs** and **quality**, with a
stated rule for **the trade-off we accept**: the cheaper tier is used only if it never wrongly verifies a
placement. The section also places the AI cost inside the business's unit economics per transaction.

| Item | Where |
| --- | --- |
| The 10 tasks (golden cases g01 to g10) | https://github.com/wop29/TableMatch-Vf/blob/main/evals/golden/golden_cases.jsonl |
| Runner | https://github.com/wop29/TableMatch-Vf/blob/main/evals/golden/run_model_evals.py |
| Scorer (computes everything below) | https://github.com/wop29/TableMatch-Vf/blob/main/evals/golden/score_golden.py |
| Prices and token accounting | https://github.com/wop29/TableMatch-Vf/blob/main/app/vision.py (`PRICES`, `check`) |
| Business unit economics report | https://github.com/wop29/TableMatch-Vf/blob/main/submission/evidence/Tablematch_Unit_Economics_and_Business_Model.md |

---

## 1. The comparison set-up

| Item | Value |
| --- | --- |
| Task | Decide from a proof photo whether the sponsor's placement is shown (three flags and a confidence), then route by fixed rules |
| The 10 tasks | g01 to g10: 4 should be verified, 3 should go to a person, 3 should ask for more evidence. Includes a wrong brand, a look-alike brand, a prompt-injection sign, a photo with no logo, a heavy blur and a placement of the wrong type (full list in Deliverable 4) |
| Tier A (default) | `claude-sonnet-5-5` |
| Tier B (cheaper) | `claude-haiku-5-5` |
| Held identical | Images, system message, prompt, knowledge context, `max_tokens` 300, image resizing (longest edge 1,568 px), routing rules |
| Runs | 1 per task per tier by default; `--runs 3` repeats each task to measure consistency and steadier latency |
| **Quality** | Share of tasks whose route matches the expected output. Reported with two error types: **false verifies** (money would be released wrongly) and **over-strict** (good proof sent back) |
| **Latency** | Wall-clock time of each API call, reported as median (p50) and 95th percentile (p95) |
| **Cost per 100 runs** | Measured input and output tokens of each call times list price, averaged, times 100 |
| Prices (USD per million tokens, input / output) | Haiku 5.5 \$0.10 / \$0.50; Sonnet 5.5 \$2.00 / \$10.00; Opus 5.5 \$4.00 / \$20.00 (Claude API pricing page, November 2026) |

## 2. Measured results

<!-- RESULTS:START -->
**Not yet run.** This needs an Anthropic API key (about 40 calls in total, estimated under \$1). When run,
`evals/golden/score_golden.py` replaces this block with a table of both tiers on the same 10 tasks: quality,
false verifies, over-strict cases, latency p50 and p95, cost per 100 runs and tokens per run, plus the result
of the trade-off rule below.
<!-- RESULTS:END -->

## 3. Expected cost before measuring (estimate)

Token arithmetic for one check of one 1200 x 900 photo. Image tokens follow Claude's published rule of one
token per 28 x 28 pixel patch. Text tokens are estimated at four characters per token. Output is estimated
from the JSON answer's length. These are estimates to sanity-check the measured numbers.

| Component | Tokens |
| --- | --- |
| Image (43 x 33 patches) | 1,419 |
| System message, sponsor, agreement and guideline slice | about 444 |
| **Input per check** | **about 1,863** |
| Output (JSON answer) | about 90 |

| Tier | Cost per check | **Cost per 100 runs** | Per 1,000 checks |
| --- | --- | --- | --- |
| Haiku 5.5 | \$0.00023 | **\$0.023** | \$0.23 |
| Sonnet 5.5 | \$0.00463 | **\$0.46** | \$4.63 |
| Opus 5.5 (judge only, not a candidate) | \$0.00925 | \$0.93 | \$9.25 |

On these estimates Sonnet costs about 20 times more than Haiku per check, but both are small in absolute terms.

## 4. The trade-off we accept

**Rule, applied automatically by the scorer:** use the cheaper tier only if it has **zero false verifies** on
the 10 tasks **and** its route accuracy is within **10 percentage points** of the default tier. Otherwise keep
the default tier.

Why we draw the line there:

| Consideration | Number | What it means |
| --- | --- | --- |
| Cost of one false verify | The deal value, on average \$1,200 (base case), plus the brand's trust in escrow | One wrong release costs more than about 260,000 Sonnet checks at the estimated price |
| Cost of the AI per transaction | About 18 images per base-case transaction; at about \$0.0046 each on Sonnet, roughly \$0.08 per transaction against a \$360 fee | Under 0.1% of the fee; the saving from switching tier is cents |
| Cost of being over-strict | A host retakes a photo, or a reviewer spends about 6 minutes (about \$4.38 at \$43.75 an hour) | Real but bounded, and it does not lose a brand's money |

So we accept paying more per check and some over-strictness in exchange for no wrong releases. If Haiku
passes the rule, the planned design is a **hybrid**: Haiku screens every photo; anything it does not clearly
verify goes to Sonnet; disputes go to a person.

## 5. Where the AI cost sits in the business

From the Tablematch unit economics model (base-case estimates; full report linked above). One transaction is
one brand buying one placement or one package at one event.

| Per transaction | Conservative | **Base** | Optimistic |
| --- | --- | --- | --- |
| Average deal value | \$700 | **\$1,200** | \$2,000 |
| Platform fee (30%, cap \$3,000) | \$210.00 | **\$360.00** | \$600.00 |
| Payment fees (cards, bank transfer, payouts, accounts) | \$20.70 | **\$29.04** | \$34.59 |
| People: ops, support and payout approval | \$29.66 | **\$17.21** | \$7.75 |
| People: review of flagged proof and disputes | \$4.27 | **\$1.97** | \$0.82 |
| AI proof checks, detector and storage | \$1.15 | **\$0.33** | \$0.08 |
| Other AI (matching, message drafts) | \$0.15 | **\$0.10** | \$0.05 |
| Total variable cost | \$56.88 | **\$49.57** | \$43.81 |
| **Contribution profit** | \$153.12 | **\$310.43** | \$556.19 |
| Contribution margin (of the fee) | 73% | **86%** | 93% |
| Break-even, transactions a month | 51 | **40** | 42 |

**Reading.** AI and evidence technology is about 1% of
variable cost in the base case. Payment fees and people are about
97%. The model-tier decision is therefore a quality and
safety decision, not a cost decision; the business's results depend on deal size, take rate and repeat brands.

### Stress case: lots of photos

The model also tests a photo-heavy event: 150 guests, a 5-placement package, 30 photos and two one-minute
videos per placement, 40% resubmitted, 300 such events a month. Analysing every video frame at full resolution
on Sonnet costs about \$24.72 per event (\$7,415 a month). Five design choices (resize photos, sample one video
frame every five seconds, cache the prompt, use batch processing, let Haiku screen with Sonnet rechecking 20%)
bring it to about \$1.34 per event (\$401 a month), against a \$3,000 fee. Details are in the business report.

## 6. Limits

- Latency is measured from the person running the script to the API, so it includes their network.
- 10 tasks give direction, not precision; `--runs 3` improves the latency estimate and shows consistency.
- Prices are list prices; batch and caching discounts are excluded from the tier comparison so both tiers are
  compared on the same terms.
- The business figures are estimates from the team's model, not observed sales.
