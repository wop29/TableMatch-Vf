"""Placement verification: did the host really show the sponsor's logo or ad at the dinner?

Two modes:
  claude  Used when ANTHROPIC_API_KEY is set. Sends the photos to a Claude vision model and asks for a
          structured judgement. Cost scales with the number of photos, not with the size of the deal.
  demo    Used otherwise. Checks photo size and sharpness for real. It cannot read logos, so for your own
          uploads it sends the photo to human review. The three "sample photo" buttons simulate the
          brand check so the whole flow can be shown offline.

Decisions: verified (funds can be released), needs_review (a person on the platform checks),
rejected (host retakes the photos).
"""
import base64
import io
import json
import os
import re

from PIL import Image, ImageDraw, ImageFilter, ImageFont, ImageStat

MIN_W, MIN_H = 640, 400
MIN_SHARPNESS = 40.0  # variance of edge response on a 640px-wide copy; tuned on the demo samples


def mode():
    forced = os.environ.get("HL_VERIFY", "").lower()
    if forced in ("demo", "claude"):
        return forced
    return "claude" if os.environ.get("ANTHROPIC_API_KEY") else "demo"


def sharpness(img):
    g = img.convert("L")
    w, h = g.size
    if w > 640:
        g = g.resize((640, max(1, round(h * 640 / w))))
    return ImageStat.Stat(g.filter(ImageFilter.FIND_EDGES)).var[0]


def _quality(images):
    checks, ok = [], True
    for i, im in enumerate(images, 1):
        w, h = im.size
        big = w >= MIN_W and h >= MIN_H
        sharp = sharpness(im) >= MIN_SHARPNESS
        checks.append({"label": f"Photo {i} is large enough ({w} by {h})", "ok": big})
        checks.append({"label": f"Photo {i} is in focus", "ok": sharp})
        ok = ok and big and sharp
    return checks, ok


def verify(images, raw_files, slot, sponsor, event, settings, scenario=None):
    """images: PIL images, raw_files: (name, bytes, mime). Returns a result dict."""
    n = len(images)
    cost = round(n * settings["ai_cost_per_photo"], 4)
    need = slot["photos_required"]
    checks = [{"label": f"{n} of {need} required photo{'s' if need != 1 else ''} received", "ok": n >= need}]
    if n < need:
        return {"mode": mode(), "decision": "rejected", "confidence": 1.0, "checks": checks,
                "notes": f"This slot needs {need} photo{'s' if need != 1 else ''}. Add the missing ones and submit again.",
                "ai_cost": 0.0}

    if mode() == "claude" and not scenario:
        try:
            return _claude(raw_files, slot, sponsor, event, settings, cost, checks)
        except Exception as e:  # never block the flow on an API problem
            checks.append({"label": "AI check unavailable, sent to a person", "ok": False})
            return {"mode": "claude", "decision": "needs_review", "confidence": 0.0, "checks": checks,
                    "notes": f"The AI check failed ({type(e).__name__}). A reviewer will look at the photos.",
                    "ai_cost": 0.0}

    q_checks, q_ok = _quality(images)
    checks += q_checks
    if not q_ok:
        return {"mode": "demo", "decision": "rejected", "confidence": 0.9, "checks": checks,
                "notes": "At least one photo is too small or out of focus. Retake it with the placement in frame.",
                "ai_cost": cost}

    if scenario == "good":
        checks += [{"label": f"{sponsor['name']} logo visible (simulated)", "ok": True},
                   {"label": f"Placement matches '{slot['title']}' (simulated)", "ok": True}]
        return {"mode": "demo", "decision": "verified", "confidence": 0.93, "checks": checks,
                "notes": "Simulated result for a clear photo of the right placement.", "ai_cost": cost}
    if scenario == "wrong_brand":
        checks += [{"label": f"{sponsor['name']} logo visible (simulated)", "ok": False}]
        return {"mode": "demo", "decision": "rejected", "confidence": 0.91, "checks": checks,
                "notes": f"Simulated result: the photo shows a different brand, not {sponsor['name']}.", "ai_cost": cost}
    # Real upload in demo mode: quality passes but nothing can read the logo.
    checks.append({"label": "Logo match needs a person (demo mode cannot read logos)", "ok": False})
    return {"mode": "demo", "decision": "needs_review", "confidence": 0.5, "checks": checks,
            "notes": "Photo quality is fine. Add an API key to let AI check the logo, or approve it in the review queue.",
            "ai_cost": cost}


