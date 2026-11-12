"""Tablematch prototype API. Run with:  python run.py"""
import io
import re
from contextlib import asynccontextmanager
from datetime import datetime
from typing import List, Optional

from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from PIL import Image
from pydantic import BaseModel

from . import db, evidence, matching, payments, seed, verify

ROOT = db.ROOT


@asynccontextmanager
async def lifespan(_app):
    db.init()
    if not db.q("SELECT 1 FROM sponsors LIMIT 1") or str(db.get_settings().get("data_version")) not in (seed.DATA_VERSION, seed.DATA_VERSION + ".0"):
        seed.seed()  # demo data only: older demo databases are rebuilt with the new profile fields
    seed.backfill_covers()
    yield


app = FastAPI(title="Tablematch prototype", lifespan=lifespan)


def now():
    return datetime.now().isoformat(timespec="seconds")


# ------------------------------------------------------------------ views
def slot_view(s):
    return s


def event_view(ev, with_slots=True):
    club = db.one("SELECT * FROM clubs WHERE id=?", (ev["club_id"],))
    ev = dict(ev, club_name=club["name"], host_name=club["host_name"])
    slots = db.q("SELECT * FROM slots WHERE event_id=? ORDER BY price", (ev["id"],))
    st = db.get_settings()
    gross = net = fee = 0.0
    sponsor_ids, cats, placements = [], [], 0
    for s in slots:
        o = db.one("SELECT * FROM orders WHERE slot_id=? AND status NOT IN ('refunded') ORDER BY id DESC", (s["id"],))
        s["order_status"] = o["status"] if o else None
        if not o:
            continue
        placements += 1
        if o["sponsor_id"] not in sponsor_ids:
            sponsor_ids.append(o["sponsor_id"])
            sp = db.one("SELECT cat FROM sponsors WHERE id=?", (o["sponsor_id"],))
            if sp and sp["cat"]:
                cats.append(sp["cat"])
        if o["status"] in payments.HELD + ("released",):
            gross += o["price"]
            f, n, _ = payments.compute_fee(o["price"], st["fee_rate"], st["fee_cap"])
            fee += o["fee"] if o["fee"] is not None else f
            net += o["net"] if o["net"] is not None else n
    ev["funded"] = gross

    # funding calculator: cost minus ticket revenue is the gap sponsors are asked to close
    ticket_rev = (ev.get("ticket_price") or 0) * ev["guests"]
    total = ev.get("total_cost")
    gap = max(0.0, total - ticket_rev) if total is not None else (ev["funding_needed"] or 0)
    remaining = max(0.0, gap - net)
    cap = ev.get("max_sponsors") or 3
    room = max(0, cap - len(sponsor_ids))
    rec, acc = [], 0.0
    for s in sorted([x for x in slots if x["status"] == "open"], key=lambda x: -x["price"]):
        if acc >= remaining or len(rec) >= room:
            break
        rec.append({"id": s["id"], "title": s["title"], "price": s["price"]})
        acc += payments.compute_fee(s["price"], st["fee_rate"], st["fee_cap"])[1]
    ev["funding"] = {"total_cost": total, "ticket_price": ev.get("ticket_price"), "ticket_revenue": ticket_rev,
                     "gap": gap, "gross": gross, "fee": fee, "net": net, "remaining": remaining,
                     "pct": round(min(1.0, net / gap) * 100) if gap else 100,
                     "recommended": rec, "recommended_net": acc}

    # sponsorship density: how commercial does the evening feel?
    per10 = placements / max(ev["guests"], 1) * 10
    level = "None yet" if not placements else ("Heavy" if (len(sponsor_ids) > cap or per10 > 1.5) else
                                              "Balanced" if len(sponsor_ids) >= max(1, cap - 1) else "Light")
    ev["density"] = {"sponsor_ids": sponsor_ids, "sponsors": len(sponsor_ids), "placements": placements,
                     "max_sponsors": cap, "at_capacity": len(sponsor_ids) >= cap, "taken_cats": cats,
                     "per_10_guests": round(per10, 2), "level": level, "flag": level == "Heavy"}
    if with_slots:
        ev["slots"] = slots
        by_id = {x["id"]: x for x in slots}
        ev["packages"] = [package_view(p, by_id, ev) for p in
                          db.q("SELECT * FROM packages WHERE event_id=? AND active=1 ORDER BY id", (ev["id"],))]
    return ev


def _deadline(day):
    from datetime import date, timedelta
    try:
        return (date.fromisoformat(day) + timedelta(days=3)).isoformat()
    except ValueError:
        return day


def money_str(x):
    return f"${x:,.0f}"


def _preview(o):
    """Fee for one placement. Inside a package the cap applies to the whole deal, split by price."""
    st = db.get_settings()
    if not o.get("deal_id"):
        return payments.preview(o["price"], st)
    deal = db.one("SELECT * FROM deals WHERE id=?", (o["deal_id"],))
    d = payments.preview(deal["price"], st)
    share = o["price"] / deal["price"] if deal["price"] else 0
    fee = round(d["fee"] * share, 2)
    return dict(d, price=round(o["price"], 2), fee=fee, net=round(o["price"] - fee, 2), deal_price=deal["price"])


def deal_view(d):
    ev = event_view(get_or_404("events", d["event_id"]), with_slots=False)
    orders = [order_view(o) for o in db.q("SELECT * FROM orders WHERE deal_id=? ORDER BY id", (d["id"],))]
    pk = db.one("SELECT * FROM packages WHERE id=?", (d["package_id"],)) if d["package_id"] else None
    live = [o for o in orders if o["status"] != "refunded"]
    return dict(d, event=ev, orders=orders, package=pk,
                awaiting=all(o["status"] == "awaiting_payment" for o in live) and bool(live),
                verified=sum(1 for o in live if o["status"] in ("ready_for_payout", "released")),
                total=len(live))


