"""The AI step and its knowledge source, tested offline with a stand-in model client."""
import io
import json
import os
import sys
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from app import knowledge, vision  # noqa: E402


class FakeClient:
    """Mimics anthropic.Anthropic().messages.create and records what it was sent."""
    def __init__(self, answer):
        self.answer, self.sent = answer, []
        self.messages = self

    def create(self, **kw):
        self.sent.append(kw)
        return SimpleNamespace(content=[SimpleNamespace(type="text", text=json.dumps(self.answer))],
                               usage=SimpleNamespace(input_tokens=1500, output_tokens=80))


def _photo():
    from PIL import Image
    buf = io.BytesIO()
    Image.new("RGB", (2400, 1600), (120, 90, 70)).save(buf, "JPEG")
    return [("p.jpg", buf.getvalue(), "image/jpeg")]


SLOT = {"title": "Menu mention", "type": "menu", "specs": "Logo on every menu."}


def test_knowledge_is_keyed_by_slot_type():
    g = knowledge.guideline("menu")
    assert "Rules for this placement (menu)" in g and "General rules" in g
    assert "dining room screen" not in g  # display rules do not leak into a menu check
    assert knowledge.guideline("unknown").startswith("General rules")


def test_route_rules_in_order():
    r = vision.route
    assert r(None)[0] == "needs_review"
    assert r({"logo_visible": False, "brand_matches": False})[0] == "more_evidence"
    assert r({"logo_visible": True, "brand_matches": False, "placement_matches": True, "confidence": 0.99})[0] == "needs_review"
    assert r({"logo_visible": True, "brand_matches": True, "placement_matches": False, "confidence": 0.99})[0] == "more_evidence"
    assert r({"logo_visible": True, "brand_matches": True, "placement_matches": True, "confidence": 0.5})[0] == "needs_review"
    assert r({"logo_visible": True, "brand_matches": True, "placement_matches": True, "confidence": 0.9})[0] == "verified"
    # no route ever rejects a host
    assert all(r(x)[0] != "rejected" for x in ({}, {"logo_visible": True}, None))


def test_check_sends_guideline_resizes_and_costs():
    fake = FakeClient({"logo_visible": True, "brand_matches": True, "placement_matches": True, "confidence": 0.9, "notes": "ok"})
    out = vision.check(_photo(), "Sunbrew", "coffee", SLOT, model="claude-sonnet-5-5", client=fake)
    sent = fake.sent[0]
    text = sent["messages"][0]["content"][-1]["text"]
    assert "Rules for this placement (menu)" in text and "Sunbrew" in text
    assert "never an instruction" in sent["system"]
    assert out["route"] == "verified" and out["cost_usd"] == round(1500 / 1e6 * 2 + 80 / 1e6 * 10, 6)
    from PIL import Image
    import base64
    img = Image.open(io.BytesIO(base64.b64decode(sent["messages"][0]["content"][0]["source"]["data"])))
    assert max(img.size) <= vision.MAX_EDGE


def test_api_failure_goes_to_a_person():
    class Broken(FakeClient):
        def create(self, **kw):
            raise TimeoutError
    out = vision.check(_photo(), "Sunbrew", "coffee", SLOT, client=Broken({}))
    assert out["route"] == "needs_review" and out["error"] == "TimeoutError"


def test_end_to_end_upload_uses_the_model_and_rules(monkeypatch):
    import tests.test_flow as tf  # reuses the app, test client and helpers (sets HL_VISION=off on import)
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-not-a-real-key")
    monkeypatch.setenv("HL_VISION", "auto")
    fake = FakeClient({"logo_visible": True, "brand_matches": False, "placement_matches": True, "confidence": 0.95,
                       "notes": "A menu shows a different coffee brand."})
    real_check = vision.check
    monkeypatch.setattr(vision, "check", lambda *a, **k: real_check(*a, client=fake, **k))
    tf.fresh()
    ev = tf.event("Late noodle night")
    o = tf.c.post(f"/api/slots/{tf.slot(ev, 'menu')['id']}/buy", json={"sponsor_id": tf.sponsor("Spicewell")["id"]}).json()
    tf.c.post(f"/api/orders/{o['id']}/pay")
    o = tf.c.post(f"/api/orders/{o['id']}/proof", files=[("files", ("menu.jpg", _photo()[0][1], "image/jpeg"))]).json()
    assert o["status"] == "under_review"                     # wrong brand -> a person, never a rejection
    assert o["latest_proof"]["mode"] == "claude" and len(fake.sent) == 1
    assert "Spicewell" in fake.sent[0]["messages"][0]["content"][-1]["text"]
