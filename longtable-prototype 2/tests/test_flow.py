"""End-to-end checks of the whole deal flow. Run:  python -m pytest -q   (or: python tests/test_flow.py)"""
import os
import sys
import tempfile
from pathlib import Path

tmp = tempfile.mkdtemp()
os.environ["HL_DB"] = str(Path(tmp) / "t.db")
os.environ["HL_UPLOADS"] = str(Path(tmp) / "up")
os.environ["HL_VERIFY"] = "demo"
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from fastapi.testclient import TestClient  # noqa: E402

from app import payments  # noqa: E402
from app.main import app  # noqa: E402

c = TestClient(app)
c.__enter__()


def fresh():
    assert c.post("/api/reset").status_code == 200


def sponsor(name):
    return next(s for s in c.get("/api/meta").json()["sponsors"] if s["name"] == name)


def event(title):
    return next(e for e in c.get("/api/events").json() if e["title"] == title)


def slot(ev, kind):
    return next(s for s in ev["slots"] if s["type"] == kind and s["status"] == "open")


# --- fee rules ---------------------------------------------------------------------------------
def test_fee_is_30_percent_and_capped():
    assert payments.compute_fee(300, 0.30, 3000) == (90.0, 210.0, False)
    assert payments.compute_fee(10000, 0.30, 3000) == (3000.0, 7000.0, False)   # 30% is exactly the cap
    fee, net, capped = payments.compute_fee(12000, 0.30, 3000)
    assert (fee, net, capped) == (3000.0, 9000.0, True)


def test_fee_settings_change_the_preview():
    fresh()
    assert c.get("/api/fee-preview", params={"price": 1000}).json()["fee"] == 300
    c.put("/api/settings", json={"fee_rate": 0.2, "fee_cap": 100})
    assert c.get("/api/fee-preview", params={"price": 1000}).json()["fee"] == 100
    assert c.put("/api/settings", json={"fee_rate": 1.5}).status_code == 400
    fresh()


# --- matching ----------------------------------------------------------------------------------
def test_sponsor_prompt_finds_brooklyn_hip_dinners_first():
    fresh()
    r = c.post("/api/search/events", json={"query": "a hip, trendy Brooklyn crowd of creatives"}).json()
    assert r["parsed"]["vibes"] == ["hip", "trendy"] and r["parsed"]["audiences"] == ["creatives"]
    assert "Williamsburg" in r["parsed"]["places"]
    top = r["results"][0]
    assert top["score"] >= 80 and top["event"]["borough"] == "Brooklyn"
    assert all(x["event"]["neighborhood"] != "Harlem" or x["score"] < top["score"] for x in r["results"])


def test_budget_filters_out_dinners_with_nothing_affordable():
    fresh()
    r = c.post("/api/search/events", json={"query": "foodies in Queens", "budget": 100}).json()
    assert r["results"] == []


def test_host_search_ranks_sponsors_and_sizes_a_package():
    fresh()
    ev = event("Smoke and stone fruit")
    r = c.post("/api/search/sponsors", json={"event_id": ev["id"], "guests": 24, "funding_needed": 3200,
                                              "notes": "we like coffee brands"}).json()
    names = [x["sponsor"]["name"] for x in r["results"]]
    assert names[0] in ("Sunbrew", "Leafline", "Tidewell")
    assert names.index("Sunbrew") < names.index("Pawlette")
    assert r["package"]["needed"] == 3200 and r["package"]["covered"] > 0