def order_view(o):
    slot = db.one("SELECT * FROM slots WHERE id=?", (o["slot_id"],))
    ev = db.one("SELECT * FROM events WHERE id=?", (slot["event_id"],))
    club = db.one("SELECT * FROM clubs WHERE id=?", (ev["club_id"],))
    sp = db.one("SELECT * FROM sponsors WHERE id=?", (o["sponsor_id"],))
    proofs = db.q("SELECT * FROM proofs WHERE order_id=? ORDER BY id DESC", (o["id"],))
    s = db.get_settings()
    est = _preview(o)
    return dict(o, status_label=payments.STATUS_LABEL[o["status"]], slot=slot,
                event={k: ev[k] for k in ("id", "title", "date", "neighborhood", "borough", "guests", "cover", "kind")},
                club={"id": club["id"], "name": club["name"], "host_name": club["host_name"]},
                sponsor={"id": sp["id"], "name": sp["name"], "color": sp["color"]},
                proofs=proofs, latest_proof=proofs[0] if proofs else None,
                files=db.q("SELECT kind, shared, sha256, blurred, uploaded_at FROM evidence_files WHERE proof_id=?",
                           (proofs[0]["id"],)) if proofs else [],
                deadline=_deadline(ev["date"]),
                estimate=est)


def offer_view(of):
    slot = db.one("SELECT * FROM slots WHERE id=?", (of["slot_id"],))
    ev = db.one("SELECT * FROM events WHERE id=?", (slot["event_id"],))
    club = db.one("SELECT * FROM clubs WHERE id=?", (ev["club_id"],))
    sp = db.one("SELECT * FROM sponsors WHERE id=?", (of["sponsor_id"],))
    return dict(of, slot=slot, event={"id": ev["id"], "title": ev["title"], "date": ev["date"]},
                club={"id": club["id"], "name": club["name"]},
                sponsor={"id": sp["id"], "name": sp["name"], "color": sp["color"]})


def get_or_404(table, id_):
    row = db.one(f"SELECT * FROM {table} WHERE id=?", (id_,))
    if not row:
        raise HTTPException(404, f"{table[:-1]} {id_} not found")
    return row


def ledger(order_id, kind, amount, note):
    db.insert("ledger", order_id=order_id, ts=now(), kind=kind, amount=amount, note=note)


# ------------------------------------------------------------------ read
@app.get("/api/meta")
def meta():
    return {"sponsors": db.q("SELECT * FROM sponsors ORDER BY name"),
            "clubs": db.q("SELECT * FROM clubs ORDER BY name"),
            "settings": db.get_settings(), "verify_mode": verify.mode(),
            "slot_types": {k: v[0] for k, v in seed.SLOT_TYPES.items()},
            "scenarios": {k: v["label"] for k, v in evidence.SCENARIOS.items()},
            "risk_weights": evidence.RISK_WEIGHTS, "categories": seed.CATEGORIES, "formats": seed.FORMATS, "kinds": seed.KINDS, "interests": seed.INTERESTS,
            "age_groups": seed.AGE_GROUPS, "vibes": list(matching.VIBES), "audiences": list(matching.AUDIENCES),
            "weights": matching.WEIGHTS}


@app.get("/api/events")
def list_events(club_id: Optional[int] = None):
    rows = db.q("SELECT * FROM events WHERE (? IS NULL OR club_id=?) ORDER BY date", (club_id, club_id))
    return [event_view(r) for r in rows]


@app.get("/api/fee-preview")
def fee_preview(price: float):
    return payments.preview(price, db.get_settings())


# ------------------------------------------------------------------ matching
class SponsorSearch(BaseModel):
    query: str = ""
    sponsor_id: Optional[int] = None
    budget: Optional[float] = None
    slot_type: Optional[str] = None
    filters: dict = {}


@app.post("/api/search/events")
def search_events(body: SponsorSearch):
    sponsor = db.one("SELECT * FROM sponsors WHERE id=?", (body.sponsor_id,)) if body.sponsor_id else None
    events = [event_view(r) for r in db.q("SELECT * FROM events ORDER BY date")]
    filters = {k: v for k, v in (body.filters or {}).items() if v not in (None, "")}
    results, parsed, hidden = matching.rank_events(events, body.query, sponsor, body.budget,
                                                   body.slot_type or None, filters)
    db.insert("searches", ts=now(), side="sponsor", results=len(results))
    return {"parsed": parsed, "results": results, "hidden": hidden, "filters": filters}


class HostSearch(BaseModel):
    event_id: int
    guests: int
    funding_needed: float
    notes: str = ""


@app.post("/api/search/sponsors")
def search_sponsors(body: HostSearch):
    ev = event_view(get_or_404("events", body.event_id))
    club = get_or_404("clubs", ev["club_id"])
    sponsors = db.q("SELECT * FROM sponsors")
    history = {}
    for o in db.q("SELECT * FROM orders WHERE status != 'refunded'"):
        slot = db.one("SELECT event_id FROM slots WHERE id=?", (o["slot_id"],))
        e = db.one("SELECT club_id FROM events WHERE id=?", (slot["event_id"],)) if slot else None
        if e and e["club_id"] == ev["club_id"] and slot["event_id"] != ev["id"]:
            history[o["sponsor_id"]] = "club"
        else:
            history.setdefault(o["sponsor_id"], "platform")
    results, package, hidden = matching.rank_sponsors(sponsors, ev, club, body.guests, body.funding_needed,
                                                      body.notes, history)
    db.insert("searches", ts=now(), side="host", results=len(results))
    return {"results": results, "package": package, "hidden": hidden}


