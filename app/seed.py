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
    dict(name="Second Hand Hearts", host_name="Nadia Brooks", neighborhood="Bushwick", borough="Brooklyn",
         blurb="Swap meets and breakup parties for people starting over, one tote bag at a time.",
         vibes=["hip", "casual", "community"], audiences=["young-professionals", "creatives", "students"]),
    dict(name="Static Room", host_name="Ines Varga", neighborhood="Lower East Side", borough="Manhattan",
         blurb="A storefront gallery that hosts artist talks, readings and odd little performances.",
         vibes=["creative", "trendy", "late-night"], audiences=["creatives", "young-professionals"]),
    dict(name="Dawn Patrol Run Club", host_name="Kofi Mensah", neighborhood="Williamsburg", borough="Brooklyn",
         blurb="Sunrise runs over the bridge that end with coffee and something warm.",
         vibes=["wellness", "community", "casual"], audiences=["fitness", "young-professionals"]),
    dict(name="Side B Sessions", host_name="Rae Tanaka", neighborhood="Bushwick", borough="Brooklyn",
         blurb="Full-album listening parties on a very good sound system. Phones down, records up.",
         vibes=["music", "cozy", "late-night"], audiences=["creatives", "young-professionals", "couples"]),
    dict(name="Kiln & Co", host_name="Sofia Reyes", neighborhood="Astoria", borough="Queens",
         blurb="Beginner pottery nights with snacks, playlists and too many mugs.",
         vibes=["creative", "cozy", "community"], audiences=["couples", "creatives", "families"]),
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
    (6, "The Ex Files: swap out your ex's stuff", 8, 150, 4500, ["hip", "casual", "community"], ["young-professionals", "creatives", "students"],
     "Bring the hoodie, the records and the air fryer. Leave with something that has no memories attached. DJ from 8.",
     [("menu", 300, 1), ("drink", 1200, 2), ("gift", 900, 1), ("display", 700, 1), ("title", 3000, 2)]),
    (7, "Psychic Telephone: an artist talk", 13, 60, 1800, ["creative", "trendy"], ["creatives", "young-professionals"],
     "Three artists pass one idea down the line and show what came out the other end. Q&A and drinks after.",
     [("menu", 200, 1), ("drink", 700, 2), ("display", 400, 1)]),
    (8, "Bridge run and bagels", 4, 120, 2200, ["wellness", "community", "casual"], ["fitness", "young-professionals"],
     "A 5K over the Williamsburg Bridge at sunrise, then bagels and cold drinks in the park.",
     [("drink", 800, 2), ("gift", 700, 1), ("table", 500, 1)]),
    (9, "Side B: a full-album listening party", 17, 70, 2400, ["music", "cozy", "late-night"], ["creatives", "couples"],
     "One classic record, start to finish, on a sound system worth hearing. No talking during side B.",
     [("drink", 900, 2), ("display", 500, 1), ("gift", 600, 1)]),
    (10, "Mugs and mezcal: a pottery night", 21, 24, 1500, ["creative", "cozy"], ["couples", "creatives"],
     "Throw your first mug, glaze someone else's, and take a finished piece home three weeks later.",
     [("drink", 600, 2), ("gift", 450, 1), ("table", 350, 1)]),
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


# Structured profile data added for the action plan (interests, age groups, category, preferred placements).
CATEGORIES = {
    "snacks": "Snacks", "coffee": "Coffee", "spirits": "Spirits and alcohol", "pet": "Pet products",
    "beverages": "Soft drinks and water", "skincare": "Beauty and skincare", "fintech": "Finance apps",
    "condiments": "Sauces and condiments",
}
FORMATS = {
    "swap": "Swap meet", "talk": "Talk and Q&A", "run": "Group run", "listening": "Listening session",
    "workshop": "Hands-on workshop",
    "family-style": "Family-style supper", "tasting": "Seated tasting menu", "music": "Supper with live music",
    "late-night": "Late-night counter", "cook-off": "Cook-off or competition", "banquet": "Large banquet",
    "test-kitchen": "Test kitchen", "potluck": "Neighborhood potluck",
}
INTERESTS = ["design", "art", "food culture", "music", "wellness", "fitness", "tech", "sustainability",
             "nightlife", "travel", "fashion", "family"]
