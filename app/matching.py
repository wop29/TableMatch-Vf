"""Matching in both directions over the curated demo list. No internet search.

Rule-based on purpose, so every score can be explained factor by factor.
Order of work for both directions:
  1. hard constraints remove options (filters, budget ceilings, excluded categories,
     category exclusivity, sponsor capacity);
  2. what is left is ranked with weighted soft factors (WEIGHTS below);
  3. each result carries a breakdown of those factors so the interface can show why.
The weights are starting points from the action plan and are meant to be tested and tuned.
"""
import re
from datetime import date

WEIGHTS = {
    "sponsor": [  # a brand ranking dinners
        ("audience", "Audience fit", 30),
        ("interests", "Interest and lifestyle", 20),
        ("location", "Location", 15),
        ("vibe", "Event vibe and format", 15),
        ("budget", "Budget and slot fit", 10),
        ("engagement", "Engagement opportunity", 10),
    ],
    "host": [  # a host ranking brands
        ("brand", "Brand compatibility", 25),
        ("audience", "Audience alignment", 20),
        ("funding", "Funding contribution", 25),
        ("operations", "Operational feasibility", 15),
        ("experience", "Guest experience compatibility", 10),
        ("repeat", "Repeat partnership potential", 5),
    ],
}

VIBES = {
    "hip": ["hip", "cool", "stylish", "fashionable"],
    "trendy": ["trendy", "trending", "buzzy"],
    "cozy": ["cozy", "intimate", "warm", "homey"],
    "upscale": ["upscale", "fancy", "luxury", "elegant", "refined", "premium"],
    "casual": ["casual", "relaxed", "laid-back", "laid back"],
    "creative": ["creative", "artsy", "arty", "indie"],
    "late-night": ["late-night", "late night", "after-hours", "after hours"],
    "wellness": ["wellness", "healthy", "health", "mindful", "plant-based"],
    "family": ["family", "families", "kids"],
    "foodie": ["foodie", "foodies", "adventurous", "culinary"],
    "music": ["music", "jazz", "vinyl", "dj", "live music"],
    "community": ["community", "neighbors", "neighborhood"],
}
AUDIENCES = {
    "young-professionals": ["young professionals", "professionals", "20s", "30s", "millennial", "millennials", "gen z"],
    "creatives": ["creatives", "creative types", "designers", "artists", "makers"],
    "tech": ["tech", "startup", "startups", "founders", "engineers"],
    "families": ["families", "parents"],
    "fitness": ["fitness", "runners", "yoga", "gym", "active"],
    "foodies": ["foodies", "food lovers"],
    "students": ["students", "college", "grad students"],
    "couples": ["couples", "date night"],
}
INTEREST_WORDS = {
    "design": ["design", "designers", "architecture"], "art": ["art", "artists", "gallery"],
    "food culture": ["food", "foodies", "culinary", "chefs"], "music": ["music", "jazz", "dj", "vinyl"],
    "wellness": ["wellness", "mindful", "healthy", "plant-based"], "fitness": ["fitness", "runners", "yoga", "gym"],
    "tech": ["tech", "startup", "startups", "founders"], "sustainability": ["sustainable", "sustainability", "zero waste"],
    "nightlife": ["nightlife", "late night", "late-night", "bars"], "travel": ["travel", "travelers"],
    "fashion": ["fashion", "style"], "family": ["family", "families", "parents", "kids"],
}
PLACES = {
    "Williamsburg": ["williamsburg"], "Bushwick": ["bushwick"], "Park Slope": ["park slope"],
    "DUMBO": ["dumbo"], "Harlem": ["harlem"], "Astoria": ["astoria"],
}
BOROUGHS = {
    "brooklyn": ["Williamsburg", "Bushwick", "Park Slope", "DUMBO"],
    "manhattan": ["Harlem"],
    "queens": ["Astoria"],
}
SLOT_WORDS = {
    "menu": ["menu"], "table": ["table", "place setting"], "display": ["screen", "tv", "display", "logo"],
    "drink": ["drink", "cocktail", "welcome drink"], "gift": ["gift", "take-home", "goodie bag", "swag"],
    "title": ["title", "presenting"],
}


def _has(text, words):
    return any(re.search(r"(?<![a-z])" + re.escape(w) + r"(?![a-z])", text) for w in words)


