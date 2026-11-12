"""Tiny SQLite layer. One file, no ORM, easy to read and to swap for Postgres later."""
import json
import os
import sqlite3
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DB_PATH = Path(os.environ.get("HL_DB", ROOT / "data" / "marketplace.db"))
UPLOADS = Path(os.environ.get("HL_UPLOADS", ROOT / "data" / "uploads"))

SCHEMA = """
CREATE TABLE IF NOT EXISTS settings (key TEXT PRIMARY KEY, value TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS sponsors (
  id INTEGER PRIMARY KEY, name TEXT, category TEXT, blurb TEXT,
  vibes TEXT, audiences TEXT, places TEXT,
  budget_min REAL, budget_max REAL, min_guests INTEGER, max_guests INTEGER, color TEXT,
  cat TEXT, interests TEXT, age_groups TEXT, engagement TEXT
);
CREATE TABLE IF NOT EXISTS clubs (
  id INTEGER PRIMARY KEY, name TEXT, host_name TEXT, neighborhood TEXT, borough TEXT,
  blurb TEXT, vibes TEXT, audiences TEXT
);
CREATE TABLE IF NOT EXISTS events (
  id INTEGER PRIMARY KEY, club_id INTEGER, title TEXT, date TEXT, venue TEXT,
  neighborhood TEXT, borough TEXT, guests INTEGER, funding_needed REAL,
  vibes TEXT, audiences TEXT, description TEXT, cover TEXT,
  format TEXT, interests TEXT, age_group TEXT, total_cost REAL, ticket_price REAL, max_sponsors INTEGER,
  preferred_cats TEXT, excluded_cats TEXT
);
CREATE TABLE IF NOT EXISTS slots (
  id INTEGER PRIMARY KEY, event_id INTEGER, type TEXT, title TEXT, specs TEXT,
  price REAL, photos_required INTEGER DEFAULT 1, status TEXT DEFAULT 'open'
);
CREATE TABLE IF NOT EXISTS offers (
  id INTEGER PRIMARY KEY, slot_id INTEGER, sponsor_id INTEGER, from_side TEXT,
  amount REAL, message TEXT, status TEXT DEFAULT 'pending', created TEXT
);
CREATE TABLE IF NOT EXISTS orders (
  id INTEGER PRIMARY KEY, slot_id INTEGER, sponsor_id INTEGER, offer_id INTEGER,
  source TEXT, price REAL, fee REAL, net REAL, status TEXT, note TEXT,
  created TEXT, paid_at TEXT, released_at TEXT
);
CREATE TABLE IF NOT EXISTS proofs (
  id INTEGER PRIMARY KEY, order_id INTEGER, created TEXT, mode TEXT, decision TEXT,
  confidence REAL, checks TEXT, notes TEXT, photos TEXT, ai_cost REAL, reviewer_note TEXT
);
CREATE TABLE IF NOT EXISTS feedback (
  id INTEGER PRIMARY KEY, ts TEXT, role TEXT, rating INTEGER, message TEXT, page TEXT
);
CREATE TABLE IF NOT EXISTS searches (id INTEGER PRIMARY KEY, ts TEXT, side TEXT, results INTEGER);
CREATE TABLE IF NOT EXISTS ledger (
  id INTEGER PRIMARY KEY, order_id INTEGER, ts TEXT, kind TEXT, amount REAL, note TEXT
);
"""

JSON_FIELDS = {"vibes", "audiences", "places", "checks", "photos", "interests", "age_groups", "engagement",
               "preferred_cats", "excluded_cats"}


def conn():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    c = sqlite3.connect(DB_PATH)
    c.row_factory = sqlite3.Row
    return c


def _decode(row):
    d = dict(row)
    for k in JSON_FIELDS:
        if k in d and isinstance(d[k], str):
            try:
                d[k] = json.loads(d[k])
            except ValueError:
                pass
    return d


def q(sql, args=()):
    c = conn()
    try:
        return [_decode(r) for r in c.execute(sql, args).fetchall()]
    finally:
        c.close()


def one(sql, args=()):
    rows = q(sql, args)
    return rows[0] if rows else None


def run(sql, args=()):
    c = conn()
    try:
        cur = c.execute(sql, args)
        c.commit()
        return cur.lastrowid
    finally:
        c.close()


def insert(table, **fields):
    cols = ", ".join(fields)
    marks = ", ".join("?" for _ in fields)
    vals = [json.dumps(v) if isinstance(v, (list, dict)) else v for v in fields.values()]
    return run(f"INSERT INTO {table} ({cols}) VALUES ({marks})", vals)


def update(table, id_, **fields):
    sets = ", ".join(f"{k}=?" for k in fields)
    vals = [json.dumps(v) if isinstance(v, (list, dict)) else v for v in fields.values()]
    run(f"UPDATE {table} SET {sets} WHERE id=?", [*vals, id_])


def init():
    c = conn()
    try:
        c.executescript(SCHEMA)
        # older databases were created before covers existed
        add = {"events": ["cover TEXT", "format TEXT", "interests TEXT", "age_group TEXT", "total_cost REAL",
                          "ticket_price REAL", "max_sponsors INTEGER", "preferred_cats TEXT", "excluded_cats TEXT"],
               "sponsors": ["cat TEXT", "interests TEXT", "age_groups TEXT", "engagement TEXT"]}
        for table, defs in add.items():
            cols = [r["name"] for r in c.execute(f"PRAGMA table_info({table})").fetchall()]
            for d in defs:
                if d.split()[0] not in cols:
                    c.execute(f"ALTER TABLE {table} ADD COLUMN {d}")
        c.commit()
    finally:
        c.close()


def wipe():
    c = conn()
    try:
        for t in ("settings", "sponsors", "clubs", "events", "slots", "offers", "orders", "proofs", "ledger", "searches"):
            c.execute(f"DROP TABLE IF EXISTS {t}")
        c.commit()
    finally:
        c.close()
    init()


# settings ---------------------------------------------------------------
DEFAULT_SETTINGS = {
    "fee_rate": 0.30,          # placeholder from the meeting: 30%
    "fee_cap": 3000.0,         # placeholder from the meeting: capped at $3,000 per transaction
    "ai_cost_per_photo": 0.02, # placeholder: image checks cost about the same per photo, whatever the deal size
    "auto_verify_confidence": 0.80,
}


def get_settings():
    out = dict(DEFAULT_SETTINGS)
    for r in q("SELECT key, value FROM settings"):
        try:
            out[r["key"]] = float(r["value"])
        except ValueError:
            out[r["key"]] = r["value"]
    return out


def set_setting(key, value):
    run("INSERT INTO settings(key, value) VALUES(?, ?) ON CONFLICT(key) DO UPDATE SET value=excluded.value",
        (key, str(value)))
