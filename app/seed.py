"""Curated, fictional demo data. Every sponsor, supper club and dinner here is invented.

Edit this file to change what the demo marketplace contains, then use "Reset demo data" in the app.
"""
from datetime import date, datetime, timedelta

from . import db, payments

BROOKLYN = ["Williamsburg", "Bushwick", "Park Slope", "DUMBO"]

SPONSORS = [
    dict(name="Leafline", category="Plant-based snacks",
         blurb="Crunchy chickpea and seaweed snacks for people who read the label.",
         vibes=["hip", "wellness", "casual"], audiences=["young-professionals", "fitness"],
         places=["Williamsburg", "Bushwick", "Park Slope", "DUMBO"],
         budget_min=500, budget_max=6000, min_guests=20, max_guests=80, color="#2F7D5B"),
    dict(name="Sunbrew", category="Cold brew coffee",
         blurb="Small-batch cold brew in a can, sold at independent cafes.",
         vibes=["hip", "trendy", "creative"], audiences=["creatives", "young-professionals", "tech"],
         places=["Williamsburg", "Bushwick", "DUMBO"],
         budget_min=300, budget_max=4000, min_guests=15, max_guests=60, color="#8A5A2B"),
    dict(name="Copperhollow", category="Craft spirits",
         blurb="Barrel-aged bourbon and rye from a four-person distillery in the Hudson Valley.",
         vibes=["upscale", "cozy", "music"], audiences=["foodies", "couples", "young-professionals"],
         places=["Harlem", "Park Slope", "Williamsburg", "Astoria"],
         budget_min=1500, budget_max=15000, min_guests=20, max_guests=100, color="#B4562B"),
    dict(name="Pawlette", category="Pet wellness",
         blurb="Gentle supplements and treats for dogs and cats.",
         vibes=["family", "cozy", "community"], audiences=["families", "couples"],
         places=["Park Slope", "Astoria"],
         budget_min=300, budget_max=3000, min_guests=15, max_guests=50, color="#5B7FA6"),
    dict(name="Tidewell", category="Sparkling water",
         blurb="Mineral sparkling water with a hint of fruit and no sweeteners.",
         vibes=["casual", "wellness", "hip"], audiences=["fitness", "young-professionals", "students"],
         places=["Williamsburg", "Bushwick", "Park Slope", "DUMBO", "Harlem", "Astoria"],
         budget_min=200, budget_max=2500, min_guests=15, max_guests=100, color="#2A8FA3"),
    dict(name="Glowlab", category="Skincare",
         blurb="Fragrance-free skincare made with dermatologists, sold online.",
         vibes=["upscale", "trendy", "wellness"], audiences=["creatives", "couples", "young-professionals"],
         places=["Williamsburg", "DUMBO", "Harlem"],
         budget_min=1000, budget_max=9000, min_guests=20, max_guests=70, color="#B0577A"),
    dict(name="Pocketpal", category="Budgeting app",
         blurb="A budgeting app that splits bills and tracks shared spending.",
         vibes=["casual", "hip"], audiences=["students", "young-professionals", "tech"],
         places=["Bushwick", "DUMBO", "Astoria"],
         budget_min=500, budget_max=5000, min_guests=20, max_guests=90, color="#5A4FCF"),
    dict(name="Spicewell", category="Hot sauce",
         blurb="Fermented hot sauces in six heat levels, made in Red Hook.",
         vibes=["foodie", "casual", "late-night"], audiences=["foodies", "young-professionals"],
         places=["Bushwick", "Astoria", "Williamsburg"],
         budget_min=250, budget_max=3500, min_guests=12, max_guests=60, color="#C0392B"),
]