def parse_brief(text):
    """Turn free text into tags we can match on."""
    t = (text or "").lower()
    out = {"vibes": [], "audiences": [], "interests": [], "places": [], "budget": None, "slot_types": []}
    for tag, words in VIBES.items():
        if _has(t, words):
            out["vibes"].append(tag)
    for tag, words in AUDIENCES.items():
        if _has(t, words):
            out["audiences"].append(tag)
    for tag, words in INTEREST_WORDS.items():
        if _has(t, words):
            out["interests"].append(tag)
    for place, words in PLACES.items():
        if _has(t, words):
            out["places"].append(place)
    for b, places in BOROUGHS.items():
        if re.search(r"\b" + b + r"\b", t):
            out["places"].extend(p for p in places if p not in out["places"])
    m = re.search(r"\$\s?([\d,]+(?:\.\d+)?)\s*(k)?", t)
    if m:
        n = float(m.group(1).replace(",", ""))
        out["budget"] = n * 1000 if m.group(2) else n
    for st, words in SLOT_WORDS.items():
        if _has(t, words):
            out["slot_types"].append(st)
    return out


def _overlap(want, have):
    want, have = set(want or []), set(have or [])
    if not want:
        return None, []
    hit = sorted(want & have)
    return len(hit) / len(want), hit


def _plural(n, word):
    return f"{n} {word}" + ("" if n == 1 else "s")


def _score(side, parts):
    """parts: {key: (score 0..1 or None, note)}. Factors with None were not asked about and are left out."""
    breakdown, num, den = [], 0.0, 0.0
    for key, label, w in WEIGHTS[side]:
        s, note = parts.get(key, (None, ""))
        breakdown.append({"key": key, "label": label, "weight": w,
                          "score": None if s is None else round(s * 100), "note": note})
        if s is not None:
            num += s * w
            den += w
    return (round(num / den * 100) if den else 50), breakdown


# ---------------------------------------------------------------------------
# Sponsor side: a brand describes who it wants to reach, we rank dinners.
# ---------------------------------------------------------------------------
def _passes_filters(ev, f):
    if not f:
        return True
    if f.get("borough") and ev["borough"].lower() != f["borough"].lower():
        return False
    if f.get("vibe") and f["vibe"] not in ev["vibes"]:
        return False
    if f.get("audience") and f["audience"] not in ev["audiences"]:
        return False
    if f.get("interest") and f["interest"] not in (ev.get("interests") or []):
        return False
    if f.get("format") and ev.get("format") != f["format"]:
        return False
    if f.get("age_group") and ev.get("age_group") != f["age_group"]:
        return False
    if f.get("min_guests") and ev["guests"] < int(f["min_guests"]):
        return False
    if f.get("max_guests") and ev["guests"] > int(f["max_guests"]):
        return False
    if f.get("within_days"):
        days = (date.fromisoformat(ev["date"]) - date.today()).days
        if days > int(f["within_days"]) or days < 0:
            return False
    return True