# --- full deal: buy, pay, verify, payout --------------------------------------------------------
def test_buy_verify_and_payout_with_fee_deducted():
    fresh()
    ev = event("Founders table: the bridge dinner")
    title = slot(ev, "title")
    cop = sponsor("Copperhollow")
    o = c.post(f"/api/slots/{title['id']}/buy", json={"sponsor_id": cop["id"]}).json()
    assert o["status"] == "awaiting_payment" and o["price"] == 12000
    # slot is gone for everyone else
    assert c.post(f"/api/slots/{title['id']}/buy", json={"sponsor_id": sponsor('Glowlab')["id"]}).status_code == 409
    # cannot upload photos or release before paying
    assert c.post(f"/api/orders/{o['id']}/proof", data={"scenario": "good"}).status_code == 409
    o = c.post(f"/api/orders/{o['id']}/pay").json()
    assert o["status"] == "in_escrow" and o["fee"] == 3000 and o["net"] == 9000
    # funds cannot be released until the placement is verified
    assert c.post(f"/api/orders/{o['id']}/release", json={"confirm": True}).status_code == 409
    o = c.post(f"/api/orders/{o['id']}/proof", data={"scenario": "good"}).json()
    assert o["status"] == "ready_for_payout"
    assert len(o["latest_proof"]["photos"]) == 3                       # the title slot needs 3 photos
    assert abs(o["latest_proof"]["ai_cost"] - 3 * 0.02) < 1e-9        # cost scales with photos, not price
    pv = c.get(f"/api/orders/{o['id']}/payout-preview").json()
    assert pv["net"] == 9000 and pv["capped"] is True
    assert c.post(f"/api/orders/{o['id']}/release", json={"confirm": False}).status_code == 400
    o = c.post(f"/api/orders/{o['id']}/release", json={"confirm": True}).json()
    assert o["status"] == "released" and o["net"] == 9000
    ov = c.get("/api/overview").json()
    assert ov["fees_earned"] >= 3000


def test_cost_of_checks_is_the_same_for_a_small_and_a_large_slot():
    fresh()
    small = slot(event("Late noodle night"), "menu")
    big = slot(event("Founders table: the bridge dinner"), "table")
    assert small["photos_required"] == big["photos_required"] == 1
    costs = []
    for s, name in ((small, "Spicewell"), (big, "Copperhollow")):
        o = c.post(f"/api/slots/{s['id']}/buy", json={"sponsor_id": sponsor(name)["id"]}).json()
        c.post(f"/api/orders/{o['id']}/pay")
        o = c.post(f"/api/orders/{o['id']}/proof", data={"scenario": "good"}).json()
        costs.append(o["latest_proof"]["ai_cost"])
    assert costs[0] == costs[1]


def test_bad_photos_are_rejected_and_funds_stay_held():
    fresh()
    ev = event("Late noodle night")
    o = c.post(f"/api/slots/{slot(ev, 'menu')['id']}/buy", json={"sponsor_id": sponsor("Spicewell")["id"]}).json()
    c.post(f"/api/orders/{o['id']}/pay")
    for scenario in ("blurry", "wrong_brand"):
        o = c.post(f"/api/orders/{o['id']}/proof", data={"scenario": scenario}).json()
        assert o["status"] == "in_escrow" and o["latest_proof"]["decision"] == "rejected"
    assert c.post(f"/api/orders/{o['id']}/release", json={"confirm": True}).status_code == 409


def test_real_upload_in_demo_mode_goes_to_human_review():
    fresh()
    import io

    from PIL import Image, ImageDraw
    img = Image.new("RGB", (1000, 700), (200, 190, 180))
    d = ImageDraw.Draw(img)
    for i in range(0, 1000, 25):
        d.line([(i, 0), (1000 - i, 700)], fill=(30, 30, 30), width=3)
    buf = io.BytesIO()
    img.save(buf, "JPEG")
    ev = event("Late noodle night")
    o = c.post(f"/api/slots/{slot(ev, 'menu')['id']}/buy", json={"sponsor_id": sponsor("Spicewell")["id"]}).json()
    c.post(f"/api/orders/{o['id']}/pay")
    o = c.post(f"/api/orders/{o['id']}/proof", files=[("files", ("table.jpg", buf.getvalue(), "image/jpeg"))]).json()
    assert o["status"] == "under_review"
    o = c.post(f"/api/orders/{o['id']}/review", json={"decision": "approve", "note": "Logo visible"}).json()
    assert o["status"] == "ready_for_payout"
    assert c.post("/api/orders/%d/proof" % o["id"], data={"scenario": "good"}).status_code == 409


