"""Evidence verification pipeline. PROTOTYPE: every check below is a mock.

Five modules, kept separate so each could later be swapped for a real service:
  A. ingest      store the original file, SHA-256 hash, timestamp, basic metadata (this part is real)
  B. provenance  content credentials, metadata, duplicates, manipulation (SIMULATED)
  C. vision      brand, product, placement, context, quantity, clarity (SIMULATED)
  D. risk        0-100 score from weighted factors plus "must review" triggers (real arithmetic on simulated inputs)
  E. decide      low risk -> verified, medium -> more evidence or review, high -> human review

Nothing here calls an outside API. Real uploads always pass. The demo scenarios
("reused", "ai_signals", ...) exist only to show what the other outcomes look like.
AI findings never reject a host or move money on their own: people do that.
"""
import hashlib
import io
from datetime import datetime

from PIL import Image, ImageFilter
from PIL.ExifTags import TAGS

from . import db

SIMULATED = True

RISK_WEIGHTS = {  # how much each factor can add to the 0-100 score
    "synthetic": ("AI-generation signals", 25),
    "duplicate": ("Similarity to earlier photos", 25),
    "metadata": ("Metadata problems", 15),
    "context": ("Event or setting mismatch", 15),
    "placement": ("Placement not clearly shown", 15),
    "missing": ("Missing evidence", 5),
}
BANDS = [(20, "low"), (45, "medium"), (101, "high")]

# Demo scenarios. Each sets the simulated factor levels (0..1) and any must-review triggers.
SCENARIOS = {
    "authentic": {"label": "Authentic photo", "factors": {}, "triggers": []},
    "reused": {"label": "Reused photo", "factors": {"duplicate": 0.95, "context": 0.4},
               "triggers": ["Near-identical to a photo submitted for a different event"]},
    "ai_signals": {"label": "AI-generation signals", "factors": {"synthetic": 0.8, "metadata": 0.6},
                   "triggers": ["Possible AI-generated image: a person must check (this alone never rejects the host)"]},
    "insufficient": {"label": "Not enough evidence", "factors": {"placement": 0.85, "missing": 1.0}, "triggers": []},
    "needs_review": {"label": "Unclear, needs a person", "factors": {"placement": 0.8, "context": 0.7, "metadata": 0.5},
                     "triggers": []},
}
LEGACY = {"good": "authentic", "blurry": "insufficient", "wrong_brand": "insufficient"}

VIDEO_EXT = (".mp4", ".mov", ".m4v", ".webm")


def now():
    return datetime.now().isoformat(timespec="seconds")


def audit(actor, role, action, order_id=None, detail=""):
    db.insert("audit_log", ts=now(), actor=actor, role=role, action=action, order_id=order_id, detail=detail)


# ---------------------------------------------------------------- A. ingestion (real)
def ingest(order, files, uploader, capture_session=None, blur_faces=False):
    """files: list of (name, bytes, mime). Saves originals untouched and returns stored records."""
    folder = db.UPLOADS / str(order["id"])
    folder.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%H%M%S%f")[:-3]
    out = []
    for i, (name, data, mime) in enumerate(files, 1):
        is_video = (mime or "").startswith("video/") or name.lower().endswith(VIDEO_EXT)
        ext = (name.rsplit(".", 1)[-1].lower() if "." in name else ("mp4" if is_video else "jpg"))[:5]
        original = folder / f"{stamp}-{i}-original.{ext}"
        original.write_bytes(data)  # never overwritten: every submission gets new names
        rec = {"name": name, "kind": "video" if is_video else "photo", "mime": mime, "size": len(data),
               "sha256": hashlib.sha256(data).hexdigest(), "original": f"/uploads/{order['id']}/{original.name}",
               "shared": f"/uploads/{order['id']}/{original.name}", "exif": {}, "blurred": False,
               "uploaded_by": uploader, "uploaded_at": now(), "capture_session": capture_session}
        if not is_video:
            try:
                im = Image.open(io.BytesIO(data))
                rec["exif"] = {TAGS.get(k, str(k)): str(v)[:80] for k, v in (im.getexif() or {}).items()
                               if TAGS.get(k) in ("Make", "Model", "DateTime", "Software")}
                rec["dimensions"] = f"{im.width}x{im.height}"
                if blur_faces:
                    # Prototype face blur: softens the upper part of the frame, where faces usually are.
                    # The original is kept for reviewers; sponsors see this shared copy.
                    rgb = im.convert("RGB")
                    top = rgb.crop((0, 0, rgb.width, int(rgb.height * 0.45))).filter(ImageFilter.GaussianBlur(14))
                    rgb.paste(top, (0, 0))
                    shared = folder / f"{stamp}-{i}-shared.jpg"
                    rgb.save(shared, quality=85)  # re-saving also drops location metadata
                    rec["shared"] = f"/uploads/{order['id']}/{shared.name}"
                    rec["blurred"] = True
            except Exception:
                rec["exif"] = {}
        out.append(rec)
    return out


