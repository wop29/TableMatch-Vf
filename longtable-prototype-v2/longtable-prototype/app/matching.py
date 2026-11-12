"""Matching in both directions over the curated demo list. No internet search.

It is deliberately rule-based so the results are explainable: every match comes with its reasons.
An LLM could replace parse_brief() later without changing anything else.
"""
import re

VIBES = {
    "hip": ["hip", "cool", "stylish", "fashionable"],
    "trendy": ["trendy", "trending", "buzzy"],
    "cozy": ["cozy", "intimate", "warm", "homey"],
    "upscale": ["upscale", "fancy", "luxury", "elegant", "refined", "premium"],
    "casual": ["casual", "relaxed", "laid-back", "laid back"],
    "creative": ["creative", "artsy", "arty", "design", "indie"],
    "late-night": ["late-night", "late night", "after-hours", "after hours", "nightlife"],
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
    out = {"vibes": [], "audiences": [], "places": [], "budget": None, "slot_types": []}
    for tag, words in VIBES.items():
        if _has(t, words):
            out["vibes"].append(tag)
    for tag, words in AUDIENCES.items():
        if _has(t, words):
            out["audiences"].append(tag)
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
    want, have = set(want), set(have)
    if not want:
        return None, []
    hit = sorted(want & have)
    return len(hit) / len(want), hit


def _blend(parts):
    """parts: list of (score or None, weight). Ignores dimensions that were not asked about."""
    live = [(s, w) for s, w in parts if s is not None]
    if not live:
        return 0.5
    return sum(s * w for s, w in live) / sum(w for _, w in live)


def _plural(n, word):
    return f"{n} {word}" + ("" if n == 1 else "s")


# ---------------------------------------------------------------------------
# Sponsor side: a brand describes who it wants to reach, we rank dinners.
# ---------------------------------------------------------------------------
def rank_events(events, brief, sponsor=None, budget=None, slot_type=None):
    want = parse_brief(brief)
    if budget is None:
        budget = want["budget"]
    types = [slot_type] if slot_type else want["slot_types"]
    results = []
    for ev in events:
        open_slots = [s for s in ev["slots"] if s["status"] == "open"]
        if types:
            open_slots = [s for s in open_slots if s["type"] in types]
        if not open_slots:
            continue
        affordable = [s for s in open_slots if budget is None or s["price"] <= budget]
        if budget is not None and not affordable:
            continue

        v_score, v_hit = _overlap(want["vibes"], ev["vibes"])
        a_score, a_hit = _overlap(want["audiences"], ev["audiences"])
        if want["places"]:
            p_score = 1.0 if ev["neighborhood"] in want["places"] else 0.0
        else:
            p_score = None
        implicit = False
        if v_score is None and a_score is None and p_score is None and sponsor:
            # Nothing typed: fall back to the sponsor's own profile.
            v_score, v_hit = _overlap(sponsor["vibes"], ev["vibes"])
            a_score, a_hit = _overlap(sponsor["audiences"], ev["audiences"])
            p_score = 1.0 if ev["neighborhood"] in sponsor["places"] else 0.0
            implicit = True
        b_score = None
        if budget is not None:
            b_score = 1.0
        score = _blend([(v_score, 0.4), (a_score, 0.3), (p_score, 0.2), (b_score, 0.1)])

        reasons = []
        if v_hit:
            reasons.append("Vibe: " + ", ".join(v_hit))
        if a_hit:
            reasons.append("Guests: " + ", ".join(a_hit))
        if p_score == 1.0:
            reasons.append(f"Location: {ev['neighborhood']}, {ev['borough']}")
        if budget is not None:
            reasons.append(f"{_plural(len(affordable), 'slot')} within ${budget:,.0f}")
        if implicit:
            reasons.insert(0, "Based on your brand profile, since the brief was empty")
        if not reasons:
            reasons.append("Open slots at this dinner")
        results.append({"event": ev, "score": round(score * 100), "reasons": reasons,
                        "matching_slot_ids": [s["id"] for s in affordable]})
    results.sort(key=lambda r: (-r["score"], r["event"]["date"]))
    return results, want


# ---------------------------------------------------------------------------
# Host side: a host gives guests and funding for one dinner, we rank sponsors.
# ---------------------------------------------------------------------------
def rank_sponsors(sponsors, event, club, guests, funding, notes=""):
    want = parse_brief(notes)
    wanted_vibes = list(dict.fromkeys(list(event["vibes"]) + want["vibes"]))
    wanted_auds = list(dict.fromkeys(list(event["audiences"]) + want["audiences"]))
    open_slots = [s for s in event["slots"] if s["status"] == "open"]
    note_words = [w for w in re.findall(r"[a-z]{4,}", (notes or "").lower())]
    results = []
    for sp in sponsors:
        v_score, v_hit = _overlap(wanted_vibes, sp["vibes"])
        a_score, a_hit = _overlap(wanted_auds, sp["audiences"])
        in_area = event["neighborhood"] in sp["places"]
        # Guest count: inside the sponsor's usual range is a full match, outside loses points.
        if sp["min_guests"] <= guests <= sp["max_guests"]:
            g_score = 1.0
        else:
            gap = (sp["min_guests"] - guests) if guests < sp["min_guests"] else (guests - sp["max_guests"])
            g_score = max(0.0, 1 - gap / max(sp["min_guests"], 1))
        # Budget: can this sponsor cover what the host needs?
        b_score = min(1.0, sp["budget_max"] / funding) if funding else 1.0
        score = _blend([(v_score, 0.3), (a_score, 0.25), (1.0 if in_area else 0.0, 0.15),
                        (g_score, 0.1), (b_score, 0.2)])
        text = f"{sp['name']} {sp['category']} {sp['blurb']}".lower()
        note_hit = [w for w in dict.fromkeys(note_words) if w in text]
        if note_hit:
            score = min(1.0, score + 0.05)

        # Pick the most valuable open slot this sponsor can afford.
        fits = [s for s in open_slots if s["price"] <= sp["budget_max"]]
        fits.sort(key=lambda s: -s["price"])
        suggested = fits[0] if fits else None

        reasons = []
        if v_hit:
            reasons.append("Shares your vibe: " + ", ".join(v_hit[:3]))
        if a_hit:
            reasons.append("Wants your guests: " + ", ".join(a_hit[:3]))
        if in_area:
            reasons.append(f"Already targets {event['neighborhood']}")
        if sp["min_guests"] <= guests <= sp["max_guests"]:
            reasons.append(f"Usual reach is {sp['min_guests']} to {sp['max_guests']} guests")
        else:
            reasons.append(f"Usually sponsors {sp['min_guests']} to {sp['max_guests']} guests, you have {guests}")
        reasons.append(f"Typical budget ${sp['budget_min']:,.0f} to ${sp['budget_max']:,.0f}")
        if note_hit:
            reasons.append("Mentioned in your notes: " + ", ".join(note_hit[:3]))
        results.append({"sponsor": sp, "score": round(score * 100), "reasons": reasons,
                        "suggested_slot": suggested})
    results.sort(key=lambda r: -r["score"])

    # How much of the funding need could the best matches cover, one slot each?
    covered, used = 0.0, set()
    package = []
    for r in results:
        s = r["suggested_slot"]
        if not s or s["id"] in used or covered >= funding:
            continue
        used.add(s["id"])
        covered += s["price"]
        package.append({"sponsor": r["sponsor"]["name"], "slot": s["title"], "price": s["price"]})
        if len(package) == 4:
            break
    return results, {"covered": covered, "needed": funding, "items": package}
