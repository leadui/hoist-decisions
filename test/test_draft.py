#!/usr/bin/env python3
"""Draft-contract tests: lean checks, deep checks, and the deep merge.

Run:  python3 test/test_draft.py
Standard library only. All fixtures use empty docs_url so no network happens.
"""
import sys
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import hoist

FAILURES = []


def check(name, cond, detail=""):
    print(("PASS " if cond else "FAIL ") + name)
    if not cond:
        FAILURES.append(name + (" — " + detail if detail else ""))


def opt(id, **kw):
    o = {"id": id, "name": id.title() + " store", "plain_name": "plain words here",
         "analogy": "like shelves in a shop", "story": {"now": "fine this week", "later": "costly in six months"},
         "journey": ["you save a note", "the app writes it", "the store keeps it", "reads come back fast"],
         "numbers": [["Reads", "thousands a second"], ["Writers", "one at a time"]],
         "micro": 2, "trajectory": [3, 8],
         "summary": "a store", "good": [{"when": "now", "text": "easy to start"}],
         "bad": [{"when": "later", "text": "hard to move"}],
         "learn": {"what": "it keeps things", "living_with": "you tend it", "terms": [], "docs_url": ""}}
    o.update(kw)
    return o


def draft(**kw):
    d = {"question": "Where should the notes live?", "analogy": "like shelves in a shop",
         "micro_label": "upkeep burden", "growth": {"title": "Headroom", "now": "today", "later": "at 10x"},
         "options": [opt("a"), opt("b")], "default_option": "a", "agent_pick": "", "questions": []}
    d.update(kw)
    return d


def lean_draft(**kw):
    d = draft(**kw)
    d.pop("growth", None)
    for o in d["options"]:
        for k in ("numbers", "trajectory", "learn", "check_current"):
            o.pop(k, None)
    return d


def lean(**kw):
    l = {"why": "it stays boring while the project grows",
         "assumptions": ["you would rather pay a little than babysit servers"],
         "flips": ["the notes must live on your own machines"]}
    l.update(kw)
    return l


def problems(d):
    with mock.patch.object(hoist, "link_ok", lambda url: True):
        return hoist.check_draft(d)


def deep_problems(d):
    with mock.patch.object(hoist, "link_ok", lambda url: True):
        return hoist.check_deep(d)


def test_valid_plain_draft_passes():
    check("plain draft passes", problems(draft()) == [], str(problems(draft())))


def test_valid_lean_draft_passes():
    d = draft(agent_pick="a", lean=lean())
    check("lean draft passes", problems(d) == [], str(problems(d)))


def test_lean_without_deep_fields_passes():
    check("lean draft without deep fields passes", problems(lean_draft()) == [], str(problems(lean_draft())))


def test_old_draft_without_lean_passes():
    check("draft without lean still passes", problems(draft(agent_pick="a")) == [])


def test_unknown_agent_pick_fails():
    ps = problems(draft(agent_pick="zzz"))
    check("unknown agent_pick fails", any("zzz" in p for p in ps), str(ps))


def test_lean_without_pick_fails():
    ps = problems(draft(lean=lean()))
    check("lean without agent_pick fails", len(ps) > 0, str(ps))


def test_empty_lean_why_fails():
    ps = problems(draft(agent_pick="a", lean=lean(why="")))
    check("empty lean why fails", len(ps) > 0, str(ps))


def test_too_many_assumptions_fails():
    ps = problems(draft(agent_pick="a", lean=lean(assumptions=["one", "two", "three", "four"])))
    check("4 assumptions fail", len(ps) > 0, str(ps))


def test_vendor_in_assumption_fails():
    ps = problems(draft(agent_pick="a", lean=lean(assumptions=["you already use neon for everything"])))
    check("vendor in assumption fails", any("neon" in p for p in ps), str(ps))


def test_too_many_flips_fails():
    ps = problems(draft(agent_pick="a", lean=lean(flips=["one", "two", "three"])))
    check("3 flips fail", len(ps) > 0, str(ps))


