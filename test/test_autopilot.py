#!/usr/bin/env python3
"""Autopilot regression tests: the agent decides, Hoist records, records still bind.

Run:  python3 test/test_autopilot.py
Standard library only. Uses temp dirs as fake project roots and stubs the server
and the browser open, so nothing starts, opens, or calls Muse Spark.
"""
import contextlib
import io
import json
import os
import sys
import tempfile
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import hoist

FAILURES = []


def check(name, cond, detail=""):
    print(("PASS " if cond else "FAIL ") + name)
    if not cond:
        FAILURES.append(name + (" — " + detail if detail else ""))


def run_gate(payload):
    out = io.StringIO()  # stdout and stderr together: blocks go to stderr, notes to stdout
    with mock.patch("sys.stdin", io.StringIO(json.dumps(payload))), contextlib.redirect_stdout(out), \
            contextlib.redirect_stderr(out), \
            mock.patch.object(hoist, "ensure_server", return_value=False), mock.patch("webbrowser.open") as opened:
        code = hoist.gate()
    return code, out.getvalue(), opened.called


def test_autopilot():
    with tempfile.TemporaryDirectory() as d, mock.patch.dict(os.environ, {"HOIST_MODE": ""}):
        root = Path(d)
        (root / "package.json").write_text('{"name": "t", "dependencies": {"express": "^4"}}')
        check("default mode is ask", hoist.get_mode(root) == "ask")
        hoist.set_mode(root, "autopilot")
        check("mode is saved per project", hoist.get_mode(root) == "autopilot")

        code, out, _ = run_gate({"hook_event_name": "UserPromptSubmit", "prompt": "Add user accounts", "cwd": str(root)})
        check("prompt hook tells the agent about autopilot", code == 0 and "on autopilot" in out and " log " in out, out)

        code, out, opened = run_gate({"hook_event_name": "PreToolUse", "tool_name": "Bash",
                                      "tool_input": {"command": "npm install mongoose"}, "cwd": str(root)})
        recs = sorted((root / "docs" / "decisions").glob("*.md"))
        check("autopilot lets the install through", code == 0, out)
        check("autopilot opens no page", not opened)
        check("autopilot writes one record", len(recs) == 1, str(recs))
        text = recs[0].read_text() if recs else ""
        check("record says who decided", "deciders: Muse Code on autopilot" in text and "confidence: low" in text)
        check("record names the trigger", "`mongoose`" in text)
        dec = hoist.load_decisions(root)
        check("decision and record share an id", dec and recs and recs[0].name.startswith(dec[0]["id"] + "-"))

        code, out, _ = run_gate({"hook_event_name": "PreToolUse", "tool_name": "Bash",
                                 "tool_input": {"command": "npm install pg"}, "cwd": str(root)})
        check("a conflicting install is still blocked", code == 2)
        check("the block cites the autopilot record", "decided on autopilot" in out and "docs/decisions/0001-" in out, out)

        with contextlib.redirect_stdout(io.StringIO()) as o:
            hoist.log_decision("Choose sign-in", "Email and password", "it works on every device", "Email and password|Magic link", str(root))
        recs = sorted((root / "docs" / "decisions").glob("*.md"))
        check("log writes a second record", len(recs) == 2 and recs[1].name.startswith("0002-"), str(recs))
        check("log lists the other options", "2. Magic link" in recs[1].read_text())

        hoist.set_mode(root, "ask")
        code, out, _ = run_gate({"hook_event_name": "UserPromptSubmit", "prompt": "next", "cwd": str(root)})
        check("ask mode adds no autopilot note", "autopilot" not in out)


if __name__ == "__main__":
    test_autopilot()
    print(f"\n{len(FAILURES)} failure(s)")
    for f in FAILURES:
        print("FAILED:", f)
    sys.exit(1 if FAILURES else 0)