AGE_GROUPS = ["21-29", "30-39", "40-54", "55+"]

SPONSOR_PROFILE = {
    "Leafline": dict(cat="snacks", interests=["wellness", "fitness", "sustainability"], age_groups=["21-29", "30-39"], engagement=["gift", "table"]),
    "Sunbrew": dict(cat="coffee", interests=["design", "art", "tech"], age_groups=["21-29", "30-39"], engagement=["drink", "display", "menu"]),
    "Copperhollow": dict(cat="spirits", interests=["food culture", "music", "travel"], age_groups=["30-39", "40-54"], engagement=["drink", "title", "table"]),
    "Pawlette": dict(cat="pet", interests=["family", "wellness"], age_groups=["30-39", "40-54"], engagement=["gift", "table"]),
    "Tidewell": dict(cat="beverages", interests=["fitness", "wellness", "nightlife"], age_groups=["21-29", "30-39"], engagement=["drink", "table"]),
    "Glowlab": dict(cat="skincare", interests=["fashion", "wellness", "design"], age_groups=["21-29", "30-39", "40-54"], engagement=["gift", "title"]),
    "Pocketpal": dict(cat="fintech", interests=["tech", "nightlife", "travel"], age_groups=["21-29"], engagement=["display", "menu"]),
    "Spicewell": dict(cat="condiments", interests=["food culture", "nightlife"], age_groups=["21-29", "30-39"], engagement=["table", "menu", "gift"]),
}
# event kind and how many people marked themselves interested (demo numbers)
KINDS = {"dinner": "Supper club", "party": "Party", "swap": "Swap meet", "talk": "Artist talk",
         "run": "Run club", "listening": "Listening party", "workshop": "Workshop"}
EVENT_KIND = {
    "The Ex Files: swap out your ex's stuff": ("swap", 640), "Psychic Telephone: an artist talk": ("talk", 210),
    "Bridge run and bagels": ("run", 380), "Side B: a full-album listening party": ("listening", 165),
    "Mugs and mezcal: a pottery night": ("workshop", 92),
    "Smoke and stone fruit": ("dinner", 88), "The long summer table": ("dinner", 61),
    "Sunday supper with the quartet": ("dinner", 140), "Green plates, no phones": ("dinner", 47),
    "Late noodle night": ("dinner", 120), "Chili oil showdown": ("dinner", 175),
    "Founders table: the bridge dinner": ("dinner", 310), "Test kitchen: fermentation": ("dinner", 74),
    "Around Astoria in five plates": ("dinner", 96),
}

# title -> format, interests, age group, ticket price, max sponsors, preferred and excluded categories
EVENT_PROFILE = {
    "Smoke and stone fruit": ("tasting", ["food culture", "design", "art"], "21-29", 95, 3, ["coffee", "spirits", "condiments"], ["fintech"]),
    "The long summer table": ("family-style", ["food culture", "sustainability"], "30-39", 85, 3, ["beverages", "snacks"], []),
    "Sunday supper with the quartet": ("music", ["music", "food culture", "travel"], "30-39", 120, 2, ["spirits"], ["fintech", "pet"]),
    "Green plates, no phones": ("tasting", ["wellness", "sustainability", "family"], "30-39", 75, 2, ["snacks", "beverages", "skincare"], ["spirits", "fintech"]),
    "Late noodle night": ("late-night", ["nightlife", "food culture"], "21-29", 45, 3, ["condiments", "beverages"], ["pet"]),
    "Chili oil showdown": ("cook-off", ["food culture", "nightlife"], "21-29", 40, 3, ["condiments", "beverages"], []),
    "Founders table: the bridge dinner": ("banquet", ["tech", "design", "art"], "30-39", 110, 4, ["coffee", "spirits", "fintech"], ["pet"]),
    "Test kitchen: fermentation": ("test-kitchen", ["food culture", "tech", "sustainability"], "21-29", 90, 2, ["condiments", "coffee"], []),
    "The Ex Files: swap out your ex's stuff": ("swap", ["fashion", "sustainability", "nightlife"], "21-29", 15, 4, ["beverages", "snacks", "fintech"], ["pet"]),
    "Psychic Telephone: an artist talk": ("talk", ["art", "design"], "21-29", 20, 2, ["spirits", "coffee", "beverages"], ["fintech"]),
    "Bridge run and bagels": ("run", ["fitness", "wellness"], "21-29", 10, 3, ["beverages", "snacks", "coffee"], ["spirits"]),
    "Side B: a full-album listening party": ("listening", ["music", "nightlife", "design"], "30-39", 25, 2, ["spirits", "beverages"], ["fintech"]),
    "Mugs and mezcal: a pottery night": ("workshop", ["art", "design"], "30-39", 55, 2, ["spirits", "snacks"], []),
    "Around Astoria in five plates": ("potluck", ["food culture", "family", "travel"], "30-39", 35, 3, ["condiments", "beverages", "snacks"], ["spirits"]),
}
DATA_VERSION = "5"


