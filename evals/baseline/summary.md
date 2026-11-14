# Tablematch eval run baseline-run

Dataset version 1.0.0

## Thresholds

| Level | Metric | Value | Target | Status |
|---|---|---|---|---|
| must | rank.constraint_violations | 0 | <= 0 | pass |
| must | host.constraint_violations | 0 | <= 0 | pass |
| must | routing.unsafe_auto_verify | 2 | <= 0 | FAIL |
| must | routing_props.pass_rate | 1.0 | >= 1.0 | pass |
| must | privacy.pass_rate | 0.5 | >= 1.0 | FAIL |
| must | vision.false_verify_rate | None | <= 0.01 | not run |
| must | vision.schema_ok_rate | None | >= 0.99 | not run |
| should | brief.micro.f1 | 0.878 | >= 0.85 | pass |
| should | brief.budget_accuracy | 0.925 | >= 0.9 | pass |
| should | rank.hit_at_3 | 1.0 | >= 0.8 | pass |
| should | host.hit_at_3 | 0.875 | >= 0.75 | pass |
| should | photo.bad_photo_catch_rate | 0.857 | >= 0.9 | FAIL |
| should | photo.good_photo_pass_rate | 0.824 | >= 0.9 | FAIL |

## Suites

| Suite | Cases | Passed | Pass rate |
|---|---|---|---|
| brief | 40 | 24 | 0.6 |
| rank | 20 | 20 | 1.0 |
| host | 8 | 7 | 0.875 |
| photo | 48 | 40 | 0.833 |
| routing | 12 | 8 | 0.667 |
| routing_props | 5 | 5 | 1.0 |
| privacy | 2 | 1 | 0.5 |

## Failures

- **brief-010** (common): missed slot_types: ['menu']
- **brief-017** (edge, budget-format): wrong vibes: ['community']; budget: expected 600, got None
- **brief-018** (edge, budget-format): budget: expected 1200, got 800.0
- **brief-020** (edge, budget-format): budget: expected 2000, got None
- **brief-021** (edge, slang): missed places: ['Bushwick', 'DUMBO', 'Park Slope', 'Williamsburg']
- **brief-022** (edge, typo): missed places: ['Bushwick', 'Williamsburg']
- **brief-023** (edge, negation): wrong vibes: ['upscale']
- **brief-024** (edge, negation): wrong vibes: ['family']; wrong interests: ['family']
- **brief-025** (edge, negation): wrong places: ['Harlem', 'Lower East Side']
- **brief-026** (edge, hyphen): missed audiences: ['creatives']
- **brief-027** (edge, synonym): missed slot_types: ['table']
- **brief-030** (edge, implicit-age): missed audiences: ['young-professionals']
- **brief-031** (edge, false-friend): missed vibes: ['upscale']
- **brief-038** (adversarial, false-friend): wrong places: ['Lower East Side']
- **brief-039** (adversarial, conflict): wrong places: ['Bushwick', 'DUMBO', 'Park Slope', 'Williamsburg']
- **brief-040** (adversarial, language): missed audiences: ['young-professionals']
- **host-004** (notes): top 3 = ['Leafline', 'Tidewell', 'Pawlette']; expected one of ['Glowlab']
- **photo-005** (blur, borderline): gate rejected a usable photo (host must retake)
- **photo-016** (size): gate rejected a usable photo (host must retake)
- **photo-017** (size): gate rejected a usable photo (host must retake)
- **photo-024** (adversarial, no-content): gate let through a photo a person could not judge
- **photo-029** (blur, borderline): gate rejected a usable photo (host must retake)
- **photo-040** (size): gate rejected a usable photo (host must retake)
- **photo-041** (size): gate rejected a usable photo (host must retake)
- **photo-048** (adversarial, no-content): gate let through a photo a person could not judge
- **route-006** (factor-only, fraud): band medium, expected high
- **route-008** (factor-only, fraud): band medium, expected high
- **route-009** (factor-only): decision verified, expected one of ['needs_review', 'more_evidence']; UNSAFE: auto-verified (score 18) where a person or more evidence was needed
- **route-011** (factor-only): decision verified, expected needs_review; UNSAFE: auto-verified (score 15) where a person or more evidence was needed
- **privacy-002** (blur_off): FAILED shared_has_no_gps