# ------------------------------------------------------------------ host: dinners and slots
class NewEvent(BaseModel):
    title: str
    date: str
    guests: int
    funding_needed: Optional[float] = None
    total_cost: Optional[float] = None
    ticket_price: Optional[float] = None
    vibes: List[str] = []
    audiences: List[str] = []
    description: str = ""


@app.post("/api/clubs/{club_id}/events")
def create_event(club_id: int, body: NewEvent):
    club = get_or_404("clubs", club_id)
    ticket = body.ticket_price or 0
    total = body.total_cost if body.total_cost is not None else ((body.funding_needed or 0) + body.guests * ticket)
    if body.guests < 1 or total < 0 or ticket < 0:
        raise HTTPException(400, "Guests must be at least 1, and costs and ticket prices cannot be negative.")
    gap = max(0.0, total - body.guests * ticket)
    eid = db.insert("events", club_id=club_id, title=body.title, date=body.date, venue=f"{club['name']} dining room",
                    neighborhood=club["neighborhood"], borough=club["borough"], guests=body.guests,
                    funding_needed=gap, vibes=body.vibes or club["vibes"],
                    audiences=body.audiences or club["audiences"], description=body.description,
                    format="family-style", interests=[], age_group=None, total_cost=total, ticket_price=ticket,
                    max_sponsors=3, preferred_cats=[], excluded_cats=[])
    return event_view(get_or_404("events", eid))


class EventProfile(BaseModel):
    title: Optional[str] = None
    date: Optional[str] = None
    guests: Optional[int] = None
    description: Optional[str] = None
    format: Optional[str] = None
    vibes: Optional[List[str]] = None
    audiences: Optional[List[str]] = None
    interests: Optional[List[str]] = None
    age_group: Optional[str] = None
    total_cost: Optional[float] = None
    ticket_price: Optional[float] = None
    max_sponsors: Optional[int] = None
    preferred_cats: Optional[List[str]] = None
    excluded_cats: Optional[List[str]] = None


@app.patch("/api/events/{event_id}")
def update_event(event_id: int, body: EventProfile):
    ev = get_or_404("events", event_id)
    ch = {k: v for k, v in body.model_dump().items() if v is not None}
    if ch.get("guests") is not None and ch["guests"] < 1:
        raise HTTPException(400, "Guests must be at least 1.")
    if any(ch.get(k, 0) < 0 for k in ("total_cost", "ticket_price")):
        raise HTTPException(400, "Costs and ticket prices cannot be negative.")
    if ch.get("max_sponsors") is not None and not 1 <= ch["max_sponsors"] <= 10:
        raise HTTPException(400, "Sponsor capacity must be between 1 and 10.")
    if set(ch.get("preferred_cats") or []) & set(ch.get("excluded_cats") or []):
        raise HTTPException(400, "A category cannot be both preferred and excluded.")
    if ch:
        db.update("events", event_id, **ch)
    ev = get_or_404("events", event_id)
    total = ev["total_cost"] if ev["total_cost"] is not None else ev["funding_needed"]
    db.update("events", event_id, funding_needed=max(0.0, (total or 0) - (ev["ticket_price"] or 0) * ev["guests"]))
    return event_view(get_or_404("events", event_id))


@app.post("/api/events/{event_id}/cover")
async def set_cover(event_id: int, file: UploadFile = File(...)):
    get_or_404("events", event_id)
    data = await file.read()
    try:
        im = Image.open(io.BytesIO(data))
        im.load()
        im = im.convert("RGB")
    except Exception:
        raise HTTPException(400, "That file is not an image. Use a JPG or PNG.")
    if im.width > 1600:
        im = im.resize((1600, round(im.height * 1600 / im.width)))
    folder = db.UPLOADS / "covers"
    folder.mkdir(parents=True, exist_ok=True)
    name = f"{event_id}-{datetime.now().strftime('%H%M%S')}.jpg"
    im.save(folder / name, "JPEG", quality=82, optimize=True)
    db.update("events", event_id, cover=f"/uploads/covers/{name}")
    return event_view(get_or_404("events", event_id))


class NewSlot(BaseModel):
    type: str
    title: Optional[str] = None
    specs: Optional[str] = None
    price: float
    photos_required: int = 1


@app.post("/api/events/{event_id}/slots")
def create_slot(event_id: int, body: NewSlot):
    get_or_404("events", event_id)
    if body.type not in seed.SLOT_TYPES:
        raise HTTPException(400, "Unknown slot type.")
    if body.price <= 0:
        raise HTTPException(400, "Price must be more than zero.")
    name, specs = seed.SLOT_TYPES[body.type]
    sid = db.insert("slots", event_id=event_id, type=body.type, title=body.title or name,
                    specs=body.specs or specs, price=body.price,
                    photos_required=max(1, body.photos_required), status="open")
    return get_or_404("slots", sid)


class SlotPatch(BaseModel):
    price: Optional[float] = None
    specs: Optional[str] = None
    photos_required: Optional[int] = None


@app.patch("/api/slots/{slot_id}")
def patch_slot(slot_id: int, body: SlotPatch):
    slot = get_or_404("slots", slot_id)
    if slot["status"] != "open":
        raise HTTPException(409, "Only open slots can be edited.")
    fields = {k: v for k, v in body.model_dump().items() if v is not None}
    if "price" in fields and fields["price"] <= 0:
        raise HTTPException(400, "Price must be more than zero.")
    if fields:
        db.update("slots", slot_id, **fields)
    return get_or_404("slots", slot_id)


@app.delete("/api/slots/{slot_id}")
def delete_slot(slot_id: int):
    slot = get_or_404("slots", slot_id)
    if slot["status"] != "open":
        raise HTTPException(409, "Only open slots can be removed.")
    db.run("DELETE FROM offers WHERE slot_id=?", (slot_id,))
    db.run("DELETE FROM slots WHERE id=?", (slot_id,))
    return {"ok": True}