NOW = lambda: datetime.now().isoformat(timespec="seconds")


def seed():
    db.wipe()
    for k, v in db.DEFAULT_SETTINGS.items():
        db.set_setting(k, v)
    sp_ids = [db.insert("sponsors", **s, **SPONSOR_PROFILE[s["name"]]) for s in SPONSORS]
    club_ids = [db.insert("clubs", **c) for c in CLUBS]
    slot_ids = {}  # (event index, slot type) -> id
    ev_ids = []
    for i, (ci, title, days, guests, need, vibes, auds, desc, slots) in enumerate(EVENTS):
        club = CLUBS[ci]
        d = (date.today() + timedelta(days=days)).isoformat()
        eid = db.insert("events", club_id=club_ids[ci], title=title, date=d, venue=f"{club['name']} dining room",
                        neighborhood=club["neighborhood"], borough=club["borough"], guests=guests,
                        funding_needed=need, vibes=vibes, audiences=auds, description=desc, cover=cover_for(title),
                        **_profile(title, guests, need))
        ev_ids.append(eid)
        for t, price, photos in slots:
            name, specs = SLOT_TYPES[t]
            slot_ids[(i, t)] = db.insert("slots", event_id=eid, type=t, title=name, specs=specs,
                                         price=price, photos_required=photos, status="open")
        default_packages(eid, db.q("SELECT * FROM slots WHERE event_id=?", (eid,)))

    db.set_setting("data_version", DATA_VERSION)
    s = db.get_settings()
    sp = {x["name"]: sp_ids[i] for i, x in enumerate(SPONSORS)}

    # A finished deal, so the platform view shows a real payout and fee.
    slot = slot_ids[(5, "menu")]
    done = _order(slot, sp["Spicewell"], 300, "buy", s, "released", paid=True, released=True)
    db.update("orders", done, signoff="confirmed")
    # A deal in escrow, waiting for the host to upload photos.
    slot = slot_ids[(4, "drink")]
    _order(slot, sp["Tidewell"], 700, "buy", s, "in_escrow", paid=True)
    # A bid from a sponsor, waiting for the host to decide.
    db.update("slots", slot_ids[(0, "table")], status="open")
    db.insert("offers", slot_id=slot_ids[(0, "table")], sponsor_id=sp["Spicewell"], from_side="sponsor",
              amount=800, message="We would love to put Spicewell on every place setting. Could you do $800?",
              status="pending", created=NOW())
    _evidence_demo(slot_ids, sp, s, done)

    # A proposal from a host, waiting for the sponsor to decide.
    db.insert("offers", slot_id=slot_ids[(0, "display")], sponsor_id=sp["Sunbrew"], from_side="host",
              amount=600, message="Your cold brew would suit this crowd. The screen runs all night.",
              status="pending", created=NOW())


