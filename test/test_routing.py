#!/usr/bin/env python3
"""Routing-path regression tests: solo routing question -> PostToolBatch -> session + wait.

Run:  python3 test/test_routing.py
Needs nothing but the standard library and this repo. Uses temp dirs as fake
project roots and stubs the server, the session POST, and the browser open, so
no network, no browser, and no Muse Spark calls happen.

The PostToolBatch payload shape below is the logged live shape: tool_response
arrives as a JSON string holding {"answers": [...]}.
"""
import contextlib
import io
import json
import sys
import tempfile
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import hoist

# These tests cover the Muse Spark drafter (with a key). The default, agent drafting, is in test_agent_draft.py.
hoist.effective_drafter = lambda root: "muse"

ROOT = Path(__file__).resolve().parent.parent
FIXTURE = ROOT / "test" / "fixtures" / "post_tool_batch_hoist_pick.json"

FAILURES = []


def check(name, cond, detail=""):
    print(("PASS " if cond else "FAIL ") + name)
    if not cond:
        FAILURES.append(name + (" — " + detail if detail else ""))


def routing_payload(pick, root, multi=False, recommended=False, response=None):
    """A PostToolBatch payload for the skill's solo routing question."""
    label = pick + (" (Recommended)" if recommended else "")
    question = {"id": "q0", "header": "Decide",
                "question": "The database and the sign-in method are hard to change later. How do you want to decide?",
                "selection": {"mode": "multiple" if multi else "single"},
                "options": [{"label": "Answer here", "description": "Quick: I'll ask you the questions now."},
                            {"label": "Decide with Hoist instead",
                             "description": "Opens a page that explains each option in plain words and records your choice."}]}
    if response is None:
        answer = {"id": "q0", ("selected_labels" if multi else "selected_label"): ([label] if multi else label)}
        response = json.dumps({"answers": [answer]})
    return {"hook_event_name": "PostToolBatch", "cwd": str(root),
            "tool_calls": [{"tool_name": "request_user_input",
                            "tool_input": {"questions": [question]},
                            "tool_response": response}]}


def run_gate(payload):
    """Feed a payload to gate() with server POSTs and browser stubbed. Returns (rc, stdout, calls)."""
    calls = {}
    out = io.StringIO()
    with mock.patch.object(hoist, "ensure_server", lambda root: calls.setdefault("server", root) or True), \
         mock.patch.object(hoist, "post_session", lambda task, hints="": calls.setdefault("session", (task, hints)) or True), \
         mock.patch.object(hoist.webbrowser, "open", lambda url: calls.setdefault("browser", url)), \
         mock.patch.object(hoist.sys, "stdin", io.StringIO(json.dumps(payload))), \
         contextlib.redirect_stdout(out):
        rc = hoist.gate()
    return rc, out.getvalue(), calls


def test_live_sequence():
    """The proven live path: prompt saved, Hoist pick starts a session and tells the agent to wait."""
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        prompt = {"hook_event_name": "UserPromptSubmit", "cwd": str(root),
                  "prompt": "Add user accounts with saved projects. Use MongoDB."}
        with mock.patch.object(hoist.sys, "stdin", io.StringIO(json.dumps(prompt))), \
             contextlib.redirect_stdout(io.StringIO()):
            check("prompt-submit returns 0", hoist.gate() == 0)
        check("prompt-submit saves last_task.txt",
              (root / ".hoist" / "last_task.txt").read_text().startswith("Add user accounts"))
        rc, out, calls = run_gate(routing_payload("Decide with Hoist instead", root))
        check("hoist pick returns 0", rc == 0)
        check("hoist pick starts the server for this project", calls.get("server") == root, str(calls))
        task, hints = calls.get("session", ("", ""))
        check("session posts the saved task", task.startswith("Add user accounts"), repr(task))
        check("session posts the agent question as hints", "hard to change later" in hints, repr(hints))
        check("page opens on the session view", (calls.get("browser") or "").endswith("/#/session"), str(calls))
        check("agent is told to run hoist wait", "Run `python3" in out and " wait` now" in out, out.strip()[:200])


