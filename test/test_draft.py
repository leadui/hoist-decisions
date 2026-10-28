#!/usr/bin/env python3
"""Draft-contract tests: check_draft accepts good drafts and rejects bad ones.

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
         "summary": "a store", "good": [{"when": "now", "text": "easy to start"}],
         "bad": [{"when": "later", "text": "hard to move"}],
         "learn": {"what": "it keeps things", "living_with": "you tend it", "terms": [], "docs_url": ""}}
    o.update(kw)
    return o


def draft(**kw):
    d = {"question": "Where should the notes live?", "analogy": "like shelves in a shop",
         "options": [opt("a"), opt("b")], "default_option": "a", "agent_pick": "", "questions": []}
    d.update(kw)
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


def test_valid_plain_draft_passes():
    check("plain draft passes", problems(draft()) == [], str(problems(draft())))


def test_valid_lean_draft_passes():
    d = draft(agent_pick="a", lean=lean())
    check("lean draft passes", problems(d) == [], str(problems(d)))


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


if __name__ == "__main__":
    test_valid_plain_draft_passes()
    test_valid_lean_draft_passes()
    test_old_draft_without_lean_passes()
    test_unknown_agent_pick_fails()
    test_lean_without_pick_fails()
    test_empty_lean_why_fails()
    test_too_many_assumptions_fails()
    test_vendor_in_assumption_fails()
    test_too_many_flips_fails()
    test_empty_assumption_fails()
    print(f"\n{len(FAILURES)} failure(s)")
    for f in FAILURES:
        print("FAILED:", f)
    sys.exit(1 if FAILURES else 0)
