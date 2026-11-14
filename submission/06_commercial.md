# Tablematch — Deliverable 6: Commercial

**Claim.** Tablematch has a clear paying customer (consumer brands that want to reach young New Yorkers at
small, trusted events), a simple revenue model (a 30% fee on each placement, capped at \$3,000, collected
through escrow), positive unit economics at the expected deal size (\$310 contribution on a \$1,200 deal),
break-even at about 40 transactions a month, and a pilot plan that tests the three assumptions the business
depends on: deal size, repeat purchase and take rate. All figures are estimates from the team's model unless
a source is named.

| Item | Where |
| --- | --- |
| Live product | https://tablematch-prototype.onrender.com |
| Business unit economics report | https://github.com/wop29/TableMatch-Vf/blob/main/submission/evidence/Tablematch_Unit_Economics_and_Business_Model.md |
| Board deck (PowerPoint) | https://github.com/wop29/TableMatch-Vf/blob/main/submission/evidence/Tablematch_Board_Deck.pptx |

---

## 1. The problem and who pays

| Side | Who | Their problem today | What Tablematch gives them | Pays? |
| --- | --- | --- | --- | --- |
| **Brand** | Consumer brands targeting New Yorkers in their 20s and 30s: coffee, snacks, drinks, spirits, skincare, fintech, pet | Small, high-trust events (supper clubs, swap meets, artist talks, run clubs) reach exactly the right people, but they are hard to find, hard to book at \$250 to \$3,000 a placement, and hard to verify. Agencies are too expensive at that size | Search by audience, neighborhood, vibe and budget; fixed prices; packages; money held in escrow until proof is verified | **Yes** |
| **Host** | Supper clubs and independent event organizers | Events often run at a loss; sponsorship is ad hoc, slow and unpaid until long after | Listed slots, brands ranked for each event, a suggested funding package, guaranteed payment once proof is accepted | Pays the fee out of the payout in the current design |

## 2. Revenue model

| Element | How it works |
| --- | --- |
| Transaction fee | 30% of the placement price |
| Cap | \$3,000 per transaction; a package of several placements is one transaction with one capped fee |
| Escrow | The brand pays up front; the host is paid per verified placement; the fee is deducted at payout |
| Packages | Multi-placement bundles with a discount, to raise deal size |

### Pricing options to test in the pilot

| Option | How it works | On a \$1,200 deal | Trade-off |
| --- | --- | --- | --- |
| Current | Host pays 30% | Brand pays \$1,200; host gets \$840; platform \$360 | Simple for brands; steep for small hosts |
| Split fee | 15% from the brand + 15% from the host | Brand pays \$1,380; host gets \$1,020; platform \$360 | Same revenue, stronger host offer; common in marketplaces |
| Lower host rate | 20% from the host, packages pushed | Platform \$240 | Needs deals about 50% larger to earn the same |
| Add-ons (later) | Faster payouts, premium proof reports, brand subscriptions | Not modelled | Test only after repeat purchase is shown |

No usable public benchmark for sponsorship-marketplace take rates was found, so the 30% rate is a hypothesis.

## 3. Unit economics per transaction

| Per transaction | Conservative | **Base** | Optimistic |
| --- | --- | --- | --- |
| Average deal value | \$700 | **\$1,200** | \$2,000 |
| Placements per transaction | 1.3 | **1.8** | 2.4 |
| Platform fee | \$210.00 | **\$360.00** | \$600.00 |
| Variable cost | \$56.88 | **\$49.57** | \$43.81 |
| Contribution profit | \$153.12 | **\$310.43** | \$556.19 |
| Contribution margin (of the fee) | 73% | **86%** | 93% |
| Brand acquisition cost per transaction | \$333.33 | **\$60.00** | \$15.00 |
| Contribution after acquisition | -\$180 | **\$250** | \$541 |

Variable cost in the base case: payment fees \$29.04, people (ops, support, payout approval, proof review)
\$19.18, refund losses \$0.92, AI and evidence technology \$0.43.

Acquisition assumptions (hypotheses): \$2,000 / \$1,000 / \$600 to win a brand; 1.5 / 2.5 / 4 transactions per
brand a month; 75% / 85% / 90% monthly retention.

## 4. Monthly economics and break-even

| Per month | Conservative | **Base** | Optimistic |
| --- | --- | --- | --- |
| Transactions | 15 | **60** | 200 |
| Fixed cost (technology, team, sales and marketing, legal, detector plan) | \$7,779 | **\$12,249** | \$22,999 |
| Operating profit | -\$5,482 | **\$6,377** | \$88,238 |
| Break-even transactions | 51 | **40** | 42 |
| Break-even after acquisition cost | never | **49** | 43 |

The conservative case loses money on every brand once acquisition is counted: a \$700 deal cannot pay back a
\$2,000 acquisition cost within four months. The business works only if deals are larger, or brands are
cheaper to win and stay longer.

