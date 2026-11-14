"""End-to-end checks of the whole deal flow. Run:  python -m pytest -q   (or: python tests/test_flow.py)"""
import os
import sys
import tempfile
from pathlib import Path

tmp = tempfile.mkdtemp()
os.environ["HL_DB"] = str(Path(tmp) / "t.db")
os.environ["HL_UPLOADS"] = str(Path(tmp) / "up")
os.environ["HL_VERIFY"] = "demo"
os.environ["HL_VISION"] = "off"  # keep these flow tests offline even when an API key is set
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


def test_real_upload_always_passes_in_the_prototype():
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
    assert o["status"] == "ready_for_payout" and o["latest_proof"]["risk_band"] == "low"
    assert o["files"][0]["sha256"] and len(o["files"][0]["sha256"]) == 64
    assert c.post("/api/orders/%d/proof" % o["id"], data={"scenario": "good"}).status_code == 409


def test_video_and_too_few_photos_still_pass_in_the_prototype():
    fresh()
    ev = event("Smoke and stone fruit")
    drink = slot(ev, "drink")                          # needs 2 photos
    import io

    from PIL import Image
    buf = io.BytesIO()
    Image.new("RGB", (900, 600), (90, 90, 90)).save(buf, "JPEG")
    o = c.post(f"/api/slots/{drink['id']}/buy", json={"sponsor_id": sponsor("Tidewell")["id"]}).json()
    c.post(f"/api/orders/{o['id']}/pay")
    o = c.post(f"/api/orders/{o['id']}/proof", files=[("files", ("a.jpg", buf.getvalue(), "image/jpeg")),
                                                      ("files", ("clip.mp4", b"\x00\x00fake-video", "video/mp4"))]).json()
    assert o["status"] == "ready_for_payout"
    assert {f["kind"] for f in o["files"]} == {"photo", "video"}


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
    assert ev["cover"] == "/static/covers/late-noodle-night.jpg"
    r = c.post(f"/api/events/{ev['id']}/cover", files={"file": ("table.png", buf.getvalue(), "image/png")})
    assert r.status_code == 200 and r.json()["cover"].startswith("/uploads/covers/")
    assert c.get(r.json()["cover"]).status_code == 200
    assert c.post(f"/api/events/{ev['id']}/cover", files={"file": ("x.txt", b"nope", "text/plain")}).status_code == 400


if __name__ == "__main__":
    import pytest
    sys.exit(pytest.main([__file__, "-q"]))


def test_seeded_dinners_have_bundled_covers():
    fresh()
    evs = c.get("/api/events").json()
    assert all(e["cover"] and e["cover"].startswith("/static/covers/") for e in evs if e["kind"] == "dinner")
    assert c.get(next(e for e in evs if e["cover"])["cover"]).status_code == 200


# --- action plan: filters, explained scores, funding, exclusivity, capacity, dashboard ---------
def test_hard_filters_remove_dinners_and_scores_are_explained():
    fresh()
    r = c.post("/api/search/events", json={"query": "creatives", "filters": {"borough": "Queens"}}).json()
    assert r["results"] and all(x["event"]["borough"] == "Queens" for x in r["results"])
    assert r["hidden"]["filters"] > 0
    b = r["results"][0]["breakdown"]
    assert [x["weight"] for x in b] == [30, 20, 15, 15, 10, 10]
    r = c.post("/api/search/events", json={"query": "", "filters": {"format": "banquet"}}).json()
    assert [x["event"]["title"] for x in r["results"]] == ["Founders table: the bridge dinner"]


def test_funding_calculator_and_profile_update():
    fresh()
    ev = event("Green plates, no phones")
    f = ev["funding"]
    assert f["ticket_revenue"] == 20 * 75 and f["gap"] == 2000 and f["remaining"] == 2000
    assert f["recommended"]
    ev = c.patch(f"/api/events/{ev['id']}", json={"ticket_price": 100, "total_cost": 3500}).json()
    assert ev["funding"]["gap"] == 1500 and ev["funding_needed"] == 1500
    assert c.patch(f"/api/events/{ev['id']}", json={"preferred_cats": ["snacks"], "excluded_cats": ["snacks"]}).status_code == 400