def _claude(raw_files, slot, sponsor, event, settings, cost, checks):
    import anthropic

    client = anthropic.Anthropic()
    content = []
    for name, data, mime in raw_files:
        content.append({"type": "image", "source": {"type": "base64", "media_type": mime,
                                                    "data": base64.b64encode(data).decode()}})
    content.append({"type": "text", "text": (
        f"A supper club host says they displayed the sponsor '{sponsor['name']}' ({sponsor['category']}) at a dinner. "
        f"The purchased placement is '{slot['title']}': {slot['specs']}\n"
        "Look at the photos and answer with JSON only, no other text:\n"
        '{"logo_visible": true|false, "brand_matches": true|false, "placement_matches": true|false, '
        '"confidence": 0.0-1.0, "notes": "one or two plain sentences"}')})
    msg = client.messages.create(model=os.environ.get("HL_VERIFY_MODEL", "claude-sonnet-5-5"),
                                 max_tokens=400, messages=[{"role": "user", "content": content}])
    text = "".join(b.text for b in msg.content if getattr(b, "type", "") == "text")
    data = json.loads(re.search(r"\{.*\}", text, re.S).group(0))
    conf = float(data.get("confidence", 0))
    checks += [{"label": f"{sponsor['name']} logo visible", "ok": bool(data.get("logo_visible"))},
               {"label": "Brand matches the sponsor", "ok": bool(data.get("brand_matches"))},
               {"label": f"Placement matches '{slot['title']}'", "ok": bool(data.get("placement_matches"))}]
    all_ok = all(bool(data.get(k)) for k in ("logo_visible", "brand_matches", "placement_matches"))
    if all_ok and conf >= settings["auto_verify_confidence"]:
        decision = "verified"
    elif not all_ok and conf >= settings["auto_verify_confidence"]:
        decision = "rejected"
    else:
        decision = "needs_review"
    return {"mode": "claude", "decision": decision, "confidence": conf, "checks": checks,
            "notes": data.get("notes", ""), "ai_cost": cost}


# --- sample photos for the demo buttons ---------------------------------------------------------
def _font(size):
    for p in ("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", "DejaVuSans-Bold.ttf",
              "/System/Library/Fonts/Supplemental/Arial Bold.ttf", "C:/Windows/Fonts/arialbd.ttf"):
        try:
            return ImageFont.truetype(p, size)
        except OSError:
            continue
    return ImageFont.load_default(size)


def sample_image(scenario, slot_type, brand, other_brand="Other Co"):
    """Draws a simple dinner-table scene so the demo has something to upload. Not a real photo."""
    W, H = 1200, 800
    img = Image.new("RGB", (W, H), (58, 43, 36))
    d = ImageDraw.Draw(img)
    d.rectangle([60, 330, W - 60, H - 40], fill=(232, 228, 216))
    for x in (260, 600, 940):
        d.ellipse([x - 120, 470, x + 120, 700], fill=(250, 250, 248), outline=(190, 190, 184), width=5)
        d.ellipse([x - 70, 510, x + 70, 660], outline=(215, 215, 210), width=3)
    label = other_brand if scenario == "wrong_brand" else brand
    f = _font(58)
    if slot_type == "display":
        d.rectangle([260, 40, 940, 300], fill=(14, 18, 22), outline=(80, 80, 80), width=8)
        d.text((600, 170), label, font=_font(76), fill=(255, 255, 255), anchor="mm")
    else:
        d.polygon([(430, 400), (770, 400), (740, 330), (460, 330)], fill=(255, 255, 255), outline=(150, 150, 150))
        d.rectangle([430, 400, 770, 450], fill=(244, 244, 240), outline=(150, 150, 150))
        d.text((600, 372), label, font=f, fill=(30, 30, 30), anchor="mm")
    if scenario == "blurry":
        img = img.filter(ImageFilter.GaussianBlur(22))
    buf = io.BytesIO()
    img.save(buf, "PNG")
    return buf.getvalue()