def test_not_enough_photos_is_rejected():
    fresh()
    ev = event("Smoke and stone fruit")
    drink = slot(ev, "drink")                          # needs 2 photos
    import io

    from PIL import Image
    buf = io.BytesIO()
    Image.new("RGB", (900, 600), (90, 90, 90)).save(buf, "JPEG")
    o = c.post(f"/api/slots/{drink['id']}/buy", json={"sponsor_id": sponsor("Tidewell")["id"]}).json()
    c.post(f"/api/orders/{o['id']}/pay")
    o = c.post(f"/api/orders/{o['id']}/proof", files=[("files", ("a.jpg", buf.getvalue(), "image/jpeg"))]).json()
    assert o["latest_proof"]["decision"] == "rejected" and o["status"] == "in_escrow"


# --- bids and proposals ---------------------------------------------------------------------------
def test_bid_accept_creates_order_and_declines_other_bids():
    fresh()
    ev = event("Smoke and stone fruit")
    table = slot(ev, "table")
    b1 = c.post(f"/api/slots/{table['id']}/bids", json={"sponsor_id": sponsor("Tidewell")["id"], "amount": 700}).json()
    b2 = c.post(f"/api/slots/{table['id']}/bids", json={"sponsor_id": sponsor("Leafline")["id"], "amount": 900}).json()
    o = c.post(f"/api/offers/{b2['id']}/decision", json={"decision": "accept"}).json()
    assert o["price"] == 900 and o["source"] == "bid" and o["status"] == "awaiting_payment"
    offers = {x["id"]: x["status"] for x in c.get("/api/offers").json()}
    assert offers[b1["id"]] == "declined" and offers[b2["id"]] == "accepted"
    assert c.post(f"/api/offers/{b2['id']}/decision", json={"decision": "accept"}).status_code == 409


def test_host_proposal_accept_and_refund_reopens_slot():
    fresh()
    ev = event("Late noodle night")
    disp = slot(ev, "display")
    p = c.post("/api/proposals", json={"slot_id": disp["id"], "sponsor_id": sponsor("Pocketpal")["id"], "amount": 450}).json()
    o = c.post(f"/api/offers/{p['id']}/decision", json={"decision": "accept"}).json()
    assert o["source"] == "proposal" and o["price"] == 450
    c.post(f"/api/orders/{o['id']}/pay")
    o = c.post(f"/api/orders/{o['id']}/refund").json()
    assert o["status"] == "refunded"
    assert any(s["id"] == disp["id"] and s["status"] == "open" for s in event("Late noodle night")["slots"])


def test_host_can_create_dinner_and_slot():
    fresh()
    club = c.get("/api/meta").json()["clubs"][0]
    e = c.post(f"/api/clubs/{club['id']}/events", json={"title": "New dinner", "date": "2026-12-20", "guests": 18,
                                                          "funding_needed": 1500}).json()
    s = c.post(f"/api/events/{e['id']}/slots", json={"type": "menu", "price": 275}).json()
    assert s["title"] == "Menu mention" and s["status"] == "open"
    assert c.patch(f"/api/slots/{s['id']}", json={"price": 300}).json()["price"] == 300
    assert c.delete(f"/api/slots/{s['id']}").json()["ok"]


def test_feedback_is_saved_and_survives_a_reset():
    fresh()
    assert c.post("/api/feedback", json={"rating": 4, "message": "Clear, but I missed the bid button", "role": "sponsor"}).json()["ok"]
    assert c.post("/api/feedback", json={"rating": 9}).status_code == 400
    fresh()
    assert c.get("/api/feedback").json()[0]["rating"] == 4


def test_host_can_add_a_cover_photo():
    fresh()
    import io

    from PIL import Image
    buf = io.BytesIO()
    Image.new("RGB", (2400, 1600), (180, 120, 90)).save(buf, "PNG")
    ev = event("Late noodle night")
    assert ev["cover"] is None
    r = c.post(f"/api/events/{ev['id']}/cover", files={"file": ("table.png", buf.getvalue(), "image/png")})
    assert r.status_code == 200 and r.json()["cover"].startswith("/uploads/covers/")
    assert c.get(r.json()["cover"]).status_code == 200
    assert c.post(f"/api/events/{ev['id']}/cover", files={"file": ("x.txt", b"nope", "text/plain")}).status_code == 400


if __name__ == "__main__":
    import pytest
    sys.exit(pytest.main([__file__, "-q"]))
