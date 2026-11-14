# Tablematch — Deliverable 1: Working prototype

**Claim.** Tablematch runs end to end on real inputs. A brand types a free-text brief, the app searches a
catalog of New York dinners, the brand buys a placement and pays into escrow, the host uploads a real JPEG
photo as proof, the proof is checked and routed, the sponsor signs off, and the platform releases the payout
minus its fee. Every step runs through the same HTTP API the web app uses, and every step is logged.

| Item | Where |
| --- | --- |
| Live app | https://tablematch-prototype.onrender.com (free hosting: the first request after a quiet period takes about one minute to wake the server) |
| Source code | https://github.com/wop29/TableMatch-Vf |
| End-to-end script | https://github.com/wop29/TableMatch-Vf/blob/main/submission/run_end_to_end.py |
| Recorded run | https://github.com/wop29/TableMatch-Vf/blob/main/submission/evidence/end_to_end_simulated.json |
| Tests | https://github.com/wop29/TableMatch-Vf/tree/main/tests (39 tests, all passing) |

---

## 1. What the product does

Tablematch is a two-sided sponsorship marketplace for supper clubs and independent events in New York
(dinners, swap meets, artist talks, listening parties, run clubs, workshops).

| Side | What they do in the app |
| --- | --- |
| **Brand (sponsor)** | Describes the audience it wants in plain English, filters by borough, vibe, audience, format and date, sees ranked events with the reasons for each rank, buys single placements or multi-placement packages, pays into escrow, signs off or disputes the proof |
| **Host** | Lists an event with slots and prices, sees brands ranked for that event and a suggested funding package, uploads proof photos or video, gets paid per verified placement |
| **Platform** | Holds the money in escrow, checks proof, routes unclear cases to a reviewer, releases payouts, keeps a 30% fee capped at \$3,000 per transaction, keeps an audit log |

Placement types a brand can buy: menu mention, table sponsor (cards and product at each setting), screen and
logo display, welcome drink, take-home gift, presenting sponsor.

## 2. Architecture

| Layer | Technology | Files |
| --- | --- | --- |
| Web app | Vanilla JavaScript single-page app, self-hosted fonts | `static/index.html`, `static/app.js`, `static/style.css` |
| API | FastAPI (Python) | `app/main.py` (44 endpoints) |
| Matching | Rule-based ranking in both directions | `app/matching.py` |
| Money | Fee, cap, escrow state machine | `app/payments.py` |
| Evidence | Upload, hashing, metadata, face blur, risk scoring, routing | `app/evidence.py` |
| AI step | Visual placement check with a knowledge source in context | `app/vision.py`, `app/knowledge.py`, `knowledge/placement_guidelines.md` |
| Data | SQLite, seeded with 14 events, 8 brands, 11 host clubs | `app/db.py`, `app/seed.py` |
| Hosting | Render web service from `render.yaml` | `render.yaml` |

## 3. End-to-end run on real inputs (recorded)

The script `submission/run_end_to_end.py` starts the real application, resets the demo data and drives two
deals through the HTTP endpoints. Inputs are real: a typed brief, the app's own event catalog, and two JPEG
photographs uploaded as multipart form data. The table is the recorded output of that run.

**Brief typed by the brand:** "Specialty coffee brand looking for creative, design-minded dinners in
Williamsburg, budget \$700, menu mention"

| # | Step | Request | HTTP | Time | Result |
| --- | --- | --- | --- | --- | --- |
| 1 | Reset demo data | `POST /api/reset` | 200 | 377 ms | 14 events and 8 brands loaded |
| 2 | Brand searches with the brief | `POST /api/search/events` | 200 | 28 ms | Brief read as: vibe "creative", interest "design", place "Williamsburg", budget \$700, placement "menu". Top 3: Smoke and stone fruit (score 100), The long summer table (50), Test kitchen: fermentation (50). 1 event hidden for being over budget |
| 3 | Host-side view of the top dinner | `POST /api/search/sponsors` | 200 | 8 ms | Brands ranked: Sunbrew (87), Glowlab (70), Copperhollow (65). Suggested package: Sunbrew table sponsor \$1,000 + Glowlab welcome drink \$900 |
| 4 | Brand buys the menu slot | `POST /api/slots/1/buy` | 200 | 6 ms | Order 8 created, \$300, awaiting payment |
| 5 | Brand pays | `POST /api/orders/8/pay` | 200 | 6 ms | Status: in escrow |
| 6 | Host uploads a JPEG photo of the menu card | `POST /api/orders/8/proof` | 200 | 26 ms | Original stored untouched, SHA-256 `ed1ff66bd592b8a9...` recorded, risk score 3 (low), verified, ready for payout |
| 7 | Sponsor confirms the placement | `POST /api/orders/8/signoff` | 200 | 7 ms | Sign-off: confirmed |
| 8 | Platform previews the payout | `GET /api/orders/8/payout-preview` | 200 | 2 ms | Fee \$90 (30%), host receives \$210, cap \$3,000 not reached |
| 9 | Platform releases the payout | `POST /api/orders/8/release` | 200 | 7 ms | Status: released; ledger shows fee \$90 and transfer \$210 |
| 10 | Second deal: Spicewell buys a menu slot at Late noodle night | `POST /api/slots/17/buy` | 200 | 7 ms | Order 9, \$250 |
| 11 | Second deal: pays | `POST /api/orders/9/pay` | 200 | 5 ms | In escrow |
| 12 | Host uploads a photo with **no logo** in it | `POST /api/orders/9/proof` | 200 | 20 ms | In simulated mode: verified (see section 5) |
| 13 | Audit trail | `GET /api/audit` | 200 | 2 ms | Newest entries: evidence submitted, paid into escrow, payout released, sponsor sign-off confirmed |