def test_answer_here_is_silent():
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        rc, out, calls = run_gate(routing_payload("Answer here", root))
        check("answer-here returns 0", rc == 0)
        check("answer-here posts no session", "session" not in calls, str(calls))
        check("answer-here opens no page", "browser" not in calls, str(calls))


def test_multiselect_variant():
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        rc, _, calls = run_gate(routing_payload("Decide with Hoist instead", root, multi=True))
        check("multi-select hoist pick starts a session", "session" in calls, str(calls))


def test_recommended_suffix():
    """Muse marks the recommended option with a suffix; a Hoist pick must still match,
    and the suffix must not leak into the planner hints."""
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        rc, _, calls = run_gate(routing_payload("Decide with Hoist instead", root, recommended=True))
        check("recommended-suffixed hoist pick starts a session", "session" in calls, str(calls))
        _, hints = calls.get("session", ("", ""))
        check("hints carry no recommended suffix", "(Recommended)" not in hints, repr(hints))
        check("hints carry no hoist option", "Decide with Hoist instead" not in hints, repr(hints))


def test_server_down_falls_back_to_chat():
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        out = io.StringIO()
        with mock.patch.object(hoist, "ensure_server", lambda r: False), \
             mock.patch.object(hoist.sys, "stdin", io.StringIO(json.dumps(
                 routing_payload("Decide with Hoist instead", root)))), \
             contextlib.redirect_stdout(out):
            rc = hoist.gate()
        check("server-down returns 0", rc == 0)
        check("server-down falls back to chat", "in chat instead" in out.getvalue(), out.getvalue().strip()[:200])


def test_malformed_response_is_ignored():
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        rc, _, calls = run_gate(routing_payload("Decide with Hoist instead", root, response="not json{"))
        check("malformed tool_response returns 0", rc == 0)
        check("malformed tool_response posts no session", "session" not in calls, str(calls))


def test_unrelated_tool_is_silent():
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        payload = routing_payload("Decide with Hoist instead", root)
        payload["tool_calls"][0]["tool_name"] = "bash"
        rc, _, calls = run_gate(payload)
        check("non-questionnaire batch posts no session", "session" not in calls, str(calls))


def test_passthrough_when_nothing_matches():
    """A PreToolUse the catalog doesn't know passes through untouched."""
    with tempfile.TemporaryDirectory() as tmp:
        payload = {"hook_event_name": "PreToolUse", "cwd": str(tmp), "tool_name": "bash",
                   "tool_input": {"command": "ls node_modules"}}
        err = io.StringIO()
        with mock.patch.object(hoist.sys, "stdin", io.StringIO(json.dumps(payload))), \
             contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(err):
            rc = hoist.gate()
        check("unknown tool passes through", rc == 0 and err.getvalue() == "", f"rc={rc} err={err.getvalue()[:100]}")


def test_fixture_replays():
    """The checked-in PostToolBatch fixture replays the live shape end to end."""
    check("fixture exists", FIXTURE.exists(), str(FIXTURE))
    if not FIXTURE.exists():
        return
    with tempfile.TemporaryDirectory() as tmp:
        payload = json.loads(FIXTURE.read_text().replace("__ROOT__", str(tmp)))
        (Path(tmp) / ".hoist").mkdir(exist_ok=True)
        (Path(tmp) / ".hoist" / "last_task.txt").write_text("lets review my options for the design system")
        rc, _, calls = run_gate(payload)
        check("fixture hoist pick starts a session", "session" in calls, str(calls))


if __name__ == "__main__":
    test_live_sequence()
    test_answer_here_is_silent()
    test_multiselect_variant()
    test_recommended_suffix()
    test_server_down_falls_back_to_chat()
    test_malformed_response_is_ignored()
    test_unrelated_tool_is_silent()
    test_passthrough_when_nothing_matches()
    test_fixture_replays()
    print(f"\n{len(FAILURES)} failure(s)")
    for f in FAILURES:
        print("FAILED:", f)
    sys.exit(1 if FAILURES else 0)