# ------------------------------------------------------------------ deals: buy, bid, propose
def _check_fit(slot, sponsor_id):
    """Hard rules that protect the dinner: excluded categories, one brand per category, sponsor capacity."""
    ev = event_view(get_or_404("events", slot["event_id"]))
    sp = get_or_404("sponsors", sponsor_id)
    d = ev["density"]
    label = seed.CATEGORIES.get(sp["cat"], sp["category"])
    if sp["cat"] in (ev.get("excluded_cats") or []):
        raise HTTPException(409, f"The host does not take {label.lower()} sponsors at this dinner.")
    if sponsor_id not in d["sponsor_ids"]:
        if sp["cat"] in d["taken_cats"]:
            raise HTTPException(409, f"Another {label.lower()} brand already sponsors this dinner. Each category is exclusive.")
        if d["at_capacity"]:
            raise HTTPException(409, f"This dinner has reached its limit of {d['max_sponsors']} sponsors.")


def _reserve(slot, sponsor_id, price, source, offer_id=None):
    if slot["status"] != "open":
        raise HTTPException(409, "This slot is no longer available.")
    _check_fit(slot, sponsor_id)
    oid = db.insert("orders", slot_id=slot["id"], sponsor_id=sponsor_id, offer_id=offer_id, source=source,
                    price=price, fee=None, net=None, status="awaiting_payment", note="", created=now(),
                    paid_at=None, released_at=None)
    db.update("slots", slot["id"], status="reserved")
    db.run("UPDATE offers SET status='declined' WHERE slot_id=? AND status='pending' AND id IS NOT ?",
           (slot["id"], offer_id))
    return oid


class Buy(BaseModel):
    sponsor_id: int


@app.post("/api/slots/{slot_id}/buy")
def buy(slot_id: int, body: Buy):
    slot = get_or_404("slots", slot_id)
    get_or_404("sponsors", body.sponsor_id)
    oid = _reserve(slot, body.sponsor_id, slot["price"], "buy")
    return order_view(get_or_404("orders", oid))


class Bid(BaseModel):
    sponsor_id: int
    amount: float
    message: str = ""


@app.post("/api/slots/{slot_id}/bids")
def place_bid(slot_id: int, body: Bid):
    slot = get_or_404("slots", slot_id)
    get_or_404("sponsors", body.sponsor_id)
    if slot["status"] != "open":
        raise HTTPException(409, "This slot is no longer available.")
    if body.amount <= 0:
        raise HTTPException(400, "A bid must be more than zero.")
    _check_fit(slot, body.sponsor_id)
    oid = db.insert("offers", slot_id=slot_id, sponsor_id=body.sponsor_id, from_side="sponsor",
                    amount=body.amount, message=body.message, status="pending", created=now())
    return offer_view(get_or_404("offers", oid))


class Proposal(BaseModel):
    slot_id: int
    sponsor_id: int
    amount: float
    message: str = ""


@app.post("/api/proposals")
def propose(body: Proposal):
    slot = get_or_404("slots", body.slot_id)
    get_or_404("sponsors", body.sponsor_id)
    if slot["status"] != "open":
        raise HTTPException(409, "This slot is no longer available.")
    if body.amount <= 0:
        raise HTTPException(400, "An offer must be more than zero.")
    _check_fit(slot, body.sponsor_id)
    oid = db.insert("offers", slot_id=body.slot_id, sponsor_id=body.sponsor_id, from_side="host",
                    amount=body.amount, message=body.message, status="pending", created=now())
    return offer_view(get_or_404("offers", oid))


class Decision(BaseModel):
    decision: str  # accept | decline


@app.post("/api/offers/{offer_id}/decision")
def decide_offer(offer_id: int, body: Decision):
    offer = get_or_404("offers", offer_id)
    if offer["status"] != "pending":
        raise HTTPException(409, "This offer has already been answered.")
    if body.decision == "decline":
        db.update("offers", offer_id, status="declined")
        return offer_view(get_or_404("offers", offer_id))
    if body.decision != "accept":
        raise HTTPException(400, "Decision must be accept or decline.")
    slot = get_or_404("slots", offer["slot_id"])
    source = "bid" if offer["from_side"] == "sponsor" else "proposal"
    oid = _reserve(slot, offer["sponsor_id"], offer["amount"], source, offer_id)
    db.update("offers", offer_id, status="accepted")
    return order_view(get_or_404("orders", oid))


@app.get("/api/offers")
def list_offers(sponsor_id: Optional[int] = None, club_id: Optional[int] = None):
    rows = db.q("SELECT * FROM offers ORDER BY id DESC")
    out = [offer_view(r) for r in rows]
    if sponsor_id:
        out = [o for o in out if o["sponsor"]["id"] == sponsor_id]
    if club_id:
        out = [o for o in out if o["club"]["id"] == club_id]
    return out


# ------------------------------------------------------------------ orders: pay, proof, review, payout
@app.get("/api/orders")
def list_orders(sponsor_id: Optional[int] = None, club_id: Optional[int] = None, status: Optional[str] = None):
    out = [order_view(r) for r in db.q("SELECT * FROM orders ORDER BY id DESC")]
    if sponsor_id:
        out = [o for o in out if o["sponsor"]["id"] == sponsor_id]
    if club_id:
        out = [o for o in out if o["club"]["id"] == club_id]
    if status:
        out = [o for o in out if o["status"] == status]
    return out


def _order(order_id, *allowed):
    o = get_or_404("orders", order_id)
    if allowed and o["status"] not in allowed:
        raise HTTPException(409, f"This order is '{payments.STATUS_LABEL[o['status']]}', so that action is not available.")
    return o