def test_category_exclusivity_and_excluded_categories():
    fresh()
    ev = event("Late noodle night")  # Tidewell (soft drinks) already sponsors it
    table = slot(ev, "table")
    leaf = sponsor("Leafline")  # snacks, a different category: allowed
    tidewell_rival = sponsor("Tidewell")
    assert c.post(f"/api/slots/{table['id']}/buy", json={"sponsor_id": tidewell_rival["id"]}).status_code == 200  # same sponsor may add slots
    fresh()
    ev = event("Sunday supper with the quartet")  # excludes finance apps
    menu = slot(ev, "menu")
    r = c.post(f"/api/slots/{menu['id']}/buy", json={"sponsor_id": sponsor("Pocketpal")["id"]})
    assert r.status_code == 409 and "does not take" in r.json()["detail"]
    assert c.post(f"/api/slots/{menu['id']}/buy", json={"sponsor_id": leaf["id"]}).status_code == 200


def test_one_brand_per_category_and_sponsor_capacity():
    fresh()
    ev = event("Test kitchen: fermentation")  # capacity 2
    c.post(f"/api/slots/{slot(ev, 'menu')['id']}/buy", json={"sponsor_id": sponsor("Sunbrew")["id"]})
    ev = event("Test kitchen: fermentation")
    assert "coffee" in ev["density"]["taken_cats"]
    c.post(f"/api/slots/{slot(ev, 'table')['id']}/buy", json={"sponsor_id": sponsor("Spicewell")["id"]})
    ev = event("Test kitchen: fermentation")
    assert ev["density"]["at_capacity"]
    r = c.post(f"/api/slots/{slot(ev, 'gift')['id']}/buy", json={"sponsor_id": sponsor("Glowlab")["id"]})
    assert r.status_code == 409 and "limit" in r.json()["detail"]
    found = c.post("/api/search/events", json={"query": "", "sponsor_id": sponsor("Glowlab")["id"]}).json()
    assert ev["id"] not in [x["event"]["id"] for x in found["results"]]


def test_host_matching_breakdown_and_dashboard():
    fresh()
    ev = event("Smoke and stone fruit")
    r = c.post("/api/search/sponsors", json={"event_id": ev["id"], "guests": 24, "funding_needed": 3200}).json()
    assert [x["weight"] for x in r["results"][0]["breakdown"]] == [25, 20, 25, 15, 10, 5]
    assert "Pocketpal" not in [x["sponsor"]["name"] for x in r["results"]]  # finance apps excluded here
    perf = c.get("/api/overview").json()["performance"]
    assert perf["searches"] >= 1 and perf["deals"] >= 2 and perf["events"] == 14


# --- event types, extra proof and sponsor sign-off --------------------------------------------
def test_event_types_and_interest_counts():
    fresh()
    r = c.post("/api/search/events", json={"query": "", "filters": {"kind": "swap"}}).json()
    assert [x["event"]["title"] for x in r["results"]] == ["The Ex Files: swap out your ex's stuff"]
    assert r["results"][0]["event"]["interested"] == 640
    r = c.post("/api/search/events", json={"query": "creatives on the lower east side"}).json()
    assert "Lower East Side" in r["parsed"]["places"]  # Psychic Telephone itself is sold out in the demo data


