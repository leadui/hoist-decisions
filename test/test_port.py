#!/usr/bin/env python3
"""One port, many projects: when another project's Hoist page holds the port, this project's hook takes it over,
so the page always shows the project the person is working in (and their answers reach the agent that waits).

Run:  python3 test/test_port.py
Standard library only. Real page servers on a spare port, in temp project roots; no browser, no Muse Spark calls.
"""
import json
import os
import subprocess
import sys
import tempfile
import time
import urllib.request
from pathlib import Path

os.environ["HOIST_PORT"] = os.environ.get("HOIST_TEST_PORT", "7398")
os.environ["BROWSER"] = "true"
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
import hoist

FAILURES = []


def check(name, cond, detail=""):
    print(("PASS " if cond else "FAIL ") + name)
    if not cond:
        FAILURES.append(name + (" — " + detail if detail else ""))


def wait_for(fn, secs=8):
    end = time.time() + secs
    while time.time() < end:
        if fn():
            return True
        time.sleep(0.1)
    return False


def test_takeover():
    with tempfile.TemporaryDirectory() as a, tempfile.TemporaryDirectory() as b:
        A, B = Path(a).resolve(), Path(b).resolve()
        for r in (A, B):
            (r / ".hoist").mkdir()
        check("the test port starts free", not hoist.port_open(), f"port {hoist.PORT} is busy")
        old = subprocess.Popen([sys.executable, str(ROOT / "hoist.py"), "serve", str(A)], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        try:
            check("project A's page is up", wait_for(lambda: hoist.serving(A)))
            check("project B is not being served yet", not hoist.serving(B))
            check("project B's hook takes the port over", hoist.ensure_server(B))
            check("the page now shows project B", hoist.serving(B), json.dumps(hoist.page_state() or {})[:120])
            check("project A's server stepped aside", wait_for(lambda: old.poll() is not None, 5))
            check("project A's session files are untouched", (A / ".hoist").is_dir())

        finally:
            if old.poll() is None:
                old.kill()
            req = urllib.request.Request(f"{hoist.URL}/api/shutdown", data=b"{}", method="POST",
                                         headers={"Content-Type": "application/json", "Origin": hoist.URL})
            try:
                urllib.request.urlopen(req, timeout=2).read()
            except OSError:
                pass
            wait_for(lambda: not hoist.port_open(), 5)


def test_leaves_other_programs_alone():
    other = subprocess.Popen([sys.executable, "-m", "http.server", str(hoist.PORT), "--bind", "127.0.0.1"],
                             stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, cwd=tempfile.gettempdir())
    try:
        wait_for(hoist.port_open)
        with tempfile.TemporaryDirectory() as b:
            check("a port held by something that isn't Hoist is left alone", not hoist.ensure_server(Path(b).resolve()))
        check("that program is still running", other.poll() is None)
    finally:
        other.kill()
        wait_for(lambda: not hoist.port_open(), 5)


def test_shutdown_needs_the_page_origin():
    with tempfile.TemporaryDirectory() as a:
        A = Path(a).resolve(); (A / ".hoist").mkdir()
        srv = subprocess.Popen([sys.executable, str(ROOT / "hoist.py"), "serve", str(A)], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        try:
            wait_for(lambda: hoist.serving(A))
            req = urllib.request.Request(f"{hoist.URL}/api/shutdown", data=b"{}", method="POST",
                                         headers={"Content-Type": "application/json", "Origin": "https://evil.example"})
            try:
                urllib.request.urlopen(req, timeout=2)
                code = 200
            except urllib.error.HTTPError as e:
                code = e.code
            check("a web page from elsewhere can't stop the server", code == 403 and srv.poll() is None, str(code))
        finally:
            srv.kill()
            wait_for(lambda: not hoist.port_open(), 5)


if __name__ == "__main__":
    test_takeover()
    test_leaves_other_programs_alone()
    test_shutdown_needs_the_page_origin()
    print(f"\n{len(FAILURES)} failure(s)")
    for f in FAILURES:
        print("FAILED:", f)
    sys.exit(1 if FAILURES else 0)