@app.post("/api/orders/{order_id}/pay")
def pay(order_id: int):
    o = _order(order_id, "awaiting_payment")
    if o.get("deal_id"):
        raise HTTPException(409, "This placement is part of a package. Pay for the whole package instead.")
    p = _preview(o)
    db.update("orders", order_id, status="in_escrow", fee=p["fee"], net=p["net"], paid_at=now())
    evidence.audit("Sponsor", "sponsor", "paid_into_escrow", order_id, money_str(o["price"]))
    ledger(order_id, "charge", o["price"], "Sponsor paid the platform, funds held in escrow")
    return order_view(get_or_404("orders", order_id))


@app.post("/api/orders/{order_id}/cancel")
def cancel(order_id: int):
    o = _order(order_id, "awaiting_payment")
    if o.get("deal_id"):
        raise HTTPException(409, "This placement is part of a package. Cancel the whole package instead.")
    db.update("orders", order_id, status="refunded", note="Cancelled before payment")
    db.update("slots", o["slot_id"], status="open")
    return order_view(get_or_404("orders", order_id))


@app.post("/api/orders/{order_id}/proof")
async def upload_proof(order_id: int, files: List[UploadFile] = File(default=[]), scenario: str = Form(""),
                       links: str = Form(""), checkins: str = Form(""), note: str = Form(""),
                       capture: str = Form(""), blur_faces: str = Form("")):
    """Host submits evidence for one placement. PROTOTYPE: checks are simulated, real uploads always pass."""
    o = _order(order_id, "in_escrow")
    slot = get_or_404("slots", o["slot_id"])
    sp = get_or_404("sponsors", o["sponsor_id"])
    club = db.one("SELECT c.* FROM clubs c JOIN events e ON e.club_id=c.id WHERE e.id=?", (slot["event_id"],))
    if scenario:
        if evidence.LEGACY.get(scenario, scenario) not in evidence.SCENARIOS:
            raise HTTPException(400, "Unknown sample scenario.")
        raw = evidence.sample_files(slot, sp["name"], evidence.LEGACY.get(scenario, scenario), slot["photos_required"])
    else:
        raw = []
        for f in files:
            data = await f.read()
            mime = f.content_type or ""
            name = f.filename or "file"
            if not (mime.startswith("image/") or mime.startswith("video/") or name.lower().endswith(evidence.VIDEO_EXT + (".jpg", ".jpeg", ".png", ".heic", ".webp"))):
                raise HTTPException(400, f"{name} is not a photo or video.")
            raw.append((name, data, mime))
    if not raw:
        raise HTTPException(400, "Add at least one photo or video of the placement.")
    link_list = [u.strip() for u in re.split(r"[\s,]+", links or "") if u.strip()]
    bad = [u for u in link_list if not re.match(r"^https?://[^\s/]+\.[^\s]+", u)]
    if bad:
        raise HTTPException(400, f"These do not look like web links: {', '.join(bad[:3])}")
    n_checkins = None
    if str(checkins).strip():
        try:
            n_checkins = int(float(checkins))
        except ValueError:
            raise HTTPException(400, "Check-ins must be a number.")
        if n_checkins < 0:
            raise HTTPException(400, "Check-ins cannot be negative.")
    evidence.run(o, raw, scenario, f"{club['host_name']} ({club['name']})", note=note, links=link_list,
                 checkins=n_checkins, capture_session=capture or None, blur_faces=blur_faces in ("1", "true", "on"))
    return order_view(get_or_404("orders", order_id))


class Signoff(BaseModel):
    decision: str  # confirm | dispute
    note: str = ""


@app.post("/api/orders/{order_id}/signoff")
def sponsor_signoff(order_id: int, body: Signoff):
    """The sponsor confirms the placement, or disputes it. A dispute pauses the payout and goes to review."""
    o = _order(order_id, "ready_for_payout", "under_review", "released")
    evidence.audit("Sponsor", "sponsor", "signoff_" + body.decision, order_id, body.note)
    if body.decision == "confirm":
        db.update("orders", order_id, signoff="confirmed")
    elif body.decision == "dispute":
        if o["status"] == "released":
            raise HTTPException(409, "This placement is already paid out. Contact the platform to raise a dispute.")
        db.update("orders", order_id, signoff="disputed", status="under_review",
                  note="Sponsor disputed the placement: " + (body.note or "no reason given"))
    else:
        raise HTTPException(400, "Decision must be confirm or dispute.")
    return order_view(get_or_404("orders", order_id))


class Review(BaseModel):
    decision: str  # approve | reject | request_evidence | escalate | flag_fraud
    note: str = ""
    reviewer: str = "Platform reviewer"


@app.post("/api/orders/{order_id}/review")
def review(order_id: int, body: Review):
    """People decide. AI findings only inform this."""
    o = _order(order_id, "under_review", "in_escrow", "ready_for_payout")
    proof = db.one("SELECT * FROM proofs WHERE order_id=? ORDER BY id DESC", (order_id,))
    d, note = body.decision, body.note.strip()
    if d in ("reject", "flag_fraud", "escalate", "request_evidence") and not note:
        raise HTTPException(400, "Write down the reason. It goes in the audit trail and to the host.")
    if d == "approve":
        if o["status"] != "under_review":
            raise HTTPException(409, "Only items in review can be approved.")
        db.update("orders", order_id, status="ready_for_payout", note="Approved by a reviewer")
        if proof:
            db.update("proofs", proof["id"], decision="verified", reviewer_note=note or "Approved",
                      notes=f"Checked and approved by a reviewer{' after a ' + proof['risk_band'] + '-risk flag' if proof.get('risk_band') in ('medium', 'high') else ''}.")
    elif d in ("reject", "request_evidence"):
        db.update("orders", order_id, status="in_escrow",
                  note=("Evidence rejected: " if d == "reject" else "More evidence requested: ") + note)
        if proof:
            db.update("proofs", proof["id"], decision="rejected", reviewer_note=note)
    elif d == "escalate":
        db.update("orders", order_id, status="under_review", signoff="disputed", note="Escalated to a dispute: " + note)
    elif d == "flag_fraud":
        db.update("orders", order_id, status="under_review", fraud_flag=1, note="Flagged as suspected fraud: " + note)
    else:
        raise HTTPException(400, "Unknown decision.")
    evidence.audit(body.reviewer, "reviewer", d, order_id, note)
    return order_view(get_or_404("orders", order_id))