def test_proof_links_checkins_and_sponsor_signoff():
    fresh()
    tide = next(o for o in c.get("/api/orders").json() if o["sponsor"]["name"] == "Tidewell")
    bad = c.post(f"/api/orders/{tide['id']}/proof", data={"scenario": "good", "links": "not a link"})
    assert bad.status_code == 400
    o = c.post(f"/api/orders/{tide['id']}/proof",
               data={"scenario": "good", "links": "https://example.com/p/1\nhttps://example.com/p/2", "checkins": "28"}).json()
    assert o["status"] == "ready_for_payout"
    labels = [x["label"] for x in o["latest_proof"]["checks"]]
    assert any("2 social post link" in l for l in labels) and any("28 of 32" in l for l in labels)
    o = c.post(f"/api/orders/{tide['id']}/signoff", json={"decision": "dispute", "note": "Name missing"}).json()
    assert o["status"] == "under_review" and o["signoff"] == "disputed"
    o = c.post(f"/api/orders/{tide['id']}/review", json={"decision": "approve"}).json()
    assert o["status"] == "ready_for_payout"
    assert c.post(f"/api/orders/{tide['id']}/signoff", json={"decision": "confirm"}).json()["signoff"] == "confirmed"


# --- packages and multi-placement deals ------------------------------------------------------
def test_predefined_package_one_payment_separate_fulfilment():
    fresh()
    ev = event("Founders table: the bridge dinner")
    pk = next(p for p in ev["packages"] if p["tier"] == "presenting")
    assert pk["available"] and pk["discount"] == round(pk["list_total"] * 0.15, 2)
    sun = sponsor("Sunbrew")["id"]
    d = c.post("/api/deals", json={"event_id": ev["id"], "slot_ids": pk["slot_ids"], "package_id": pk["id"], "sponsor_id": sun}).json()
    assert d["price"] == pk["price"] and d["total"] == len(pk["slot_ids"]) and d["awaiting"]
    assert abs(sum(o["price"] for o in d["orders"]) - d["price"]) < 0.05
    # placements in a package cannot be paid one by one
    assert c.post(f"/api/orders/{d['orders'][0]['id']}/pay").status_code == 409
    d = c.post(f"/api/deals/{d['id']}/pay").json()
    assert all(o["status"] == "in_escrow" for o in d["orders"])
    # each placement is verified on its own
    first = d["orders"][0]["id"]
    c.post(f"/api/orders/{first}/proof", data={"scenario": "good"})
    d = c.get(f"/api/deals?sponsor_id={sun}").json()[0]
    assert d["verified"] == 1 and d["total"] == len(pk["slot_ids"])
    # the package is no longer offered once its slots are sold
    assert not next(p for p in event("Founders table: the bridge dinner")["packages"] if p["id"] == pk["id"])["available"]


def test_custom_builder_bundle_discount_and_conflicts():
    fresh()
    ev = event("The Ex Files: swap out your ex's stuff")
    ids = [x["id"] for x in ev["slots"] if x["type"] in ("menu", "gift", "display")]
    q = c.post("/api/quote", json={"event_id": ev["id"], "slot_ids": ids}).json()
    assert q["discount_pct"] == 5 and q["price"] == round(q["list_total"] * 0.95, 2)
    q2 = c.post("/api/quote", json={"event_id": ev["id"], "slot_ids": ids[:2]}).json()
    assert q2["discount"] == 0
    c.put(f"/api/events/{ev['id']}/bundle", json={"bundle_discount_pct": 12, "bundle_min": 2})
    assert c.post("/api/quote", json={"event_id": ev["id"], "slot_ids": ids[:2]}).json()["discount_pct"] == 12
    d = c.post("/api/deals", json={"event_id": ev["id"], "slot_ids": ids, "sponsor_id": sponsor("Leafline")["id"]}).json()
    assert d["name"] == "Custom package"
    r = c.post("/api/deals", json={"event_id": ev["id"], "slot_ids": ids[:1], "sponsor_id": sponsor("Glowlab")["id"]})
    assert r.status_code == 409
    c.post(f"/api/deals/{d['id']}/cancel")
    assert all(s["status"] == "open" for s in event("The Ex Files: swap out your ex's stuff")["slots"] if s["id"] in ids)