CLUBS = [
    dict(name="Fig & Ember", host_name="Maya Okafor", neighborhood="Williamsburg", borough="Brooklyn",
         blurb="Fire-cooked seasonal dinners in a converted print shop. Twenty-four seats, one long table.",
         vibes=["hip", "trendy", "creative", "cozy"], audiences=["creatives", "young-professionals", "foodies"]),
    dict(name="Long Table Lenox", host_name="Desmond Pierre", neighborhood="Harlem", borough="Manhattan",
         blurb="Sunday suppers built around live music and family recipes.",
         vibes=["community", "music", "upscale", "cozy"], audiences=["couples", "foodies", "creatives"]),
    dict(name="The Quiet Course", host_name="Priya Nair", neighborhood="Park Slope", borough="Brooklyn",
         blurb="Slow, plant-forward dinners with no phones at the table.",
         vibes=["wellness", "family", "cozy"], audiences=["families", "fitness", "couples"]),
    dict(name="Midnight Noodle Society", host_name="Theo Lin", neighborhood="Bushwick", borough="Brooklyn",
         blurb="Late seatings, hand-pulled noodles, a playlist that gets louder as the night goes on.",
         vibes=["late-night", "hip", "foodie", "casual"], audiences=["young-professionals", "students", "foodies"]),
    dict(name="Dumbo Dinner Lab", host_name="Sam Rivera", neighborhood="DUMBO", borough="Brooklyn",
         blurb="Test-kitchen dinners for founders and designers, with a view of the bridge.",
         vibes=["trendy", "creative", "upscale"], audiences=["tech", "young-professionals", "creatives"]),
    dict(name="Corner Table Queens", host_name="Elena Kostas", neighborhood="Astoria", borough="Queens",
         blurb="Neighborhood dinners that cook through Queens one cuisine at a time.",
         vibes=["foodie", "community", "casual"], audiences=["foodies", "families", "students"]),
]

# slot catalog: type -> (title, specs template)
SLOT_TYPES = {
    "menu": ("Menu mention", "Logo and one line of copy printed on every menu. You supply the artwork, we place it."),
    "table": ("Table sponsor", "Your name on the table cards, and your product at each place setting."),
    "display": ("Screen and logo display", "Your logo on the dining room screen during arrival and between courses."),
    "drink": ("Welcome drink", "A welcome drink named after your brand, poured for every guest on arrival."),
    "gift": ("Take-home gift", "Your sample or gift in each guest's take-home bag, with a printed card."),
    "title": ("Presenting sponsor", "Your name in the dinner title, on all invitations, plus a two-minute welcome from the host."),
}

# (club index, title, days from today, guests, funding needed, vibes, audiences, description, [(slot type, price, photos)])
EVENTS = [
    (0, "Smoke and stone fruit", 9, 24, 3200, ["hip", "trendy", "creative"], ["creatives", "young-professionals"],
     "Five courses cooked over open fire, finished with grilled peaches.",
     [("menu", 300, 1), ("table", 1000, 1), ("display", 600, 1), ("drink", 900, 2), ("gift", 700, 1)]),
    (0, "The long summer table", 23, 24, 3600, ["cozy", "hip", "foodie"], ["foodies", "young-professionals"],
     "A slow family-style dinner to close the season.",
     [("menu", 300, 1), ("table", 1100, 1), ("drink", 900, 2), ("gift", 700, 1)]),
    (1, "Sunday supper with the quartet", 12, 36, 4800, ["music", "upscale", "cozy"], ["couples", "foodies"],
     "A four-course supper with a live jazz quartet between courses.",
     [("menu", 400, 1), ("table", 1500, 1), ("drink", 1800, 2), ("title", 4500, 2)]),
    (2, "Green plates, no phones", 15, 20, 2000, ["wellness", "cozy"], ["fitness", "families", "couples"],
     "Plant-forward tasting menu. Phones go in a basket at the door.",
     [("menu", 250, 1), ("table", 800, 1), ("gift", 600, 1)]),
    (3, "Late noodle night", 6, 32, 2600, ["late-night", "hip", "foodie"], ["young-professionals", "students"],
     "Hand-pulled noodles, three broths, a 9:30 seating.",
     [("menu", 250, 1), ("display", 500, 1), ("drink", 700, 2), ("table", 800, 1)]),
    (3, "Chili oil showdown", 30, 40, 3000, ["foodie", "casual", "late-night"], ["foodies", "young-professionals"],
     "Six house chili oils, judged by the table.",
     [("menu", 300, 1), ("display", 600, 1), ("table", 900, 1), ("gift", 650, 1)]),
    (4, "Founders table: the bridge dinner", 18, 80, 15000, ["trendy", "creative", "upscale"], ["tech", "young-professionals", "creatives"],
     "Our biggest dinner of the year, eighty seats under the bridge.",
     [("menu", 900, 1), ("display", 2200, 1), ("table", 3500, 1), ("drink", 4000, 2), ("title", 12000, 3)]),
    (4, "Test kitchen: fermentation", 40, 28, 4200, ["creative", "trendy"], ["tech", "creatives"],
     "Seven small plates built around things that sat in a jar for a month.",
     [("menu", 350, 1), ("table", 1200, 1), ("gift", 900, 1)]),
    (5, "Around Astoria in five plates", 11, 30, 3000, ["foodie", "community", "casual"], ["foodies", "families", "students"],
     "Greek, Egyptian, Colombian, Bangladeshi and Brazilian plates from five neighbors.",
     [("menu", 250, 1), ("table", 800, 1), ("drink", 700, 2), ("gift", 550, 1)]),
]

