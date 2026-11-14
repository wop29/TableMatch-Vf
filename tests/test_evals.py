"""Unit tests for the eval graders, so a broken grader cannot hide a broken system.  python -m pytest -q tests/test_evals.py"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "evals"))
import graders as G  # noqa: E402


def test_brief_grader_counts_misses_and_allowed_extras():
    case = {"expected": {"vibes": ["cozy"], "audiences": [], "interests": [], "places": ["Astoria"], "budget": 500,
                         "slot_types": []}, "allow": {"interests": ["art"]}}
    out = {"vibes": ["cozy", "hip"], "audiences": [], "interests": ["art"], "places": [], "budget": 500, "slot_types": []}
    s, notes = G.grade_brief(case, out)
    assert not s["exact"] and s["counts"]["vibes"] == (1, 1, 0) and s["counts"]["places"] == (0, 0, 1)
    assert s["counts"]["interests"] == (0, 0, 0)  # allowed extra is not an error


def test_ndcg_perfect_and_empty():
    assert G.ndcg_at_k(["a", "b"], {"a": 2, "b": 1}) == 1.0
    assert G.ndcg_at_k(["x"], {"a": 2}) == 0.0


def test_vision_grader_flags_false_verify_and_bad_schema():
    case = {"expected": {"brand_matches": False, "decision": "not_verified"}}
    raw = {"logo_visible": True, "brand_matches": True, "placement_matches": True, "confidence": 0.9, "notes": "ok"}
    s, _ = G.grade_vision(case, raw, "verified")
    assert s["false_verify"] and not s["fields_ok"] and s["schema_ok"]
    s, _ = G.grade_vision(case, None, "not_verified")
    assert not s["schema_ok"] and not s["false_verify"]


def test_route_grader_marks_unsafe_auto_verify():
    s, notes = G.grade_route({"expected": {"decision": "needs_review"}}, "low", "verified", 10)
    assert s["unsafe_auto_verify"] and not s["correct"]


def test_photo_grader_outcomes():
    assert G.grade_photo({"expected": {"pass": False}}, True)[0]["outcome"] == "fp"
    assert G.grade_photo({"expected": {"pass": True}}, False)[0]["outcome"] == "fn"
