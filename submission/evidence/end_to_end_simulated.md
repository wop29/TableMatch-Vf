# End-to-end run (simulated proof check)

Brief: "Specialty coffee brand looking for creative, design-minded dinners in Williamsburg, budget $700, menu mention"

| # | Step | Request | HTTP | ms | Result |
| --- | --- | --- | --- | --- | --- |
| 1 | Reset the demo database | `POST /api/reset` | 200 | 395 | `"ok"` |
| 2 | Brand search from a free-text brief | `POST /api/search/events` | 200 | 23 | `{"parsed": {"vibes": ["creative"], "audiences": [], "interests": ["design"], "places": ["Williamsburg"], "budget": 700.0, "slot_types": ["menu"]}, "top3": [["Smoke and stone fruit", 100], ["The long summer table", 50], ["Test kitchen: fermentation", 50]], "hidden": {"filters": 0, "budget": 1, "categ` |
| 3 | Host-side check: brands ranked for that dinner | `POST /api/search/sponsors` | 200 | 8 | `{"top3": [["Sunbrew", 87], ["Glowlab", 70], ["Copperhollow", 65]], "package": [{"sponsor": "Sunbrew", "slot": "Table sponsor", "price": 1000.0}, {"sponsor": "Glowlab", "slot": "Welcome drink", "price": 900.0}]}` |
| 4 | Brand buys the menu slot | `POST /api/slots/1/buy` | 200 | 7 | `{"order": 8, "price": 300.0, "status": "awaiting_payment"}` |
| 5 | Brand pays into escrow | `POST /api/orders/8/pay` | 200 | 6 | `{"status": "in_escrow"}` |
| 6 | Host uploads a real photo of the menu card (g01.jpg) | `POST /api/orders/8/proof` | 200 | 27 | `{"status": "ready_for_payout", "mode": "simulated", "risk": [3, "low"], "decision": "verified", "note": "Low risk and every requirement met. Verified automatically.", "file_sha256": "ed1ff66bd592b8a9"}` |
| 7 | Sponsor confirms the placement | `POST /api/orders/8/signoff` | 200 | 7 | `{"signoff": "confirmed"}` |
| 8 | Platform previews the payout | `GET /api/orders/8/payout-preview` | 200 | 2 | `{"fee": 90.0, "net": 210.0, "rate": 0.3, "cap": 3000.0}` |
| 9 | Platform releases the payout | `POST /api/orders/8/release` | 200 | 11 | `{"status": "released", "fee": 90.0, "net": 210.0}` |
| 10 | Second deal: Spicewell buys a menu slot | `POST /api/slots/17/buy` | 200 | 13 | `{"order": 9, "price": 250.0}` |
| 11 | Second deal: pays into escrow | `POST /api/orders/9/pay` | 200 | 6 | `{"status": "in_escrow"}` |
| 12 | Second deal: host uploads a photo with no logo (g04.jpg) | `POST /api/orders/9/proof` | 200 | 21 | `{"status": "ready_for_payout", "mode": "simulated", "decision": "verified", "note": "Low risk and every requirement met. Verified automatically."}` |
| 13 | Audit trail | `GET /api/audit` | 200 | 2 | `["Theo Lin (Midnight Noodle Society): evidence_submitted", "Sponsor: paid_into_escrow", "Platform: payout_released", "Sponsor: signoff_confirm", "Maya Okafor (Fig & Ember): evidence_submitted", "Sponsor: paid_into_escrow", "Theo Lin (Midnight Noodle Society): evidence_submitted", "Kofi Mensah (Dawn ` |