def _evidence_demo(slot_ids, sp, s, done):
    """Six labeled verification cases. All checks are simulated; the images are drawn in code."""
    from . import evidence
    host = lambda i: f"{CLUBS[EVENTS[i][0]]['host_name']} ({CLUBS[EVENTS[i][0]]['name']})"

    def submit(oid, scenario, i):
        o = db.one("SELECT * FROM orders WHERE id=?", (oid,))
        slot = db.one("SELECT * FROM slots WHERE id=?", (o["slot_id"],))
        spn = db.one("SELECT name FROM sponsors WHERE id=?", (o["sponsor_id"],))["name"]
        evidence.run(o, evidence.sample_files(slot, spn, scenario, slot["photos_required"]), scenario, host(i),
                     note="Demo submission", checkins=None)

    # 1 to 3: a three-placement package at Psychic Telephone, each placement checked on its own
    ev = 10
    types = [("drink", "authentic"), ("menu", "reused"), ("display", "ai_signals")]
    prices = {t: db.one("SELECT price FROM slots WHERE id=?", (slot_ids[(ev, t)],))["price"] for t, _ in types}
    total = sum(prices.values())
    did = db.insert("deals", sponsor_id=sp["Copperhollow"], event_id=db.one("SELECT event_id FROM slots WHERE id=?", (slot_ids[(ev, "drink")],))["event_id"],
                    package_id=None, name="Custom package", list_total=total, discount=round(total * 0.05, 2),
                    price=round(total * 0.95, 2), created=NOW())
    for t, scenario in types:
        oid = _order(slot_ids[(ev, t)], sp["Copperhollow"], round(prices[t] * 0.95, 2), "package", s, "in_escrow", paid=True)
        db.update("orders", oid, deal_id=did)
        submit(oid, scenario, ev)
    # 4: not enough evidence
    oid = _order(slot_ids[(13, "gift")], sp["Glowlab"], 450, "buy", s, "in_escrow", paid=True)
    submit(oid, "insufficient", 13)
    # 5: unclear, sent to a person
    oid = _order(slot_ids[(11, "gift")], sp["Leafline"], 700, "buy", s, "in_escrow", paid=True)
    submit(oid, "needs_review", 11)
    # 6: the completed deal gets its authentic proof on record
    db.update("orders", done, status="in_escrow")
    submit(done, "authentic", 5)
    db.update("orders", done, status="released", note="Paid out to host", signoff="confirmed")


TIER_INFO = {
    "supporting": ("Supporting sponsor", "Two light-touch placements that put your name in front of every guest.", 0),
    "featured": ("Featured sponsor", "Your product in guests' hands, plus your name on the night.", 10),
    "presenting": ("Presenting sponsor", "The headline package: your name on the event and the best placements.", 15),
}


def default_packages(event_id, slots):
    """Three starter packages per event, built from its own slots. Hosts can edit or delete them."""
    by = {s["type"]: s for s in slots}
    cheap = sorted(slots, key=lambda s: s["price"])
    plans = {
        "supporting": [t for t in ("menu", "display") if t in by] or [s["type"] for s in cheap[:2]],
        "featured": [t for t in ("drink", "gift", "menu") if t in by],
        "presenting": (["title"] if "title" in by else []) + [t for t in ("drink", "table", "display", "menu") if t in by],
    }
    for tier, types in plans.items():
        types = list(dict.fromkeys(types))[:4 if tier == "presenting" else 3]
        if len(types) < 2:
            continue
        name, desc, disc = TIER_INFO[tier]
        db.insert("packages", event_id=event_id, name=name, tier=tier, description=desc,
                  slot_ids=[by[t]["id"] for t in types], discount_pct=disc, active=1, created=NOW())


def _profile(title, guests, need):
    fmt, interests, age, ticket, cap, pref, excl = EVENT_PROFILE[title]
    # total cost is set so that cost minus ticket revenue equals the original funding gap
    kind, interested = EVENT_KIND.get(title, ("dinner", 0))
    return dict(kind=kind, interested=interested, bundle_discount_pct=5, bundle_min=3, format=fmt, interests=interests, age_group=age, ticket_price=ticket,
                total_cost=need + guests * ticket, max_sponsors=cap, preferred_cats=pref, excluded_cats=excl)


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
