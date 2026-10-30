#!/usr/bin/env python3
"""Agent drafting (the default, no key): the hook starts a session, the agent drafts it through
`hoist brief` / `hoist submit`, Hoist checks every draft, and `hoist wait` only waits once it's all in.

Run:  python3 test/test_agent_draft.py
Standard library only. Temp project roots, no browser, no server, no Muse Spark calls. The agent's
output is played by the sample's real plan and drafts.
"""
import contextlib
import io
import json
import os
import sys
import tempfile
import threading
import urllib.error
import urllib.request
from http.server import ThreadingHTTPServer
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import hoist

ROOT = Path(__file__).resolve().parent.parent
FIXTURE = ROOT / "test" / "fixtures" / "post_tool_batch_hoist_pick.json"
SAMPLE = json.loads((ROOT / "site" / "sample.json").read_text())["sample_session"]

FAILURES = []


def check(name, cond, detail=""):
    print(("PASS " if cond else "FAIL ") + name)
    if not cond:
        FAILURES.append(name + (" — " + detail if detail else ""))


def run(fn, *a):
    """Call a CLI function; return (exit code, everything it printed)."""
    out = io.StringIO()
    code = 0
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(out):
        try:
            fn(*a)
        except SystemExit as e:
            code = e.code if isinstance(e.code, int) else 1
            if not isinstance(e.code, int) and e.code:
                out.write(str(e.code))
    return code, out.getvalue()


def test_agent_drafting():
    with tempfile.TemporaryDirectory() as d, mock.patch.dict(os.environ, {"HOIST_DRAFTER": ""}):
        root = Path(d)
        (root / ".hoist").mkdir()
        (root / ".hoist" / "last_task.txt").write_text(SAMPLE["task"])
        with mock.patch.object(hoist, "ensure_key", return_value=False):
            check("without a key the agent drafts", hoist.get_drafter(root) == "agent")
        with mock.patch.object(hoist, "ensure_key", return_value=True):
            check("with a key Muse Spark drafts", hoist.get_drafter(root) == "muse")
            hoist.set_config(root, "drafter", "agent")
            check("choosing the agent wins over the key", hoist.get_drafter(root) == "agent")
            (root / ".hoist" / "config.json").unlink()

        payload = json.loads(FIXTURE.read_text().replace("__ROOT__", str(root)))
        out = io.StringIO()
        with mock.patch("sys.stdin", io.StringIO(json.dumps(payload))), contextlib.redirect_stdout(out), \
                mock.patch.object(hoist, "ensure_key", return_value=False), \
                mock.patch.object(hoist, "ensure_server", return_value=True), mock.patch("webbrowser.open") as opened, \
                mock.patch.object(hoist, "post_session", side_effect=AssertionError("no Muse Spark session without a key")):
            hoist.gate()
        ses = hoist.load_session(root)
        check("picking Hoist starts an agent session", ses and ses.get("drafter") == "agent" and ses["status"] == "planning", str(ses))
        check("the page opens", opened.called)
        check("the agent is told to brief, then wait", " brief" in out.getvalue() and " wait" in out.getvalue(), out.getvalue())
        check("the agent is told to draft itself", "without a subagent" in out.getvalue())

        code, text = run(hoist.wait, None, str(root))
        check("wait refuses to block before the drafts are in", code == 1 and "brief" in text, text)

        code, text = run(hoist.brief, str(root))
        check("brief starts with the plan contract", "step 1" in text and "decisions" in text and "submit plan" in text, text[:200])
        check("brief carries the project input", "INPUT" in text and SAMPLE["task"] in text)

        work = root / ".hoist" / "agent"
        (work / "bad.json").write_text("not json at all")
        code, text = run(hoist.submit, "plan", [str(work / "bad.json")], str(root))
        check("a broken plan file is refused with a reason", code == 1 and "JSON" in text, text)

        (work / "plan.json").write_text("Here is the plan:\n```json\n" + json.dumps(SAMPLE["plan"]) + "\n```")
        code, text = run(hoist.submit, "plan", [str(work / "plan.json")], str(root))
        asks = [x["id"] for x in json.loads((root / ".hoist" / "plan.json").read_text())["decisions"] if x["mode"] == "ask"]
        check("the plan is accepted (fenced JSON is fine)", code == 0 and "accepted" in text and asks, text)

        code, text = run(hoist.submit, "draft", ["not-a-decision", str(work / "plan.json")], str(root))
        check("an unknown decision id is refused", code == 1 and "isn't one of" in text, text)

        for i, did in enumerate(asks):
            code, text = run(hoist.brief, str(root))
            check(f"brief asks for {did}", did in text and "submit draft" in text, text[-200:])
            f = work / f"{did}.json"
            f.write_text(json.dumps(SAMPLE["drafts"][did]))
            code, text = run(hoist.submit, "draft", [did, str(f)], str(root))
            if code == 1:  # the same one repair round Muse Spark gets
                check(f"{did}: problems come back as a list to fix", "- " in text, text)
                code, text = run(hoist.submit, "draft", [did, str(f)], str(root))
            check(f"{did} accepted", code == 0 and "accepted" in text, text)

        state = hoist.session_state(root)
        check("the session is ready for the page", state["status"] == "ready", state["status"])
        check("drafts are marked as the agent's", all(v.get("drafter") == "agent" for v in state["drafts"].values()))
        code, text = run(hoist.brief, str(root))
        check("brief says there is nothing left to draft", "wait" in text, text)