# ---------------------------------------------------------------- B. provenance (simulated)
def provenance(files, scenario):
    f = SCENARIOS[scenario]["factors"]
    photos = [x for x in files if x["kind"] == "photo"]
    has_exif = any(x["exif"] for x in photos)
    findings = [
        ("provenance", "hash", "info", f"SHA-256 recorded for {len(files)} file(s)", False),
        ("provenance", "c2pa", "info", "No Content Credentials found. Common for phone photos, not a problem on its own.", True),
        ("provenance", "exif", "warn" if f.get("metadata", 0) > 0.5 else "info",
         ("Camera time does not match the event date" if f.get("metadata", 0) > 0.5 else
          "Metadata present and consistent with the event" if has_exif else "No camera metadata. Not a problem on its own."), True),
        ("provenance", "duplicate", "high" if f.get("duplicate", 0) > 0.8 else "ok",
         ("96% match with a photo submitted for Late noodle night on a different date" if f.get("duplicate", 0) > 0.8
          else "No match with earlier submissions"), True),
        ("provenance", "synthetic", "warn" if f.get("synthetic", 0) > 0.5 else "ok",
         ("Patterns typical of AI-generated images detected (model confidence 0.78)" if f.get("synthetic", 0) > 0.5
          else "No AI-generation signals"), True),
        ("provenance", "editing", "ok", "No signs of compositing or heavy editing", True),
    ]
    if any(x["kind"] == "video" for x in files):
        findings.append(("provenance", "video", "info", "Video stored and hashed. Frames not analyzed in this prototype.", True))
    return findings


# ---------------------------------------------------------------- C. visual verification (simulated)
def vision(files, slot, sponsor, event, scenario):
    f = SCENARIOS[scenario]["factors"]
    weak = f.get("placement", 0) > 0.5
    ctx = f.get("context", 0) > 0.35
    return [
        ("vision", "brand", "warn" if weak else "ok",
         f"{sponsor['name']} {'only partly visible' if weak else 'clearly visible'}", True),
        ("vision", "placement", "warn" if weak else "ok",
         f"{slot['title']} {'not clearly shown' if weak else 'shown as agreed'}", True),
        ("vision", "context", "warn" if ctx else "ok",
         "Setting does not clearly match the event venue" if ctx else f"Setting consistent with {event['title']}", True),
        ("vision", "quantity", "warn" if f.get("missing") else "ok",
         f"Fewer than the {slot['photos_required']} photo(s) the agreement asks for" if f.get("missing")
         else "Quantity consistent with the agreement", True),
        ("vision", "clarity", "warn" if weak else "ok", "Photo too dark or blurry to judge" if weak else "Clear enough to judge", True),
    ]


# ---------------------------------------------------------------- D. risk scoring
def risk(scenario, files, slot):
    f = dict(SCENARIOS[scenario]["factors"])
    if len([x for x in files if x["kind"] == "photo"]) + len([x for x in files if x["kind"] == "video"]) < slot["photos_required"] \
            and scenario == "authentic":
        f["missing"] = 0.0  # prototype: real uploads always pass
    parts = []
    score = 0.0
    for key, (label, w) in RISK_WEIGHTS.items():
        v = f.get(key, 0.0)
        pts = round(v * w, 1)
        score += pts
        parts.append({"key": key, "label": label, "weight": w, "points": pts})
    score = round(min(100, score + (3 if scenario == "authentic" else 0)))
    band = next(b for limit, b in BANDS if score < limit)
    triggers = SCENARIOS[scenario]["triggers"]
    if triggers:  # serious findings force a human review whatever the weighted total says
        band = "high"
        if score < 70:
            parts.append({"key": "trigger", "label": "Must-review rule", "weight": 0, "points": 70 - score})
            score = 70
    return score, band, parts, triggers