@app.get("/api/orders/{order_id}/evidence")
def order_evidence(order_id: int):
    """Everything a reviewer needs: agreement, every submission with files and findings, audit trail."""
    o = order_view(get_or_404("orders", order_id))
    subs = []
    for p in db.q("SELECT * FROM proofs WHERE order_id=? ORDER BY id DESC", (order_id,)):
        subs.append(dict(p, files=db.q("SELECT * FROM evidence_files WHERE proof_id=?", (p["id"],)),
                         findings=db.q("SELECT * FROM findings WHERE proof_id=?", (p["id"],))))
    return {"order": o, "submissions": subs,
            "audit": db.q("SELECT * FROM audit_log WHERE order_id=? ORDER BY id DESC", (order_id,))}


@app.get("/api/audit")
def audit_trail(limit: int = 60):
    return db.q("SELECT * FROM audit_log ORDER BY id DESC LIMIT ?", (limit,))


@app.post("/api/events/{event_id}/capture")
def capture_session(event_id: int):
    """A short-lived capture code for this event. In the prototype it is only recorded on the files."""
    get_or_404("events", event_id)
    import secrets
    token = secrets.token_hex(3).upper()
    exp = datetime.now().replace(microsecond=0)
    db.insert("capture_sessions", token=token, event_id=event_id, created=now(), expires=exp.isoformat())
    return {"token": token, "event_id": event_id, "valid_hours": 6}


@app.get("/api/orders/{order_id}/payout-preview")
def payout_preview(order_id: int):
    o = get_or_404("orders", order_id)
    return dict(_preview(o), order_id=order_id)


class Release(BaseModel):
    confirm: bool = False


@app.post("/api/orders/{order_id}/release")
def release(order_id: int, body: Release):
    o = _order(order_id, "ready_for_payout")
    if not body.confirm:
        raise HTTPException(400, "Confirm the transfer to release funds.")
    p = _preview(o)
    db.update("orders", order_id, status="released", fee=p["fee"], net=p["net"], released_at=now(),
              note="Paid out to host")
    ledger(order_id, "fee", p["fee"], f"Platform fee deducted ({p['rate']:.0%}, cap ${p['cap']:,.0f}" + (" per package" if o.get("deal_id") else "") + ")")
    ledger(order_id, "transfer", p["net"], "Transferred to host")
    evidence.audit("Platform", "platform", "payout_released", order_id, f"{money_str(p['net'])} to host after {money_str(p['fee'])} fee")
    return order_view(get_or_404("orders", order_id))


@app.post("/api/orders/{order_id}/refund")
def refund(order_id: int):
    o = _order(order_id, "in_escrow", "under_review", "ready_for_payout")
    db.update("orders", order_id, status="refunded", note="Refunded to sponsor")
    db.update("slots", o["slot_id"], status="open")
    ledger(order_id, "refund", o["price"], "Refunded to sponsor")
    evidence.audit("Platform", "platform", "refunded", order_id, money_str(o["price"]))
    return order_view(get_or_404("orders", order_id))


# ------------------------------------------------------------------ packages and multi-placement deals
def package_view(pk, slots_by_id, ev):
    slots = [slots_by_id[i] for i in pk["slot_ids"] if i in slots_by_id]
    list_total = sum(x["price"] for x in slots)
    discount = round(list_total * (pk["discount_pct"] or 0) / 100, 2)
    unavailable = [x["title"] for x in slots if x["status"] != "open"]
    return dict(pk, slots=slots, list_total=list_total, discount=discount, price=round(list_total - discount, 2),
                available=not unavailable and len(slots) == len(pk["slot_ids"]), unavailable=unavailable)


def quote(event_id, slot_ids, package_id=None):
    """Price a set of placements at one event. Packages use their own discount; a custom set of
    `bundle_min` or more placements gets the host's bundle discount."""
    ev = get_or_404("events", event_id)
    if not slot_ids:
        raise HTTPException(400, "Pick at least one placement.")
    if len(set(slot_ids)) != len(slot_ids):
        raise HTTPException(400, "Each placement can only be picked once.")
    slots = [get_or_404("slots", i) for i in slot_ids]
    if any(x["event_id"] != event_id for x in slots):
        raise HTTPException(400, "All placements in a package must be at the same event.")
    taken = [x["title"] for x in slots if x["status"] != "open"]
    pct, name = 0.0, "Custom package"
    if package_id:
        pk = get_or_404("packages", package_id)
        if pk["event_id"] != event_id or not pk["active"]:
            raise HTTPException(400, "That package is not offered at this event.")
        if sorted(pk["slot_ids"]) != sorted(slot_ids):
            raise HTTPException(400, "A package must be bought as defined. Use the builder for a custom mix.")
        pct, name = pk["discount_pct"] or 0, pk["name"]
    elif len(slot_ids) >= (ev["bundle_min"] or 3):
        pct = ev["bundle_discount_pct"] or 0
    list_total = sum(x["price"] for x in slots)
    discount = round(list_total * pct / 100, 2)
    return {"event_id": event_id, "name": name, "slots": slots, "list_total": list_total, "discount_pct": pct,
            "discount": discount, "price": round(list_total - discount, 2), "unavailable": taken,
            "fee_preview": payments.preview(list_total - discount, db.get_settings())}


