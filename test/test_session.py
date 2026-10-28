#!/usr/bin/env python3
"""Session tests: abandoning a decision unblocks the wait.

Run:  python3 test/test_session.py
Standard library only. Uses temp dirs as fake project roots.
"""
import contextlib
import io
import json
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import hoist

FAILURES = []


def check(name, cond, detail=""):
    print(("PASS " if cond else "FAIL ") + name)
    if not cond:
        FAILURES.append(name + (" — " + detail if detail else ""))


def make_session(root):
    (root / ".hoist").mkdir(exist_ok=True)
    (root / ".hoist" / "plan.json").write_text(json.dumps({
        "task": "Add user accounts", "decisions": [
            {"id": "db", "title": "Pick a database", "mode": "ask"},
            {"id": "auth", "title": "Pick sign-in", "mode": "ask"}]}))
    (root / ".hoist" / "session.json").write_text(json.dumps({
        "task": "Add user accounts", "status": "ready", "drafted": ["db", "auth"],
        "total": 2, "profile_answers": {}, "answers": {},
        "outcomes": {"db": {"choice": "sqlite", "mode": "chosen", "record": "docs/decisions/0001-x.md"}}}))


def test_abandon_records_outcome():
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        make_session(root)
        ses = hoist.abandon_decision(root, "auth")
        check("abandon returns session state", bool(ses), repr(ses)[:100])
        out = json.loads((root / ".hoist" / "session.json").read_text())["outcomes"]["auth"]
        check("abandon stores abandoned mode", out.get("mode") == "abandoned", str(out))
        check("abandon keeps the choice empty", out.get("choice") is None, str(out))


def test_abandon_unknown_decision():
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        make_session(root)
        check("abandon unknown returns None", hoist.abandon_decision(root, "nope") is None)


def test_wait_reports_abandoned():
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        make_session(root)
        hoist.abandon_decision(root, "auth")
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            hoist.wait_session(root)
        text = out.getvalue()
        check("wait finishes on abandoned session", "HOIST: decided" in text, text[:200])
        check("wait tells the agent to ask in chat",
              "back to chat" in text, text[:600])


if __name__ == "__main__":
    test_abandon_records_outcome()
    test_abandon_unknown_decision()
    test_wait_reports_abandoned()
    print(f"\n{len(FAILURES)} failure(s)")
    for f in FAILURES:
        print("FAILED:", f)
    sys.exit(1 if FAILURES else 0)