def rank_events(events, brief, sponsor=None, budget=None, slot_type=None, filters=None):
    want = parse_brief(brief)
    if budget is None:
        budget = want["budget"]
    types = [slot_type] if slot_type else want["slot_types"]
    results, hidden = [], {"filters": 0, "budget": 0, "category": 0, "capacity": 0, "excluded": 0}
    for ev in events:
        open_slots = [s for s in ev["slots"] if s["status"] == "open"]
        if types:
            open_slots = [s for s in open_slots if s["type"] in types]
        if not open_slots:
            continue
        # ---- hard constraints
        if not _passes_filters(ev, filters):
            hidden["filters"] += 1
            continue
        affordable = [s for s in open_slots if budget is None or s["price"] <= budget]
        if budget is not None and not affordable:
            hidden["budget"] += 1
            continue
        density = ev.get("density") or {}
        if sponsor:
            already_here = sponsor["id"] in density.get("sponsor_ids", [])
            if sponsor.get("cat") in (ev.get("excluded_cats") or []):
                hidden["excluded"] += 1
                continue
            if not already_here and sponsor.get("cat") in density.get("taken_cats", []):
                hidden["category"] += 1
                continue
            if not already_here and density.get("at_capacity"):
                hidden["capacity"] += 1
                continue

        # ---- soft factors (from the brief, or the brand profile when the brief is empty)
        implicit = not (want["vibes"] or want["audiences"] or want["places"] or want["interests"])
        src = sponsor if (implicit and sponsor) else None
        w_aud = src["audiences"] if src else want["audiences"]
        w_int = (src.get("interests") or []) if src else want["interests"]
        w_vib = src["vibes"] if src else want["vibes"]
        w_pla = src["places"] if src else want["places"]

        parts = {}
        a, a_hit = _overlap(w_aud, ev["audiences"])
        parts["audience"] = (a, ("Guests: " + ", ".join(a_hit)) if a_hit else ("No overlap with the guests you described" if a is not None else ""))
        i, i_hit = _overlap(w_int, ev.get("interests"))
        parts["interests"] = (i, ("Interests: " + ", ".join(i_hit)) if i_hit else ("Different interests" if i is not None else ""))
        if w_pla:
            in_area = ev["neighborhood"] in w_pla
            parts["location"] = (1.0 if in_area else 0.0,
                                 f"{ev['neighborhood']}, {ev['borough']}" + ("" if in_area else " is outside your area"))
        v, v_hit = _overlap(w_vib, ev["vibes"])
        if filters and filters.get("format"):
            v = 1.0 if v is None else (v + 1.0) / 2
        parts["vibe"] = (v, ("Vibe: " + ", ".join(v_hit)) if v_hit else ("Different vibe" if v is not None else ""))
        if budget is not None:
            share = len(affordable) / len(open_slots)
            parts["budget"] = (0.5 + share / 2, f"{_plural(len(affordable), 'slot')} within ${budget:,.0f}")
        else:
            parts["budget"] = (1.0, f"{_plural(len(open_slots), 'open slot')}, from ${min(s['price'] for s in open_slots):,.0f}")
        prefer = types or (sponsor.get("engagement") if sponsor else None) or []
        if prefer:
            have = {s["type"] for s in affordable or open_slots}
            hit = [t for t in prefer if t in have]
            parts["engagement"] = (len(hit) / len(prefer),
                                   ("Has the placements you prefer: " + ", ".join(hit)) if hit else "None of your preferred placements")
        score, breakdown = _score("sponsor", parts)

        reasons = [b["note"] for b in breakdown if b["score"] and b["note"]][:4]
        if implicit and sponsor:
            reasons.insert(0, "Ranked by your brand profile, since the description was empty")
        if not reasons:
            reasons.append("Open slots at this dinner")
        results.append({"event": ev, "score": score, "reasons": reasons, "breakdown": breakdown,
                        "matching_slot_ids": [s["id"] for s in affordable]})
    results.sort(key=lambda r: (-r["score"], r["event"]["date"]))
    return results, want, hidden