class QuoteBody(BaseModel):
    event_id: int
    slot_ids: List[int]
    package_id: Optional[int] = None
    sponsor_id: Optional[int] = None


@app.post("/api/quote")
def get_quote(body: QuoteBody):
    return quote(body.event_id, body.slot_ids, body.package_id)


@app.post("/api/deals")
def create_deal(body: QuoteBody):
    if not body.sponsor_id:
        raise HTTPException(400, "Choose which brand is buying.")
    get_or_404("sponsors", body.sponsor_id)
    q = quote(body.event_id, body.slot_ids, body.package_id)
    if q["unavailable"]:
        raise HTTPException(409, "No longer available: " + ", ".join(q["unavailable"]) + ". Pick other placements.")
    _check_fit(q["slots"][0], body.sponsor_id)  # one check covers the event: category, exclusions, capacity
    did = db.insert("deals", sponsor_id=body.sponsor_id, event_id=body.event_id, package_id=body.package_id,
                    name=q["name"], list_total=q["list_total"], discount=q["discount"], price=q["price"], created=now())
    ratio = q["price"] / q["list_total"] if q["list_total"] else 1
    for x in q["slots"]:
        oid = _reserve(x, body.sponsor_id, round(x["price"] * ratio, 2), "package")
        db.update("orders", oid, deal_id=did)
    return deal_view(get_or_404("deals", did))


@app.get("/api/deals")
def list_deals(sponsor_id: Optional[int] = None, event_id: Optional[int] = None):
    sql, args = "SELECT * FROM deals WHERE 1=1", []
    if sponsor_id:
        sql += " AND sponsor_id=?"; args.append(sponsor_id)
    if event_id:
        sql += " AND event_id=?"; args.append(event_id)
    return [deal_view(d) for d in db.q(sql + " ORDER BY id DESC", args)]


@app.post("/api/deals/{deal_id}/pay")
def pay_deal(deal_id: int):
    """One consolidated payment for every placement in the package, held in escrow."""
    d = get_or_404("deals", deal_id)
    orders = db.q("SELECT * FROM orders WHERE deal_id=? AND status='awaiting_payment'", (deal_id,))
    if not orders:
        raise HTTPException(409, "Nothing in this package is waiting for payment.")
    for o in orders:
        p = _preview(o)
        db.update("orders", o["id"], status="in_escrow", fee=p["fee"], net=p["net"], paid_at=now())
        ledger(o["id"], "charge", o["price"], f"Part of package payment for deal {deal_id}, held in escrow")
        evidence.audit("Sponsor", "sponsor", "paid_into_escrow", o["id"], f"Package deal {deal_id}")
    return deal_view(d)


@app.post("/api/deals/{deal_id}/cancel")
def cancel_deal(deal_id: int):
    d = get_or_404("deals", deal_id)
    orders = db.q("SELECT * FROM orders WHERE deal_id=?", (deal_id,))
    if any(o["status"] not in ("awaiting_payment", "refunded") for o in orders):
        raise HTTPException(409, "This package is already paid. Ask the platform for a refund instead.")
    for o in orders:
        if o["status"] == "awaiting_payment":
            db.update("orders", o["id"], status="refunded", note="Package cancelled before payment")
            db.update("slots", o["slot_id"], status="open")
    return deal_view(d)


class PackageBody(BaseModel):
    name: str
    slot_ids: List[int]
    discount_pct: float = 0
    description: str = ""
    tier: str = "custom"
    active: bool = True


def _check_package(event_id, body):
    if not body.name.strip():
        raise HTTPException(400, "Give the package a name.")
    if len(set(body.slot_ids)) < 2:
        raise HTTPException(400, "A package needs at least two different placements.")
    if not 0 <= body.discount_pct <= 50:
        raise HTTPException(400, "Bundle discounts must be between 0% and 50%.")
    for i in body.slot_ids:
        if get_or_404("slots", i)["event_id"] != event_id:
            raise HTTPException(400, "Packages can only include placements from this event.")


@app.get("/api/events/{event_id}/packages")
def list_packages(event_id: int):
    ev = get_or_404("events", event_id)
    slots = {x["id"]: x for x in db.q("SELECT * FROM slots WHERE event_id=?", (event_id,))}
    return [package_view(p, slots, ev) for p in db.q("SELECT * FROM packages WHERE event_id=? ORDER BY id", (event_id,))]


@app.post("/api/events/{event_id}/packages")
def create_package(event_id: int, body: PackageBody):
    get_or_404("events", event_id)
    _check_package(event_id, body)
    db.insert("packages", event_id=event_id, name=body.name.strip(), tier=body.tier, description=body.description,
              slot_ids=list(dict.fromkeys(body.slot_ids)), discount_pct=body.discount_pct, active=1, created=now())
    return list_packages(event_id)


@app.put("/api/packages/{package_id}")
def update_package(package_id: int, body: PackageBody):
    pk = get_or_404("packages", package_id)
    _check_package(pk["event_id"], body)
    db.update("packages", package_id, name=body.name.strip(), description=body.description,
              slot_ids=list(dict.fromkeys(body.slot_ids)), discount_pct=body.discount_pct, active=1 if body.active else 0)
    return list_packages(pk["event_id"])


@app.delete("/api/packages/{package_id}")
def delete_package(package_id: int):
    pk = get_or_404("packages", package_id)
    db.run("DELETE FROM packages WHERE id=?", (package_id,))
    return list_packages(pk["event_id"])


class BundleBody(BaseModel):
    bundle_discount_pct: float
    bundle_min: int = 3


@app.put("/api/events/{event_id}/bundle")
def set_bundle(event_id: int, body: BundleBody):
    get_or_404("events", event_id)
    if not 0 <= body.bundle_discount_pct <= 50 or body.bundle_min < 2:
        raise HTTPException(400, "Discount must be 0% to 50%, for 2 or more placements.")
    db.update("events", event_id, bundle_discount_pct=body.bundle_discount_pct, bundle_min=body.bundle_min)
    return event_view(get_or_404("events", event_id))