def test_wait_stays_off_the_network():
    """`hoist wait` runs in the agent's sandbox, where any network call stops for the person's approval."""
    with tempfile.TemporaryDirectory() as d:
        root = Path(d)
        (root / ".hoist").mkdir()
        (root / ".hoist" / "plan.json").write_text(json.dumps(SAMPLE["plan"]))
        asks = [x["id"] for x in SAMPLE["plan"]["decisions"] if x["mode"] == "ask"]
        hoist.save_session(root, {"task": "t", "status": "ready", "drafter": "agent", "drafted": asks, "total": len(asks), "failed": [],
                                  "outcomes": {a: {"mode": "default"} for a in asks}, "answers": {}, "profile_answers": {}})
        boom = AssertionError("hoist wait touched the network")
        with mock.patch("urllib.request.urlopen", side_effect=boom), mock.patch("socket.socket.connect_ex", side_effect=boom), \
                mock.patch.object(hoist, "ensure_server", side_effect=boom):
            code, text = run(hoist.wait_session, root)
        check("wait finishes from files alone", code == 0 and "decided" in text, text[-200:])


def test_tidy_draft():
    """Shape slips the agent made in a live run: no crash, and no repair round for what has one obvious meaning."""
    d = json.loads(json.dumps(SAMPLE["drafts"][next(iter(SAMPLE["drafts"]))]))
    d["profile_effects"] = ["more walks mean more driving"]
    d["assumes"] = ["one person", "local clients"]
    d.pop("agent_pick", None)
    for o in d["options"]:
        o["good"] = [x["text"] for x in o["good"]]
    t = hoist.tidy_draft(d)
    check("strings where objects belong don't crash the checks", isinstance(hoist.check_draft(t, SAMPLE["plan"]["profile"]), list))
    check("a lean with no agent_pick takes the default option", t["agent_pick"] == t["default_option"])
    check("assumes becomes a sentence", isinstance(t["assumes"], str))
    check("plain-text upsides become items", all(isinstance(x, dict) for o in t["options"] for x in o["good"]))
    check("junk isn't a draft", hoist.tidy_draft("nope") == {})


def test_server_with_agent_drafting():
    with tempfile.TemporaryDirectory() as d, mock.patch.dict(os.environ, {"HOIST_DRAFTER": ""}), \
            mock.patch.object(hoist, "ensure_key", return_value=False):
        root = Path(d)
        srv = ThreadingHTTPServer(("127.0.0.1", 0), hoist.make_handler(root))
        threading.Thread(target=srv.serve_forever, daemon=True).start()
        base = f"http://127.0.0.1:{srv.server_address[1]}"
        try:
            state = json.load(urllib.request.urlopen(base + "/api/state"))
            check("state says no key and agent drafting", state["muse"] is False and state["drafter"] == "agent", str(state)[:120])

            def post(path, body):
                req = urllib.request.Request(base + path, data=json.dumps(body).encode(), method="POST",
                                             headers={"Content-Type": "application/json", "Origin": hoist.URL})
                try:
                    return urllib.request.urlopen(req).status, {}
                except urllib.error.HTTPError as e:
                    return e.code, json.load(e)
            code, body = post("/api/session", {"task": "Add user accounts"})
            check("the page can't start a Muse Spark run without a key", code == 400 and "agent" in body.get("error", ""), str(body))
            code, body = post("/api/advocate", {"prompt": "You are reviewing a team's decision record in the role of x"})
            check("the live critic needs a key", code == 400 and "key" in body.get("error", ""), str(body))
        finally:
            srv.shutdown()


if __name__ == "__main__":
    test_agent_drafting()
    test_wait_stays_off_the_network()
    test_tidy_draft()
    test_server_with_agent_drafting()
    print(f"\n{len(FAILURES)} failure(s)")
    for f in FAILURES:
        print("FAILED:", f)
    sys.exit(1 if FAILURES else 0)