The two uploaded photos are real photographs of dinners (the app's own cover images) with a printed menu card
added to the first. They are in the repository at `evals/golden/images/g01.jpg` and `g04.jpg`.

## 4. Verify it yourself

### Option A: the live app, in a browser (no setup)

1. Open https://tablematch-prototype.onrender.com and wait up to a minute if the server is waking.
2. Choose the **Sponsor** role. In **Find events**, type a brief such as "late night foodies in Bushwick, budget \$600" and search. Each result shows why it ranks where it does.
3. Open an event, reserve a slot, then pay for it in **My deals**. The money is now held in escrow.
4. Switch to the **Host** role. In **Evidence**, upload any photo as proof for that placement.
5. Switch back to **Sponsor**, open **My deals** and press **Confirm placement**.
6. Switch to the **Platform** role. In **Payouts**, release the transfer and see the 30% fee deducted. **Verification** shows the review queue.
7. Use **Reset demo data** at the bottom of the page to restore the starting data.

### Option B: the live API, from a terminal or an agent

```bash
BASE=https://tablematch-prototype.onrender.com
curl -s -X POST $BASE/api/reset
curl -s $BASE/api/meta | head -c 400                    # brands, settings, fee rules
curl -s -X POST $BASE/api/search/events -H 'Content-Type: application/json' \
  -d '{"query":"creative design dinners in Williamsburg, budget $700, menu mention"}'
curl -s "$BASE/api/fee-preview?price=1200"               # 30% fee, $3,000 cap
```

### Option C: run everything locally

```bash
git clone https://github.com/wop29/TableMatch-Vf && cd TableMatch-Vf
pip install -r requirements.txt pytest httpx
python -m pytest -q                       # expect: 39 passed
python submission/run_end_to_end.py       # records the run above
python run.py                             # web app at http://localhost:8000
```

## 5. What is real and what is simulated

| Part | Status | Detail |
| --- | --- | --- |
| Brief reading, search, filters, ranking, explanations | Real | Rule-based; every score shows its factor breakdown |
| Packages, bundle discounts, category exclusivity, sponsor limits per event | Real | |
| Fee (30%), cap (\$3,000), escrow states, refunds | Real arithmetic and state machine | No real money moves: there is no Stripe connection |
| Photo and video upload, SHA-256 hash, original kept, camera metadata, optional face blur | Real | Originals are never overwritten |
| Review queue, sponsor sign-off and disputes, payout release, audit log | Real | |
| AI placement check | Real when an Anthropic API key is set on the server; simulated otherwise | `app/vision.py`. Without a key, real uploads are treated as passing, which is why step 12 above is verified. With a key, step 12 must be routed to "more evidence" because no logo is visible |
| AI-image detector, search across all past photos for re-use | Simulated | Shown with "(simulated)" labels in the interface |

## 6. Test evidence

| Test file | Tests | What it proves |
| --- | --- | --- |
| `tests/test_flow.py` | 29 | Fee and cap; brand-side and host-side search; buy, pay, proof, review, sign-off, dispute, payout, refund; packages and bundle pricing; capacity and category rules; evidence storage and hashing |
| `tests/test_vision.py` | 5 | The knowledge source is looked up by placement type; routing rules in order; the prompt carries the guideline; images are resized before sending; cost is computed from tokens; an API failure goes to a person; a full upload through the AI step routes a wrong-brand photo to review, never to rejection |
| `tests/test_evals.py` | 5 | The eval graders themselves |

Result on the submitted code: **39 passed**.

## 7. Known limits

- Payments are simulated; a Stripe Connect integration is designed (fees modelled in Deliverable 5) but not built.
- The live demo uses one shared database; anyone can reset it.
- Free hosting sleeps after inactivity; the first request takes about a minute.
- The live server does not have an API key, so the live AI check runs in simulated mode.