# ---------------------------------------------------------------- E. decision
def decide(band, scenario):
    """Returns (decision, order status, explanation). Never rejects or pays out on its own."""
    if scenario == "insufficient":
        return "more_evidence", "in_escrow", "The placement is not clearly shown. Please add clearer photos of it."
    if band == "low":
        return "verified", "ready_for_payout", "Low risk and every requirement met. Verified automatically."
    if band == "medium":
        return "needs_review", "under_review", "Medium risk. A reviewer will look before anything is paid."
    return "needs_review", "under_review", "High risk. A reviewer must check this before anything is paid."


# ---------------------------------------------------------------- the whole pipeline
def run(order, files, scenario, uploader, note="", links=None, checkins=None, capture_session=None, blur_faces=False):
    scenario = LEGACY.get(scenario, scenario) or "authentic"
    if scenario not in SCENARIOS:
        scenario = "authentic"
    slot = db.one("SELECT * FROM slots WHERE id=?", (order["slot_id"],))
    event = db.one("SELECT * FROM events WHERE id=?", (slot["event_id"],))
    sponsor = db.one("SELECT * FROM sponsors WHERE id=?", (order["sponsor_id"],))
    stored = ingest(order, files, uploader, capture_session, blur_faces)
    findings = provenance(stored, scenario) + vision(stored, slot, sponsor, event, scenario)
    score, band, parts, triggers = risk(scenario, stored, slot)
    decision, status, explanation = decide(band, scenario)
    # placeholder cost per checked file, so the fee page still shows what checks would cost
    cost = round(len(stored) * float(db.get_settings()["ai_cost_per_photo"]), 4)
    checks = [{"label": f"{f[3]}{' (simulated)' if f[4] else ''}", "ok": f[2] in ("ok", "info")} for f in findings]
    if links:
        checks.append({"label": f"{len(links)} social post link(s) submitted as extra proof", "ok": True})
    if checkins is not None:
        checks.append({"label": f"{checkins} of {event['guests']} expected guests checked in", "ok": checkins >= event["guests"] * 0.5})
    pid = db.insert("proofs", order_id=order["id"], created=now(), mode="simulated",
                    decision={"verified": "verified", "more_evidence": "rejected"}.get(decision, "needs_review"),
                    confidence=round(1 - score / 100, 2), checks=checks, notes=explanation,
                    photos=[x["shared"] for x in stored if x["kind"] == "photo"], ai_cost=cost, reviewer_note="",
                    links=links or [], checkins=checkins, risk_score=score, risk_band=band, scenario=scenario,
                    host_note=note, triggers=triggers, risk_parts=parts)
    for x in stored:
        db.insert("evidence_files", proof_id=pid, order_id=order["id"], deal_id=order.get("deal_id"),
                  event_id=event["id"], kind=x["kind"], name=x["name"], mime=x["mime"], size=x["size"],
                  sha256=x["sha256"], original=x["original"], shared=x["shared"], exif=x["exif"],
                  blurred=1 if x["blurred"] else 0, uploaded_by=uploader, uploaded_at=x["uploaded_at"],
                  capture_session=capture_session)
    for comp, code, sev, detail, sim in findings:
        db.insert("findings", proof_id=pid, component=comp, code=code, severity=sev, detail=detail, simulated=1 if sim else 0)
    db.update("orders", order["id"], status=status, note=explanation)
    if cost:
        db.insert("ledger", order_id=order["id"], ts=now(), kind="ai_check", amount=cost,
                  note=f"Simulated check on {len(stored)} file(s)")
    audit(uploader, "host", "evidence_submitted", order["id"],
          f"{len(stored)} file(s), risk {score} ({band}), outcome: {decision}" + (", faces blurred" if blur_faces else ""))
    return decision


def sample_files(slot, sponsor_name, scenario, n=1):
    """Placeholder images for the demo buttons, drawn in code. Clearly not real photos."""
    from . import verify
    base = {"insufficient": "blurry", "ai_signals": "good", "reused": "good", "needs_review": "good"}.get(scenario, "good")
    return [(f"sample-{scenario}-{i + 1}.png", verify.sample_image(base, slot["type"], sponsor_name, "Other Co"), "image/png")
            for i in range(max(1, n))]
