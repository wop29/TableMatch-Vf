"""Runs one complete Tablematch deal on real inputs and records every step.

    python submission/run_end_to_end.py          # simulated proof checks (no key needed)
    ANTHROPIC_API_KEY=... python submission/run_end_to_end.py   # real AI placement check

Real inputs: a brand's free-text brief, the app's own catalog of NYC dinners, and real JPEG photos uploaded
through the same HTTP endpoints the web app uses (photos from evals/golden/images). Writes
submission/evidence/end_to_end_<mode>.json and .md.
"""
import json
import os
import sys
import tempfile
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
tmp = tempfile.mkdtemp()
os.environ.setdefault("HL_DB", str(Path(tmp) / "e2e.db"))
os.environ.setdefault("HL_UPLOADS", str(Path(tmp) / "up"))
os.environ["HL_VERIFY"] = "demo"

from fastapi.testclient import TestClient  # noqa: E402

from app import vision  # noqa: E402
from app.main import app  # noqa: E402

MODE = "ai" if vision.enabled() else "simulated"
c = TestClient(app)
c.__enter__()
steps = []


def step(name, method, path, show, **kw):
    t = time.perf_counter()
    r = getattr(c, method)(path, **kw)
    ms = round((time.perf_counter() - t) * 1000)
    body = r.json()
    steps.append({"step": len(steps) + 1, "name": name, "request": f"{method.upper()} {path}", "status": r.status_code,
                  "ms": ms, "result": show(body)})
    print(f"{len(steps):>2}. {name}: HTTP {r.status_code}, {ms} ms -> {json.dumps(show(body))[:160]}")
    assert r.status_code == 200, body
    return body


def photo(cid):
    p = ROOT / "evals" / "golden" / "images" / f"{cid}.jpg"
    return ("files", (f"{cid}.jpg", p.read_bytes(), "image/jpeg"))


step("Reset the demo database", "post", "/api/reset", lambda b: "ok")
sponsors = {s["name"]: s for s in c.get("/api/meta").json()["sponsors"]}
sun = sponsors["Sunbrew"]
brief = "Specialty coffee brand looking for creative, design-minded dinners in Williamsburg, budget $700, menu mention"
res = step("Brand search from a free-text brief", "post", "/api/search/events",
           lambda b: {"parsed": b["parsed"], "top3": [(r["event"]["title"], r["score"]) for r in b["results"][:3]], "hidden": b["hidden"]},
           json={"query": brief, "sponsor_id": sun["id"]})
ev = res["results"][0]["event"]
slot = next(s for s in ev["slots"] if s["type"] == "menu" and s["status"] == "open")
step("Host-side check: brands ranked for that dinner", "post", "/api/search/sponsors",
     lambda b: {"top3": [(r["sponsor"]["name"], r["score"]) for r in b["results"][:3]], "package": b["package"]["items"]},
     json={"event_id": ev["id"], "guests": ev["guests"], "funding_needed": 1500, "notes": "coffee would fit"})
o = step("Brand buys the menu slot", "post", f"/api/slots/{slot['id']}/buy",
         lambda b: {"order": b["id"], "price": b["price"], "status": b["status"]}, json={"sponsor_id": sun["id"]})
step("Brand pays into escrow", "post", f"/api/orders/{o['id']}/pay", lambda b: {"status": b["status"]})
o = step("Host uploads a real photo of the menu card (g01.jpg)", "post", f"/api/orders/{o['id']}/proof",
         lambda b: {"status": b["status"], "mode": b["latest_proof"]["mode"], "risk": [b["latest_proof"]["risk_score"], b["latest_proof"]["risk_band"]],
                    "decision": b["latest_proof"]["decision"], "note": b["latest_proof"]["notes"], "file_sha256": b["files"][0]["sha256"][:16]},
         files=[photo("g01")])
if o["status"] == "ready_for_payout":
    step("Sponsor confirms the placement", "post", f"/api/orders/{o['id']}/signoff", lambda b: {"signoff": b.get("signoff")},
         json={"decision": "confirm"})
    step("Platform previews the payout", "get", f"/api/orders/{o['id']}/payout-preview", lambda b: {k: b[k] for k in ("fee", "net", "rate", "cap")})
    step("Platform releases the payout", "post", f"/api/orders/{o['id']}/release", lambda b: {"status": b["status"], "fee": b["fee"], "net": b["net"]},
         json={"confirm": True})

# A second deal where the photo shows no logo at all (g04.jpg): with the AI on, it must not be auto-verified.
ev2 = next(e for e in c.get("/api/events").json() if e["title"] == "Late noodle night")
s2 = next(s for s in ev2["slots"] if s["type"] == "menu" and s["status"] == "open")
spw = sponsors["Spicewell"]
o2 = step("Second deal: Spicewell buys a menu slot", "post", f"/api/slots/{s2['id']}/buy", lambda b: {"order": b["id"], "price": b["price"]},
          json={"sponsor_id": spw["id"]})
step("Second deal: pays into escrow", "post", f"/api/orders/{o2['id']}/pay", lambda b: {"status": b["status"]})
step("Second deal: host uploads a photo with no logo (g04.jpg)", "post", f"/api/orders/{o2['id']}/proof",
     lambda b: {"status": b["status"], "mode": b["latest_proof"]["mode"], "decision": b["latest_proof"]["decision"], "note": b["latest_proof"]["notes"]},
     files=[photo("g04")])
step("Audit trail", "get", "/api/audit", lambda b: [f"{a['actor']}: {a['action']}" for a in (b if isinstance(b, list) else b.get("items", []))][:8])

out = ROOT / "submission" / "evidence"
json.dump({"mode": MODE, "brief": brief, "steps": steps}, open(out / f"end_to_end_{MODE}.json", "w"), indent=2)
L = [f"# End-to-end run ({MODE} proof check)", "", f"Brief: \"{brief}\"", "",
     "| # | Step | Request | HTTP | ms | Result |", "| --- | --- | --- | --- | --- | --- |"]
for s in steps:
    L.append(f"| {s['step']} | {s['name']} | `{s['request']}` | {s['status']} | {s['ms']} | `{json.dumps(s['result'])[:300]}` |")
(out / f"end_to_end_{MODE}.md").write_text("\n".join(L) + "\n")
print(f"Wrote submission/evidence/end_to_end_{MODE}.json and .md")