def test_host_creates_edits_and_deletes_packages():
    fresh()
    ev = event("Bridge run and bagels")
    ids = [x["id"] for x in ev["slots"]][:2]
    pks = c.post(f"/api/events/{ev['id']}/packages", json={"name": "Finish line", "slot_ids": ids, "discount_pct": 8}).json()
    mine = next(p for p in pks if p["name"] == "Finish line")
    assert mine["discount_pct"] == 8
    assert c.post(f"/api/events/{ev['id']}/packages", json={"name": "Too big", "slot_ids": ids, "discount_pct": 80}).status_code == 400
    other = event("Late noodle night")["slots"][0]["id"]
    assert c.post(f"/api/events/{ev['id']}/packages", json={"name": "Mixed", "slot_ids": [ids[0], other]}).status_code == 400
    pks = c.put(f"/api/packages/{mine['id']}", json={"name": "Finish line plus", "slot_ids": ids, "discount_pct": 10}).json()
    assert any(p["name"] == "Finish line plus" for p in pks)
    pks = c.delete(f"/api/packages/{mine['id']}").json()
    assert not any(p["id"] == mine["id"] for p in pks)



# --- evidence verification (prototype, simulated) ---------------------------------------------
def test_six_seeded_verification_cases():
    fresh()
    orders = c.get("/api/orders").json()
    by = {o["latest_proof"]["scenario"]: o for o in orders if o["latest_proof"] and o["latest_proof"].get("scenario")}
    assert by["authentic"]["status"] in ("ready_for_payout", "released")
    assert by["reused"]["status"] == "under_review" and by["reused"]["latest_proof"]["risk_band"] == "high"
    assert by["reused"]["latest_proof"]["triggers"]  # duplicate forces review whatever the score
    assert by["ai_signals"]["status"] == "under_review"
    assert by["insufficient"]["status"] == "in_escrow"
    assert by["needs_review"]["status"] == "under_review" and by["needs_review"]["latest_proof"]["risk_band"] == "medium"
    assert any(o["status"] == "released" and o["latest_proof"] for o in orders)
    # a package keeps a status per placement
    pkg = [o for o in orders if o["deal_id"] and o["sponsor"]["name"] == "Copperhollow"]
    assert len({o["status"] for o in pkg}) >= 2


def test_reviewer_actions_need_reasons_and_are_audited():
    fresh()
    o = next(o for o in c.get("/api/orders?status=under_review").json() if o["latest_proof"]["scenario"] == "ai_signals")
    assert c.post(f"/api/orders/{o['id']}/review", json={"decision": "reject"}).status_code == 400
    r = c.post(f"/api/orders/{o['id']}/review", json={"decision": "flag_fraud", "note": "Looks generated"}).json()
    assert r["fraud_flag"] == 1 and r["status"] == "under_review"
    r = c.post(f"/api/orders/{o['id']}/review", json={"decision": "request_evidence", "note": "Send the original files"}).json()
    assert r["status"] == "in_escrow"
    ev = c.get(f"/api/orders/{o['id']}/evidence").json()
    actions = [a["action"] for a in ev["audit"]]
    assert "flag_fraud" in actions and "request_evidence" in actions and "evidence_submitted" in actions
    assert ev["submissions"][0]["findings"] and ev["submissions"][0]["files"][0]["original"]


def test_face_blur_keeps_original_and_capture_code_is_recorded():
    fresh()
    import io

    from PIL import Image
    buf = io.BytesIO()
    Image.new("RGB", (800, 600), (150, 120, 100)).save(buf, "JPEG")
    ev = event("Late noodle night")
    o = c.post(f"/api/slots/{slot(ev, 'menu')['id']}/buy", json={"sponsor_id": sponsor("Spicewell")["id"]}).json()
    c.post(f"/api/orders/{o['id']}/pay")
    code = c.post(f"/api/events/{ev['id']}/capture").json()["token"]
    c.post(f"/api/orders/{o['id']}/proof", files=[("files", ("p.jpg", buf.getvalue(), "image/jpeg"))],
           data={"blur_faces": "1", "capture": code, "note": "Menus on every seat"})
    f = c.get(f"/api/orders/{o['id']}/evidence").json()["submissions"][0]["files"][0]
    assert f["blurred"] == 1 and f["original"] != f["shared"] and f["capture_session"] == code