# ------------------------------------------------------------------ platform
@app.get("/api/overview")
def overview():
    orders = [order_view(r) for r in db.q("SELECT * FROM orders")]
    held = sum(o["price"] for o in orders if o["status"] in payments.HELD)
    released = [o for o in orders if o["status"] == "released"]
    return {
        "held": held,
        "fees_earned": sum(o["fee"] or 0 for o in released),
        "paid_out": sum(o["net"] or 0 for o in released),
        "gmv": sum(o["price"] for o in orders if o["status"] in payments.HELD + ("released",)),
        "ai_cost": sum(p["ai_cost"] or 0 for o in orders for p in o["proofs"]),
        "photos_checked": sum(len(p["photos"]) for o in orders for p in o["proofs"]),
        "counts": {s: sum(1 for o in orders if o["status"] == s) for s in payments.STATUS_LABEL},
        "performance": _performance(orders),
        "ledger": db.q("SELECT * FROM ledger ORDER BY id DESC LIMIT 40"),
    }


def _avg_deal(live):
    """Group placements into transactions: a package is one transaction, a single slot is one."""
    groups = {}
    for o in live:
        key = ("d", o["deal_id"]) if o.get("deal_id") else ("o", o["id"])
        groups.setdefault(key, []).append(o)
    if not groups:
        return 0, 0, None
    n = len(groups)
    pk = sum(1 for k in groups if k[0] == "d")
    return (round(sum(sum(x["price"] for x in g) for g in groups.values()) / n),
            round(sum(len(g) for g in groups.values()) / n, 1), round(pk / n * 100))


def _performance(orders):
    """Baseline marketplace metrics from demo activity. No targets: these establish a starting point."""
    live = [o for o in orders if o["status"] != "refunded"]
    paid = [o for o in orders if o["status"] in payments.HELD + ("released",)]
    events = [event_view(r) for r in db.q("SELECT * FROM events")]
    offers = db.q("SELECT * FROM offers")
    searches = db.q("SELECT side FROM searches")
    by_sponsor = {}
    for o in live:
        by_sponsor[o["sponsor"]["id"]] = by_sponsor.get(o["sponsor"]["id"], 0) + 1
    with_proof = [o for o in paid if o["proofs"]]
    verified = [o for o in paid if o["status"] in ("ready_for_payout", "released")]
    funded = [e for e in events if e["funding"]["gross"] > 0]
    active_ev = set()
    for x in offers:
        sl = db.one("SELECT event_id FROM slots WHERE id=?", (x["slot_id"],))
        if sl:
            active_ev.add(sl["event_id"])
    for e in events:
        if e["density"]["placements"]:
            active_ev.add(e["id"])
    pct = lambda a, b: round(a / b * 100) if b else None
    return {
        "searches": len(searches), "deals": len(live),
        "search_to_booking": pct(len(live), len(searches)),
        "offers": len(offers),
        "match_to_deal": pct(sum(1 for x in offers if x["status"] == "accepted"), len(offers)),
        "avg_revenue_per_event": round(sum(e["funding"]["gross"] for e in funded) / len(funded)) if funded else 0,
        "avg_gap_covered": round(sum(e["funding"]["pct"] for e in events) / len(events)) if events else 0,
        "liquidity": pct(len(active_ev), len(events)),
        "verification_rate": pct(len(verified), len(with_proof)),
        "repeat_rate": pct(sum(1 for n in by_sponsor.values() if n > 1), len(by_sponsor)),
        "heavy_events": [e["title"] for e in events if e["density"]["flag"]],
        "avg_deal_value": _avg_deal(live)[0],
        "avg_placements": _avg_deal(live)[1],
        "package_share": _avg_deal(live)[2],
        "events": len(events),
    }


class SettingsBody(BaseModel):
    fee_rate: Optional[float] = None
    fee_cap: Optional[float] = None
    ai_cost_per_photo: Optional[float] = None
    auto_verify_confidence: Optional[float] = None


@app.put("/api/settings")
def put_settings(body: SettingsBody):
    for k, v in body.model_dump().items():
        if v is None:
            continue
        if k == "fee_rate" and not 0 <= v <= 1:
            raise HTTPException(400, "Fee rate must be between 0% and 100%.")
        if v < 0:
            raise HTTPException(400, f"{k} cannot be negative.")
        db.set_setting(k, v)
    return db.get_settings()


class FeedbackBody(BaseModel):
    rating: int
    message: str = ""
    role: str = ""
    page: str = ""


@app.post("/api/feedback")
def add_feedback(body: FeedbackBody):
    if not 1 <= body.rating <= 5:
        raise HTTPException(400, "Pick a rating from 1 to 5.")
    db.insert("feedback", ts=now(), role=body.role[:20], rating=body.rating, message=body.message[:2000], page=body.page[:60])
    return {"ok": True}


@app.get("/api/feedback")
def list_feedback():
    return db.q("SELECT * FROM feedback ORDER BY id DESC LIMIT 100")


@app.post("/api/reset")
def reset():
    seed.seed()
    import shutil
    shutil.rmtree(db.UPLOADS, ignore_errors=True)
    db.UPLOADS.mkdir(parents=True, exist_ok=True)
    return {"ok": True}


# ------------------------------------------------------------------ static
db.UPLOADS.mkdir(parents=True, exist_ok=True)
app.mount("/uploads", StaticFiles(directory=db.UPLOADS), name="uploads")
app.mount("/static", StaticFiles(directory=ROOT / "static"), name="static")


@app.get("/")
def index():
    return FileResponse(ROOT / "static" / "index.html")