def test_empty_assumption_fails():
    ps = problems(draft(agent_pick="a", lean=lean(assumptions=[""])))
    check("empty assumption fails", len(ps) > 0, str(ps))


def test_missing_journey_fails():
    d = draft()
    d["options"][0]["journey"] = ["only", "two"]
    ps = problems(d)
    check("short journey fails", any("journey" in p for p in ps), str(ps))


def test_micro_out_of_range_fails():
    ps = problems(draft(options=[opt("a", micro=11), opt("b")]))
    check("micro 11 fails", any("micro" in p for p in ps), str(ps))


def test_missing_micro_label_fails():
    ps = problems(draft(micro_label=""))
    check("empty micro_label fails", any("micro_label" in p for p in ps), str(ps))


def test_deep_valid_passes():
    check("full draft passes deep check", deep_problems(draft()) == [], str(deep_problems(draft())))


def test_deep_lean_only_fails():
    ps = deep_problems(lean_draft())
    check("lean-only draft fails deep check", len(ps) > 0, str(ps))


def test_deep_bad_trajectory_fails():
    ps = deep_problems(draft(options=[opt("a", trajectory=[3]), opt("b")]))
    check("short trajectory fails deep", any("trajectory" in p for p in ps), str(ps))


def test_deep_malformed_numbers_fail():
    ps = deep_problems(draft(options=[opt("a", numbers=[["only-label"]]), opt("b")]))
    check("malformed numbers fail deep", any("number" in p for p in ps), str(ps))


def test_deep_missing_growth_fails():
    d = draft()
    d.pop("growth")
    ps = deep_problems(d)
    check("missing growth fails deep", any("growth" in p for p in ps), str(ps))


def test_deep_missing_learn_fails():
    d = draft()
    d["options"][0].pop("learn")
    ps = deep_problems(d)
    check("missing learn fails deep", any("plain explanation" in p for p in ps), str(ps))


def test_merge_deep_folds_payload():
    base = lean_draft()
    payload = {"growth": {"title": "Headroom", "now": "today", "later": "at 10x"},
               "deep_options": [{"id": "a", "numbers": [["Reads", "lots"]], "trajectory": [3, 8],
                                 "learn": {"what": "it keeps things"}, "check_current": ""},
                                {"id": "zzz", "numbers": [["X", "y"]]}]}
    merged = hoist.merge_deep(base, payload)
    a = [o for o in merged["options"] if o["id"] == "a"][0]
    check("merge marks deep", merged.get("deep") is True, str(merged.get("deep")))
    check("merge folds growth", (merged.get("growth") or {}).get("title") == "Headroom")
    check("merge folds option deep fields", a.get("numbers") == [["Reads", "lots"]] and a.get("trajectory") == [3, 8])
    check("merge ignores unknown ids", all(o["id"] != "zzz" for o in merged["options"]))
    check("merge leaves the lean untouched", "numbers" not in base["options"][0] and base.get("deep") is None)


if __name__ == "__main__":
    test_valid_plain_draft_passes()
    test_valid_lean_draft_passes()
    test_lean_without_deep_fields_passes()
    test_old_draft_without_lean_passes()
    test_unknown_agent_pick_fails()
    test_lean_without_pick_fails()
    test_empty_lean_why_fails()
    test_too_many_assumptions_fails()
    test_vendor_in_assumption_fails()
    test_too_many_flips_fails()
    test_empty_assumption_fails()
    test_missing_journey_fails()
    test_micro_out_of_range_fails()
    test_missing_micro_label_fails()
    test_deep_valid_passes()
    test_deep_lean_only_fails()
    test_deep_bad_trajectory_fails()
    test_deep_malformed_numbers_fail()
    test_deep_missing_growth_fails()
    test_deep_missing_learn_fails()
    test_merge_deep_folds_payload()
    print(f"\n{len(FAILURES)} failure(s)")
    for f in FAILURES:
        print("FAILED:", f)
    sys.exit(1 if FAILURES else 0)