## 5. How the fee cap changes the take

| Deal value | Placements | Fee | Effective take | Variable cost | Contribution |
| --- | --- | --- | --- | --- | --- |
| \$300 | 1 | \$90 | 30% | \$27 | \$63 |
| \$600 | 1 | \$180 | 30% | \$34 | \$146 |
| \$1,200 | 1.8 | \$360 | 30% | \$50 | \$310 |
| \$3,000 | 2.5 | \$900 | 30% | \$91 | \$809 |
| \$6,000 | 3 | \$1,800 | 30% | \$157 | \$1,643 |
| \$10,000 | 3.5 | \$3,000 | 30% | \$245 | \$2,755 |
| \$12,000 | 4 | \$3,000 | 25% | \$292 | \$2,708 |
| \$20,000 | 4 | \$3,000 | 15% | \$477 | \$2,523 |
| \$40,000 | 4 | \$3,000 | 8% | \$939 | \$2,061 |

Up to \$10,000 the platform keeps 30%; above it the fee stays at \$3,000 while card fees keep growing, so a
\$20,000 deal earns less than a \$10,000 one. Large deals should pay by bank transfer.

## 6. What drives the result (sensitivity)

Change in monthly operating profit (base case, 60 transactions) when each driver moves 25% down or up:

| Driver | Driver -25% | Driver +25% |
| --- | --- | --- |
| Take rate | -\$5,427 | +\$5,427 |
| Average transaction value | -\$5,011 | +\$5,011 |
| Share paid by card | +\$282 | -\$282 |
| Ops and support minutes | +\$219 | -\$219 |
| Share of placements sent to a person | +\$18 | -\$18 |
| Vision model price | +\$4 | -\$4 |
| Photos per placement | +\$2 | -\$2 |

Take rate and deal size dominate; AI model price and photos per placement barely register.

## 7. Six ways to cut cost

| Lever | What changes | Saves per transaction (alone) | Variable cost after it (cumulative) |
| --- | --- | --- | --- |
| ACH or invoice for deals over \$2,000 | Brand pays by bank transfer; card stays for small deals | \$7.83 | \$41.75 |
| Auto-release low-risk payouts | Verified, low-risk placements pay out after sponsor sign-off without a person | \$2.23 | \$39.51 |
| AI support drafts | Model drafts replies and onboarding answers; ops reviews | \$4.38 | \$35.14 |
| Guided in-app capture | Shot checklist and live framing cut unclear submissions | \$0.42 | \$34.72 |
| Optimized proof pipeline | Resize, sample video, cache, batch, small-model screening | \$0.18 | \$34.56 |
| Fewer refunds | Deposit and clearer slot specs before purchase | \$0.35 | \$34.33 |

Together: variable cost \$49.57 -> \$34.33 per transaction; contribution \$310.43 -> \$325.67.

## 8. Go to market

| Phase | What | Target |
| --- | --- | --- |
| 1. Supply | Recruit hosts already running events in Williamsburg and Bushwick | 10 to 15 hosts, 2 events each a month |
| 2. Demand | Founder-led outreach to brands whose audience matches those events | 10 brands |
| 3. Deal size | Lead with multi-placement packages, not single menu mentions | Average deal toward \$1,200 |
| 4. Trust | Sell proof as the product: verified photos, an audit trail and escrow | Sponsor disputes under 3% |
| 5. Expand | Add neighborhoods only once each has enough events to give brands a choice | |

## 9. What the pilot must prove

| Assumption | Why it matters | Pilot measure | Threshold to continue |
| --- | --- | --- | --- |
| Average deal near \$1,200 | Below about \$700 the conservative case loses money after acquisition | Mean transaction value; share of package deals | At least \$900 |
| Brands come back | Acquisition cost pays back only with repeat purchase | Share of brands buying again within 60 days | At least 40% |
| The take rate is accepted | Revenue moves one-for-one with it | Which pricing option hosts and brands accept | Hosts accept 30% or the split fee |
| Proof is trusted | Escrow only works if brands trust verification | Sponsor disputes; reviewer overturn rate | Disputes under 3% |

The thresholds are the team's proposals for the pilot, not results.

## 10. Risks

| Risk | Why | Mitigation |
| --- | --- | --- |
| Liquidity | Too few events per neighborhood to give brands choice | Launch in two neighborhoods; recruit hosts first |
| Take rate | No benchmark; 30% may be high for small hosts | Test the split fee |
| Deal size | If most deals are \$250 menu mentions, volume must be much higher | Packages and bundle discounts |
| Fraud in proof | Reused or generated photos | Hashing, AI placement check, a person on every flagged case, escrow |
| Seasonality | Events cluster in spring and autumn | Brand subscriptions planned once repeat purchase is shown |