# illustrative cover photos bundled in static/covers (AI-generated, for fictional dinners)
COVERS = {
    "Smoke and stone fruit": "smoke-and-stone-fruit", "The long summer table": "long-summer-table",
    "Sunday supper with the quartet": "sunday-supper-quartet", "Green plates, no phones": "green-plates-no-phones",
    "Late noodle night": "late-noodle-night", "Chili oil showdown": "chili-oil-showdown",
    "Founders table: the bridge dinner": "founders-table-bridge", "Test kitchen: fermentation": "test-kitchen-fermentation",
    "Around Astoria in five plates": "around-astoria-five-plates",
}


def cover_for(title):
    return f"/static/covers/{COVERS[title]}.jpg" if title in COVERS else None


def backfill_covers():
    """Give older demo databases the bundled photos without wiping anything a host uploaded."""
    for ev in db.q("SELECT id, title FROM events WHERE cover IS NULL OR cover = ''"):
        if cover_for(ev["title"]):
            db.update("events", ev["id"], cover=cover_for(ev["title"]))


NOW = lambda: datetime.now().isoformat(timespec="seconds")


def seed():
    db.wipe()
    for k, v in db.DEFAULT_SETTINGS.items():
        db.set_setting(k, v)
    sp_ids = [db.insert("sponsors", **s) for s in SPONSORS]
    club_ids = [db.insert("clubs", **c) for c in CLUBS]
    slot_ids = {}  # (event index, slot type) -> id
    ev_ids = []
    for i, (ci, title, days, guests, need, vibes, auds, desc, slots) in enumerate(EVENTS):
        club = CLUBS[ci]
        d = (date.today() + timedelta(days=days)).isoformat()
        eid = db.insert("events", club_id=club_ids[ci], title=title, date=d, venue=f"{club['name']} dining room",
                        neighborhood=club["neighborhood"], borough=club["borough"], guests=guests,
                        funding_needed=need, vibes=vibes, audiences=auds, description=desc, cover=cover_for(title))
        ev_ids.append(eid)
        for t, price, photos in slots:
            name, specs = SLOT_TYPES[t]
            slot_ids[(i, t)] = db.insert("slots", event_id=eid, type=t, title=name, specs=specs,
                                         price=price, photos_required=photos, status="open")

    s = db.get_settings()
    sp = {x["name"]: sp_ids[i] for i, x in enumerate(SPONSORS)}

    # A finished deal, so the platform view shows a real payout and fee.
    slot = slot_ids[(5, "menu")]
    _order(slot, sp["Spicewell"], 300, "buy", s, "released", paid=True, released=True)
    # A deal in escrow, waiting for the host to upload photos.
    slot = slot_ids[(4, "drink")]
    _order(slot, sp["Tidewell"], 700, "buy", s, "in_escrow", paid=True)
    # A bid from a sponsor, waiting for the host to decide.
    db.update("slots", slot_ids[(0, "table")], status="open")
    db.insert("offers", slot_id=slot_ids[(0, "table")], sponsor_id=sp["Spicewell"], from_side="sponsor",
              amount=800, message="We would love to put Spicewell on every place setting. Could you do $800?",
              status="pending", created=NOW())
    # A proposal from a host, waiting for the sponsor to decide.
    db.insert("offers", slot_id=slot_ids[(0, "display")], sponsor_id=sp["Sunbrew"], from_side="host",
              amount=600, message="Your cold brew would suit this crowd. The screen runs all night.",
              status="pending", created=NOW())


def _order(slot_id, sponsor_id, price, source, s, status, paid=False, released=False):
    fee, net, _ = payments.compute_fee(price, s["fee_rate"], s["fee_cap"])
    oid = db.insert("orders", slot_id=slot_id, sponsor_id=sponsor_id, offer_id=None, source=source,
                    price=price, fee=fee if paid else None, net=net if paid else None, status=status,
                    note="", created=NOW(), paid_at=NOW() if paid else None,
                    released_at=NOW() if released else None)
    db.update("slots", slot_id, status="reserved")
    if paid:
        db.insert("ledger", order_id=oid, ts=NOW(), kind="charge", amount=price, note="Sponsor paid the platform")
    if released:
        db.insert("ledger", order_id=oid, ts=NOW(), kind="fee", amount=fee, note="Platform fee deducted")
        db.insert("ledger", order_id=oid, ts=NOW(), kind="transfer", amount=net, note="Transferred to host")
    return oid
