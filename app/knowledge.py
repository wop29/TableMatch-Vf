"""The knowledge source: placement proof guidelines (knowledge/placement_guidelines.md).

Context, not retrieval. The whole guide is about 470 words, so no search index is needed. Each vision call
gets the "general" section plus the ONE section for the placement the sponsor bought, looked up by slot type.
A keyed lookup is deterministic: the same slot always gets the same text, which keeps evals reproducible and
stops rules for other placements (say, "a screen counts" for display) from leaking into a menu check.
Move to retrieval only if the guide grows past what fits comfortably in a prompt (for example, per-venue rules).
"""
import hashlib
import re
from functools import lru_cache
from pathlib import Path

PATH = Path(__file__).resolve().parent.parent / "knowledge" / "placement_guidelines.md"


@lru_cache(maxsize=1)
def sections():
    text = PATH.read_text()
    parts = re.split(r"^## (\w+)\s*$", text, flags=re.M)
    return {parts[i]: parts[i + 1].strip() for i in range(1, len(parts), 2)}


def version():
    return hashlib.sha256(PATH.read_bytes()).hexdigest()[:12]


def guideline(slot_type):
    """General rules + the section for this placement type. Unknown types get the general rules only."""
    s = sections()
    out = "General rules:\n" + s["general"]
    if slot_type in s:
        out += f"\n\nRules for this placement ({slot_type}):\n" + s[slot_type]
    return out
