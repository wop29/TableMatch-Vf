# Longtable prototype

A local, two-sided marketplace prototype for sponsoring supper clubs and small dinners. Everything runs on your computer. No GitHub, no accounts, no internet needed for the core demo.

## Run it

You need Python 3.9 or newer.

```bash
cd hyperlocal-marketplace
pip install -r requirements.txt
python run.py
```

Then open http://127.0.0.1:8000 (it also opens automatically). Stop it with Ctrl+C.
The first start creates `data/marketplace.db` and fills it with fictional demo data. Use "Reset demo data" in the footer to start over.

## What it does (from the planning meeting)

- **Sponsor side.** Describe who you want to reach ("a hip, trendy Brooklyn crowd") with an optional budget and slot type. Dinners are ranked with reasons. Open a dinner, pick a slot, then **Buy now** or **Place a bid**.
- **Host side.** Add dinners (guests, funding needed), list slots (menu, table, screen and logo, welcome drink, gift, presenting sponsor) with specs, price and photos required. **Find sponsors** takes guests and funding for one dinner and ranks sponsors, then lets you send an offer. The **Inbox** handles bids, proof photos and payout status.
- **Matching works both ways** over a curated fictional list of 8 sponsors, 6 supper clubs and 9 dinners. Nothing is searched on the internet. Edit `app/seed.py` to change the data.
- **Payments (simulated).** Sponsor pays the platform, money is held in escrow, and the host is paid only after verification. Fee is 30% capped at $3,000 per transaction, deducted at transfer, with a confirmation screen showing the net amount. Change the numbers on the Platform > Fees tab.
- **Verification is a separate step.** The host uploads photos. Checks: photo count, size, focus, then the logo and placement. Verified photos unlock payout, unclear ones go to the platform review queue, failed ones go back to the host. Cost is per photo, not per deal size.
- **Platform side.** Overview of escrow, fees and payouts, review queue, payouts, fee settings.

## Try this walk-through

1. Sponsor, acting as Sunbrew: search "hip trendy Brooklyn creatives", open *Smoke and stone fruit*, buy the menu mention.
2. Host, acting as Fig & Ember: see your sold slot in Inbox. Use "Clear photo" (sample) to submit proof.
3. Platform, Payouts: review the transfer, check the fee and net, confirm.
4. Try "Founders table" title slot ($12,000) to see the fee cap: fee $3,000, host receives $9,000.

## Made for testers

- A welcome screen asks which side you want to try. "How this works" in the footer reopens it.
- **Display** (top bar) sets text size and reduces animation. The app is always in bright mode.
- **Give feedback** (footer) saves a 1 to 5 rating and a comment. The Platform > Overview tab lists them under "Feedback from testers". Feedback survives "Reset demo data".
- On phones the section tabs sit in a bottom bar, and the dinner page keeps Buy slot and Place bid pinned at the bottom.
- Destructive actions ask first (decline, cancel, refund) or offer Undo (remove a slot).

## Demo limits

- Money is simulated. No real payment provider is connected.
- Without an API key, the verifier checks size and focus for real but **cannot read logos**. The three sample photo buttons simulate the brand check, and your own uploads go to the review queue.
- To let AI read photos, set `ANTHROPIC_API_KEY` before `python run.py`. This path is written but has not been run against the live API. Optional: `HL_VERIFY_MODEL` to pick the model, `HL_VERIFY=demo` to force demo mode.
- There are no logins. Use the "Acting as" menu to switch people.
- The Google Fonts link in `static/index.html` needs internet. Offline, system fonts are used.
- Longtable is a working name, not trademark-checked. Fee, cap and per-photo cost are placeholders.

## Layout

```
run.py            start the server
app/main.py       API and routes
app/matching.py   both matching directions
app/payments.py   fee and escrow rules
app/verify.py     photo verification, demo and AI
app/seed.py       fictional demo data
static/           the front end (HTML, CSS, JS)
tests/            python -m pytest -q
```

Backend and front end are separate: the front end only talks to `/api/...`, so a team can swap either side and merge later.

## Put it online (Render)

1. Put this folder in your own GitHub repo.
2. On render.com choose New, then Blueprint, and pick the repo. `render.yaml` fills in the build and start commands.
3. Wait for the build. You get a public link. The free plan sleeps when idle and resets the demo data on restart.