# ---------------------------------------------------------------------------
# Host side: a host picks one dinner, we rank brands for it.
# ---------------------------------------------------------------------------
def rank_sponsors(sponsors, event, club, guests, funding, notes="", history=None):
    """history: {sponsor_id: "club" | "platform"} for sponsors who already worked with this club or anywhere."""
    want = parse_brief(notes)
    history = history or {}
    wanted_vibes = list(dict.fromkeys(list(event["vibes"]) + want["vibes"]))
    wanted_ints = list(dict.fromkeys(list(event.get("interests") or []) + want["interests"]))
    open_slots = [s for s in event["slots"] if s["status"] == "open"]
    density = event.get("density") or {}
    pref, excl = event.get("preferred_cats") or [], event.get("excluded_cats") or []
    note_words = [w for w in re.findall(r"[a-z]{4,}", (notes or "").lower())]
    results, hidden = [], {"excluded": 0, "category": 0}
    for sp in sponsors:
        here = sp["id"] in density.get("sponsor_ids", [])
        if sp.get("cat") in excl:
            hidden["excluded"] += 1
            continue
        if not here and sp.get("cat") in density.get("taken_cats", []):
            hidden["category"] += 1
            continue

        parts = {}
        v, v_hit = _overlap(wanted_vibes, sp["vibes"])
        i, i_hit = _overlap(wanted_ints, sp.get("interests"))
        brand = [x for x in (v, i) if x is not None]
        b = sum(brand) / len(brand) if brand else 0.5
        text = f"{sp['name']} {sp['category']} {sp['blurb']}".lower()
        note_hit = [w for w in dict.fromkeys(note_words) if w in text]
        if sp.get("cat") in pref or note_hit:
            b = min(1.0, b + 0.25)
        bits = []
        if sp.get("cat") in pref:
            bits.append("a category you prefer")
        if v_hit:
            bits.append("vibe " + ", ".join(v_hit[:2]))
        if i_hit:
            bits.append("interests " + ", ".join(i_hit[:2]))
        if note_hit:
            bits.append("mentioned in your notes")
        parts["brand"] = (b, ("Fits on " + "; ".join(bits)) if bits else "Little in common with your dinner")

        a, a_hit = _overlap(event["audiences"], sp["audiences"])
        parts["audience"] = (a, ("Wants your guests: " + ", ".join(a_hit)) if a_hit else "Targets different guests")

        fits = sorted([s for s in open_slots if s["price"] <= sp["budget_max"]], key=lambda s: -s["price"])
        suggested = fits[0] if fits else None
        if suggested and funding:
            parts["funding"] = (min(1.0, suggested["price"] / funding),
                                f"{suggested['title']} at ${suggested['price']:,.0f} covers {min(100, round(suggested['price'] / funding * 100))}% of the gap")
        elif suggested:
            parts["funding"] = (1.0, f"Can afford {suggested['title']}")
        else:
            parts["funding"] = (0.0, f"Budget tops out at ${sp['budget_max']:,.0f}, below your open slots")

        if sp["min_guests"] <= guests <= sp["max_guests"]:
            g = 1.0
        else:
            gap = (sp["min_guests"] - guests) if guests < sp["min_guests"] else (guests - sp["max_guests"])
            g = max(0.0, 1 - gap / max(sp["min_guests"], 1))
        in_area = event["neighborhood"] in sp["places"]
        parts["operations"] = ((g + (1.0 if in_area else 0.0)) / 2,
                               f"Usually {sp['min_guests']} to {sp['max_guests']} guests" + (f", already active in {event['neighborhood']}" if in_area else f", not yet active in {event['neighborhood']}"))

        likes = {s["type"] for s in open_slots} & set(sp.get("engagement") or [])
        exp = 0.7 + (0.3 if sp.get("cat") in pref else 0) - (0.2 if density.get("level") == "Heavy" else 0)
        parts["experience"] = (max(0.0, min(1.0, exp)),
                               ("Natural placements open: " + ", ".join(sorted(likes))) if likes else "Placement would need planning")
        h = history.get(sp["id"])
        parts["repeat"] = ({"club": 1.0, "platform": 0.5}.get(h, 0.0),
                           {"club": "Has sponsored your club before", "platform": "Has sponsored on Tablematch before"}.get(h, "New to Tablematch"))
        score, breakdown = _score("host", parts)
        reasons = [b["note"] for b in breakdown if b["score"] and b["note"]][:4]
        reasons.append(f"Typical budget ${sp['budget_min']:,.0f} to ${sp['budget_max']:,.0f}")
        results.append({"sponsor": sp, "score": score, "reasons": reasons, "breakdown": breakdown,
                        "suggested_slot": suggested})
    results.sort(key=lambda r: -r["score"])

    # How much of the remaining gap could the best matches cover, one slot each, within sponsor capacity?
    room = max(0, (density.get("max_sponsors") or 99) - len(density.get("sponsor_ids", [])))
    covered, used, package, cats = 0.0, set(), [], set()
    for r in results:
        if covered >= funding or len(package) >= room:
            break
        if r["sponsor"].get("cat") in cats:  # one brand per category
            continue
        budget_max = r["sponsor"]["budget_max"]
        options = sorted([x for x in open_slots if x["price"] <= budget_max and x["id"] not in used],
                         key=lambda x: -x["price"])
        if not options:
            continue
        s = options[0]
        used.add(s["id"])
        cats.add(r["sponsor"].get("cat"))
        covered += s["price"]
        package.append({"sponsor": r["sponsor"]["name"], "slot": s["title"], "price": s["price"]})
    return results, {"covered": covered, "needed": funding, "items": package, "room": room}, hidden
