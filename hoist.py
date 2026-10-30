#!/usr/bin/env python3
"""hoist: pause a coding agent at decisions that are hard to undo, decide with the user, record the choice.

Commands:
  python3 hoist.py install [project]   add Hoist to a project (Muse Code hook, skill, docs/decisions)
  python3 hoist.py serve [project]     run the decision page on http://127.0.0.1:7317
  python3 hoist.py gate                Muse Code hook entry point (reads the hook payload on stdin)
  python3 hoist.py wait [ID] [project] wait until the open decision (or ID) is made, then print the outcome
  python3 hoist.py mode [ask|autopilot] [project]   ask before hard-to-undo choices (default), or let the agent decide and record it
  python3 hoist.py log QUESTION --chose X --because Y [--options "A|B|C"]   record a decision the agent made (autopilot)
  python3 hoist.py drafter [agent|muse] [project]   who drafts the decisions: the agent (default, no key) or Muse Spark
  python3 hoist.py brief | submit plan FILE | submit draft ID FILE   how the agent drafts for the page

Standard library only. The page and its server listen on 127.0.0.1. By default the agent drafts the decisions
and nothing leaves the machine. With a Muse Spark key (MODEL_API_KEY or the macOS Keychain entry
"hoist-meta-api") and `drafter muse`, Muse Spark drafts them and the live critic works; those calls send the
task and an excerpt of the project's manifest, config and schema files to api.meta.ai.
"""
import argparse, concurrent.futures, json, os, re, shlex, shutil, signal, socket, subprocess, sys, threading, time, urllib.request, webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

HOME = Path(__file__).resolve().parent
PORT = int(os.environ.get("HOIST_PORT", "7317"))
URL = f"http://127.0.0.1:{PORT}"
WAIT = int(os.environ.get("HOIST_WAIT", "0"))  # seconds the hook itself holds the agent; 0 = block at once and let `hoist wait` show the pause
HOOK_TIMEOUT = 600
DOOR_WORDS = {3: "one-way door: hard to undo", 2: "heavy door: days to undo", 1: "two-way door: easy to undo"}


def catalog():
    return json.loads((HOME / "catalog.json").read_text())


def decisions_dir(root):
    d = root / ".hoist" / "decisions"; d.mkdir(parents=True, exist_ok=True); return d


def records_dir(root):
    d = root / "docs" / "decisions"; d.mkdir(parents=True, exist_ok=True); return d


def load_decisions(root):
    return sorted((json.loads(p.read_text()) for p in decisions_dir(root).glob("*.json")), key=lambda d: d["id"])


def save_decision(root, dec):
    (decisions_dir(root) / f"{dec['id']}.json").write_text(json.dumps(dec, indent=2))


def next_id(root):
    nums = [int(m.group(1)) for p in records_dir(root).glob("*.md") if (m := re.match(r"(\d{4})-", p.name))]
    nums += [int(d["id"]) for d in load_decisions(root)]
    return f"{max(nums, default=0) + 1:04d}"


# ---------- modes: ask (pause and decide together) or autopilot (the agent decides, Hoist records) ----------
MODES = ("ask", "autopilot")


def config_file(root):
    return Path(root) / ".hoist" / "config.json"


def get_mode(root):
    env = os.environ.get("HOIST_MODE", "").strip().lower()
    if env in MODES:
        return env
    try:
        m = json.loads(config_file(root).read_text()).get("mode")
    except (OSError, ValueError):
        m = None
    return m if m in MODES else "ask"


def set_config(root, key, value):
    f = config_file(root)
    f.parent.mkdir(parents=True, exist_ok=True)
    try:
        cfg = json.loads(f.read_text())
    except (OSError, ValueError):
        cfg = {}
    cfg[key] = value
    f.write_text(json.dumps(cfg, indent=2) + "\n")


def set_mode(root, m):
    set_config(root, "mode", m)


# ---------- who drafts the decisions: the agent itself (default, no key) or Muse Spark (optional key) ----------
DRAFTERS = ("agent", "muse")


def get_drafter(root):
    env = os.environ.get("HOIST_DRAFTER", "").strip().lower()
    if env in DRAFTERS:
        return env
    try:
        d = json.loads(config_file(root).read_text()).get("drafter")
    except (OSError, ValueError):
        d = None
    return d if d in DRAFTERS else "agent"


def effective_drafter(root):
    """Muse Spark only when asked for and a key is there; otherwise the agent drafts (no key needed)."""
    return "muse" if get_drafter(root) == "muse" and ensure_key() else "agent"


def slugify(text):
    return re.sub(r"[^a-z0-9]+", "-", str(text).lower()).strip("-")[:60] or "decision"


def autopilot_record(root, title, chose, because, options=(), agent="Your agent", task="", door=2, good=(), bad=(), undo="", trigger="", rid=None):
    """Write a MADR record for a call the agent made on autopilot. Honest about who decided: confidence is low until a person reviews it."""
    others = [o for o in options if o and o != chose]
    lines = ["---", "status: accepted", "date: " + time.strftime("%Y-%m-%d"), "door: " + DOOR_WORDS.get(door, DOOR_WORDS[2]).split()[0],
             "proposed-by: " + agent + (f" ({task})" if task else ""), "deciders: " + agent + " on autopilot; the project owner can review it",
             "confidence: low", "mode: autopilot", "---",
             f"# {title}: {chose}", "",
             f"> **Decision:** {chose}. **Because** {because.rstrip('.')}. **Revisit** before building on it: nobody chose this on purpose yet.", "",
             "## Context and Problem Statement",
             (f"{agent} {trigger} " if trigger else "") + (f'While working on "{task}". ' if task else "") + (undo or "This is hard to change later."), "",
             "## Considered Options", "\n".join(f"{i + 1}. {o}" for i, o in enumerate([chose] + others)), "",
             "## Decision Outcome", f"Chosen: {chose}, because {because.rstrip('.')}. Decided on autopilot, without asking.", ""]
    if good or bad:
        lines += ["### Consequences"] + [f"- Good, because {g[0].lower() + g[1:]}" for g in good] + [f"- Bad, because {b[0].lower() + b[1:]}" for b in bad] + [""]
    lines += ["## More Information", "- Confidence: low; the agent decided on autopilot. Review it in Hoist's records and change it before more is built on it.", ""]
    name = f"{rid or next_id(root)}-{slugify(title + ' ' + chose)}.md"
    records_dir(root).mkdir(parents=True, exist_ok=True)
    (records_dir(root) / name).write_text("\n".join(lines))
    return f"docs/decisions/{name}"


def log_decision(title, chose, because, options, project):
    root = Path(project).resolve()
    task_file = root / ".hoist" / "last_task.txt"
    rec = autopilot_record(root, title, chose, because, [o.strip() for o in options.split("|")] if options else (),
                           agent="Your agent", task=task_file.read_text().strip() if task_file.exists() else "")
    print(f"Hoist recorded it: {rec} (autopilot, low confidence until someone reviews it). Carry on with {chose}.")


AUTOPILOT_NOTE = ("Hoist is on autopilot in this project. When you reach a choice that is hard to undo, make the call yourself, "
                  "then record it: python3 {hoist} log \"<the decision, as a short title>\" --chose \"<what you picked>\" "
                  "--because \"<one plain sentence>\" --options \"<A|B|C>\". Do not ask the routing question. "
                  "Recorded decisions in docs/decisions/ still bind you.")


# ---------- what did the agent just add? ----------
PKG_RE = re.compile(r'"(@?[A-Za-z0-9][\w.\-/]*)"\s*:\s*"[^"]*"')
INSTALL_VERBS = {"install", "i", "add"}
MANAGERS = {"npm", "pnpm", "yarn", "bun"}


def deps_in(text):
    return set(PKG_RE.findall(text or ""))


def added_packages(payload, root):
    ti = payload.get("tool_input") or {}
    path = str(ti.get("path") or ti.get("file_path") or "")
    if path.endswith("package.json"):
        if "replace" in ti or "new_string" in ti:
            return deps_in(ti.get("replace", ti.get("new_string", ""))) - deps_in(ti.get("find", ti.get("old_string", "")))
        p = Path(path) if Path(path).is_absolute() else root / path
        return deps_in(ti.get("content", "")) - deps_in(p.read_text() if p.exists() else "")
    out = set()
    for part in re.split(r"&&|\|\||;", str(ti.get("command") or "")):
        try:
            words = shlex.split(part)
        except ValueError:
            continue
        for i, w in enumerate(words[:-1]):
            if w in MANAGERS and words[i + 1] in INSTALL_VERBS:
                out |= {re.sub(r"(?<=.)@[^/]*$", "", x) for x in words[i + 2:] if not x.startswith("-")}
    return out


def match_catalog(pkgs):
    for kind, k in catalog()["kinds"].items():
        for opt, names in k["packages"].items():
            for pkg in sorted(pkgs):
                if pkg in names:
                    return kind, opt, pkg
    return None


def known_facts(root):
    if any((root / f).exists() for f in ("vercel.json", "netlify.toml")):
        return {"host": 0}, {"host": next(f for f in ("vercel.json", "netlify.toml") if (root / f).exists())}
    if any((root / f).exists() for f in ("fly.toml", "Dockerfile", "docker-compose.yml", "compose.yaml")):
        return {"host": 1}, {"host": next(f for f in ("fly.toml", "Dockerfile", "docker-compose.yml", "compose.yaml") if (root / f).exists())}
    return {}, {}


# ---------- the hook ----------
def block(msg):
    print(msg, file=sys.stderr)
    return 2


def outcome_message(dec, k, pkg):
    opt = k["options"].get(dec.get("choice") or "", {})
    rec = dec.get("record", "docs/decisions/")
    if dec["status"] == "parked":
        return (f"Hoist: the user parked this decision ({rec}). Do not add `{pkg}` or any other database package. "
                "Keep saved data in memory behind a small repository interface for now, then continue the task.")
    skip = f"Do not add `{pkg}`. " if pkg not in k["packages"].get(dec.get("choice"), []) else ""
    if dec.get("mode") == "autopilot":
        return (f"Hoist: this was already decided on autopilot: {opt.get('tn', dec.get('choice'))} (record: {rec}). {skip}"
                f"{opt.get('use', '')} If it should change, ask the user to review the record first. Then continue the original task.")
    who = "chose" if dec.get("mode") == "chosen" else "let Hoist pick"
    return (f"Hoist: the user {who} {opt.get('tn', dec.get('choice'))} for this decision (record: {rec}). "
            f"{skip}{opt.get('use', '')} Then continue the original task.")


def gate():
    try:
        payload = json.loads(sys.stdin.read() or "{}")
    except ValueError:
        return 0
    root = Path(payload.get("cwd") or os.getcwd())
    event = payload.get("hook_event_name")
    if event == "UserPromptSubmit":
        (root / ".hoist").mkdir(exist_ok=True)
        (root / ".hoist" / "last_task.txt").write_text(payload.get("prompt", ""))
        if get_mode(root) == "autopilot":
            print(AUTOPILOT_NOTE.format(hoist=shlex.quote(str(HOME / "hoist.py"))))
        return 0
    if event == "PostToolBatch":
        return questionnaire_handoff(payload, root)
    if event != "PreToolUse":
        return 0
    hit = match_catalog(added_packages(payload, root))
    if not hit:
        return 0
    kind, opt, pkg = hit
    k = catalog()["kinds"][kind]
    dec = next((d for d in reversed(load_decisions(root)) if d["kind"] == kind), None)
    if dec and dec["status"] != "open":
        return 0 if dec["status"] == "accepted" and opt == dec.get("choice") else block(outcome_message(dec, k, pkg))
    if not dec and get_mode(root) == "autopilot":
        # The agent decides; Hoist writes it down so the person can review and change it later.
        o = k["options"][opt]
        task_file = root / ".hoist" / "last_task.txt"
        task = task_file.read_text().strip() if task_file.exists() else ""
        rid = next_id(root)
        because = f"the agent reached for `{pkg}`" + (f": {o['sub']}" if o.get("sub") else "")
        rec = autopilot_record(root, k["title"], o["n"], because,
                               [x["n"] for x in k["options"].values()], agent="Muse Code", task=task, door=k.get("door", 2),
                               good=[g[1] for g in o.get("good", [])], bad=[b[1] for b in o.get("bad", [])], undo=k.get("undo", ""),
                               trigger=f"was about to add `{pkg}`.", rid=rid)
        save_decision(root, {"id": rid, "kind": kind, "status": "accepted", "created": time.strftime("%Y-%m-%d %H:%M"),
                             "agent": "Muse Code", "task": task, "agent_pick": opt, "choice": opt, "mode": "autopilot",
                             "trigger": {"package": pkg, "tool": payload.get("tool_name")}, "record": rec})
        print(f"Hoist (autopilot): recorded {k['title'].lower()} as {o['n']} in {rec}. Carry on.")
        return 0
    if not dec:
        facts, sources = known_facts(root)
        task_file = root / ".hoist" / "last_task.txt"
        dec = {"id": next_id(root), "kind": kind, "status": "open", "created": time.strftime("%Y-%m-%d %H:%M"),
               "agent": "Muse Code", "task": task_file.read_text().strip() if task_file.exists() else "",
               "agent_pick": opt, "trigger": {"package": pkg, "tool": payload.get("tool_name")},
               "facts": facts, "fact_sources": sources, "answers": {}}
        save_decision(root, dec)
    page = f"{URL}/#/decide/{dec['id']}"
    if ensure_server(root):
        webbrowser.open(page)
    end = time.time() + WAIT
    while time.time() < end:
        time.sleep(1)
        dec = json.loads((decisions_dir(root) / f"{dec['id']}.json").read_text())
        if dec["status"] != "open":
            return block(outcome_message(dec, k, pkg))
    wait_cmd = f"python3 {shlex.quote(str(HOME / 'hoist.py'))} wait {dec['id']}"
    return block(f"Hoist: paused for a lasting decision ({k['title'].lower()}). The user is deciding at {page}. "
                 f"Do not add `{pkg}` or pick another option yourself. Run `{wait_cmd}` now and let it finish: "
                 "it waits for the user and prints what they chose. Then follow that and continue the original task.")


# ---------- the agent's questionnaire: "Decide with Hoist instead" ----------
HOIST_PICK = "Decide with Hoist instead"


def questionnaire_answers(call):
    resp = call.get("tool_response")
    if isinstance(resp, str):  # Muse Code sends the questionnaire's result as a JSON string
        try:
            resp = json.loads(resp)
        except ValueError:
            return []
    return [a for a in ((resp or {}).get("answers") or []) if isinstance(a, dict)]


REC_SUFFIX = " (Recommended)"  # Muse Code marks the recommended option with this suffix


def plain_label(label):
    label = str(label)
    return label[:-len(REC_SUFFIX)] if label.endswith(REC_SUFFIX) else label


def picked_hoist(answers):
    for a in answers:
        labels = []
        if isinstance(a.get("selected_label"), str):
            labels.append(a["selected_label"])
        for key in ("selected_labels", "selected", "labels"):  # answer shapes vary; accept them all
            vals = a.get(key)
            if isinstance(vals, list):
                labels += [v for v in vals if isinstance(v, str)]
        if any(plain_label(label) == HOIST_PICK for label in labels):
            return True
    return False


def questionnaire_handoff(payload, root):
    """PostToolBatch: the only hook that sees the questionnaire (PreToolUse and PostToolUse skip it).
    When the person picked Hoist, start a session with the agent's questions as hints and open the page."""
    for call in payload.get("tool_calls") or []:
        if "request_user_input" not in str(call.get("tool_name")) or not picked_hoist(questionnaire_answers(call)):
            continue
        questions = (call.get("tool_input") or {}).get("questions") or []
        hints = "\n".join("- " + str(q.get("question", "")) + " Options the agent offered: "
                          + ", ".join(l for o in q.get("options") or [] for l in [plain_label(o.get("label", ""))]
                                       if l and l != HOIST_PICK)
                          for q in questions)
        task_file = root / ".hoist" / "last_task.txt"
        task = task_file.read_text().strip() if task_file.exists() else "The current task"
        if effective_drafter(root) == "agent":  # no key needed: the agent drafts, Hoist checks and shows
            start_agent_session(root, task, hints)
            page = ensure_server(root)
            if page:
                webbrowser.open(f"{URL}/#/session")
            hc = hoist_cmd()
            print("Hoist: the user chose to decide in Hoist, so ignore every answer in that form. "
                  + (f"The page is open at {URL}/#/session. " if page else f"Tell the user to run `{hc} serve` and open {URL}/#/session. ")
                  + f"You prepare the decisions for it: run `{hc} brief` and follow it (hand it to a subagent if you can), "
                  f"submit what it asks for, and repeat until it says everything is on the page. Then run `{hc} wait` and let it "
                  "finish: it waits until the user has decided and prints the choices. Follow them and continue the task.")
            return 0
        if ensure_server(root) and post_session(task, hints):
            webbrowser.open(f"{URL}/#/session")
            print("Hoist: the user chose to decide in Hoist, so ignore every answer in that form. Muse Spark is preparing "
                  f"the decisions at {URL}/#/session. Run `python3 {shlex.quote(str(HOME / 'hoist.py'))} wait` now and let it "
                  "finish: it waits until the user has decided and prints the choices. Then follow them and continue the task.")
        else:
            print(f"Hoist: couldn't open the decision page at {URL}. Ask the user these questions in chat instead.")
        return 0
    return 0


def post_session(task, hints=""):
    req = urllib.request.Request(f"{URL}/api/session", data=json.dumps({"task": task, "hints": hints}).encode(), method="POST",
                                 headers={"Content-Type": "application/json", "Origin": URL})
    try:
        urllib.request.urlopen(req, timeout=10).read()
        return True
    except urllib.error.HTTPError as e:
        return e.code == 409  # already preparing: the page is still the right place
    except OSError:
        return False


def ensure_server(root):
    """Make sure the page server for this project is answering; start it detached if needed."""
    if serving(root):
        return True
    if port_open() and not take_over_port(root):  # held by something that isn't a Hoist page: leave it alone
        return False
    if os.fork() == 0:  # double fork, so cancelling the hook can't take the server down with it
        os.setsid()
        if os.fork() == 0:
            log = os.open(str(root / ".hoist" / "server.log"), os.O_WRONLY | os.O_CREAT | os.O_APPEND)
            os.dup2(log, 1); os.dup2(log, 2)
            os.execv(sys.executable, [sys.executable, "-u", str(HOME / "hoist.py"), "serve", str(root)])
        os._exit(0)
    for _ in range(50):
        if serving(root):
            return True
        time.sleep(0.1)
    return False


def port_open():
    with socket.socket() as s:
        s.settimeout(0.2)
        return s.connect_ex(("127.0.0.1", PORT)) == 0


def page_state():
    try:
        with urllib.request.urlopen(f"{URL}/api/state", timeout=1) as r:
            return json.loads(r.read())
    except (OSError, ValueError):
        return None


def serving(root):
    return (page_state() or {}).get("root") == str(root)


def take_over_port(root):
    """The port holds another project's Hoist page (one port serves one project). The person is working here now,
    so that page steps aside; its session stays on disk and its own hook takes the port back when it runs."""
    other = page_state()
    if not other or "root" not in other:
        return False
    req = urllib.request.Request(f"{URL}/api/shutdown", data=b"{}", method="POST", headers={"Content-Type": "application/json", "Origin": URL})
    try:
        urllib.request.urlopen(req, timeout=2).read()
    except OSError:
        pass
    for attempt in range(60):
        if not port_open():
            return True
        if attempt == 20:  # a page from an older Hoist has no shutdown route: stop that server process directly
            try:
                pids = subprocess.run(["lsof", "-tiTCP:%d" % PORT, "-sTCP:LISTEN"], capture_output=True, text=True, timeout=5).stdout.split()
            except (OSError, subprocess.SubprocessError):
                pids = []
            for pid in pids:
                cmd = subprocess.run(["ps", "-o", "command=", "-p", pid], capture_output=True, text=True).stdout
                if "hoist.py" in cmd and " serve" in cmd:
                    try:
                        os.kill(int(pid), signal.SIGTERM)
                    except (OSError, ValueError):
                        pass
        time.sleep(0.1)
    return not port_open()


# ---------- the local page ----------
def make_handler(root):
    allowed = {f"http://127.0.0.1:{PORT}", f"http://localhost:{PORT}"}
    key = {"at": 0.0, "ok": False}

    def has_key():  # the page polls; look the key up at most every 30 s
        if time.time() - key["at"] > 30:
            key.update(at=time.time(), ok=ensure_key())
        return key["ok"]

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *a):
            pass

        def send(self, code, body, ctype="application/json"):
            data = body if isinstance(body, bytes) else (body if isinstance(body, str) else json.dumps(body)).encode()
            self.send_response(code)
            self.send_header("Content-Type", ctype + "; charset=utf-8")
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(data)

        def do_GET(self):
            path = self.path.split("?")[0]
            if path in ("/", "/index.html"):
                return self.send(200, (HOME / "site" / "index.html").read_bytes(), "text/html")
            if path == "/catalog.json":
                return self.send(200, (HOME / "catalog.json").read_bytes())
            if path in ("/vendor/bento-madr/bento-kit.css", "/vendor/bento-madr/bento-kit.js", "/hoist-bento.js"):
                return self.send(200, (HOME / "site" / path.lstrip("/")).read_bytes(), "text/css" if path.endswith(".css") else "text/javascript")
            if path == "/api/state":
                records = [{"file": p.name, "markdown": p.read_text()} for p in sorted(records_dir(root).glob("[0-9][0-9][0-9][0-9]-*.md"))]
                return self.send(200, {"project": root.name, "root": str(root), "live": True, "build": build_stamp(),
                                       "muse": has_key(), "drafter": "muse" if get_drafter(root) == "muse" and has_key() else "agent",
                                       "decisions": load_decisions(root),
                                       "records": records, "session": session_state(root)})
            self.send(404, {"error": "not found"})

        def do_POST(self):
            if self.headers.get("Origin") not in allowed:
                return self.send(403, {"error": "Requests must come from the Hoist page."})
            body = json.loads(self.rfile.read(int(self.headers.get("Content-Length", 0))) or "{}")
            if self.path == "/api/shutdown":  # another project's hook needs the port; this project's session stays on disk
                threading.Timer(0.2, os._exit, (0,)).start()
                return self.send(200, {"stopping": str(root)})
            if self.path == "/api/session":
                ses = load_session(root)
                if ses and ses["status"] in ("planning", "drafting"):
                    return self.send(409, {"error": "The last task is still being prepared."})
                if not (get_drafter(root) == "muse" and has_key()):
                    return self.send(400, {"error": "Your agent drafts the decisions, so sessions start from your agent: give it a task "
                                                    "and pick \"Decide with Hoist instead\" when it asks. To start one here instead, "
                                                    "add a Muse Spark key and run `hoist.py drafter muse`."})
                task = str(body.get("task", "")).strip()[:500]
                if not task:
                    return self.send(400, {"error": "Describe the task first."})
                hints = str(body.get("hints", ""))[:4000]
                threading.Thread(target=run_session, args=(root, task, hints, bool(body.get("resume"))), daemon=True).start()
                time.sleep(0.2)
                return self.send(200, session_state(root))
            if self.path == "/api/session/answers":
                ses = load_session(root)
                if not ses:
                    return self.send(404, {"error": "No session."})
                ses["profile_answers"].update(body.get("profile_answers", {}))
                ses.setdefault("confirmed", {}).update({k: v for k, v in (body.get("confirmed") or {}).items() if v in ("confirmed", "changed")})
                for k, v in (body.get("answers") or {}).items():
                    ses["answers"].setdefault(k, {}).update(v)
                save_session(root, ses)
                return self.send(200, session_state(root))
            m = re.fullmatch(r"/api/session/decisions/([a-z0-9-]{1,60})/deep", self.path)
            if m:
                f = root / ".hoist" / "drafts" / f"{m.group(1)}.json"
                if not f.exists():
                    return self.send(404, {"error": "No such decision in this task."})
                try:
                    return self.send(200, deepen_draft(root, m.group(1)))
                except (Exception, SystemExit) as e:
                    return self.send(502, {"error": f"Muse Spark couldn't write the deep dive ({e})."})
            m = re.fullmatch(r"/api/session/decisions/([a-z0-9-]{1,60})", self.path)
            if m:
                ses = load_session(root)
                if not ses or m.group(1) not in ses.get("drafted", []) + [x["id"] for x in (session_state(root).get("plan") or {}).get("decisions", [])]:
                    return self.send(404, {"error": "No such decision in this task."})
                slug = re.sub(r"[^a-z0-9-]+", "-", str(body.get("slug", "decision")).lower()).strip("-")[:60] or "decision"
                name = f"{next_id(root)}-{slug}.md"
                (records_dir(root) / name).write_text(str(body.get("markdown", "")))
                ses["outcomes"][m.group(1)] = {"choice": body.get("choice"), "mode": body.get("mode"), "record": f"docs/decisions/{name}",
                                               "note": str(body.get("note") or "")[:500]}
                save_session(root, ses)
                return self.send(200, session_state(root))
            if self.path == "/api/advocate":
                if not has_key():
                    return self.send(400, {"error": "The live critic needs a Muse Spark key."})
                prompt = str(body.get("prompt", ""))
                if not prompt.startswith("You are reviewing a team's decision record in the role of") or len(prompt) > 12000:
                    return self.send(400, {"error": "That is not a critic prompt from the kit."})
                try:
                    return self.send(200, muse_json(ADVOCATE_SYSTEM, prompt, f"advocate:{root.name}", max_output=3000))
                except (Exception, SystemExit) as e:
                    return self.send(502, {"error": f"Muse Spark couldn't answer ({e})."})
            if self.path == "/api/session/abandon":
                st = abandon_decision(root, str(body.get("id", "")))
                if not st:
                    return self.send(404, {"error": "No such decision in this task."})
                return self.send(200, st)
            m = re.fullmatch(r"/api/decisions/(\d{4})", self.path)
            f = decisions_dir(root) / f"{m.group(1)}.json" if m else None
            if not f or not f.exists():
                return self.send(404, {"error": "No such decision."})
            dec = json.loads(f.read_text())
            if dec["status"] != "open":
                return self.send(409, {"error": "This decision is already made."})
            slug = re.sub(r"[^a-z0-9-]+", "-", str(body.get("slug", "decision")).lower()).strip("-")[:60] or "decision"
            name = f"{dec['id']}-{slug}.md"
            (records_dir(root) / name).write_text(str(body.get("markdown", "")))
            dec.update(status="parked" if body.get("mode") == "parked" else "accepted", choice=body.get("choice"),
                       mode=body.get("mode"), answers=body.get("answers", {}), record=f"docs/decisions/{name}",
                       decided=time.strftime("%Y-%m-%d %H:%M"))
            f.write_text(json.dumps(dec, indent=2))
            self.send(200, dec)

    return Handler


WATCHED = ("hoist.py", "site/index.html", "site/bento-kit.js", "site/bento-kit.css")


def build_stamp():
    """Newest mtime across the files that define the running build."""
    return int(max((HOME / p).stat().st_mtime for p in WATCHED if (HOME / p).exists()))


def watch_and_restart(root):
    """Re-exec on code/asset change, so a stale server never serves a new page."""
    stamp = build_stamp()
    while True:
        time.sleep(2)
        try:
            now = build_stamp()
        except OSError:
            continue
        if now != stamp:
            print("Hoist: files changed — restarting the page server.", file=sys.stderr, flush=True)
            os.execv(sys.executable, [sys.executable, "-u", str(HOME / "hoist.py"), "serve", str(root)])


def serve(project):
    root = Path(project).resolve()
    print(f"Hoist decision page for {root.name}: {URL}  (Ctrl+C to stop)")
    threading.Thread(target=watch_and_restart, args=(root,), daemon=True).start()
    ThreadingHTTPServer(("127.0.0.1", PORT), make_handler(root)).serve_forever()


def wait(did, project):
    root = Path(project).resolve()
    if not did:
        waiting = [d for d in load_decisions(root) if d["status"] == "open"]
        ses = session_state(root)
        if not waiting and ses and ses.get("drafter") == "agent" and ses["status"] in ("planning", "drafting"):
            print(f"HOIST: the decisions aren't drafted yet. Run `{hoist_cmd()} brief`, submit what it asks for, then wait.")
            sys.exit(1)
        if not waiting and ses and (ses["status"] in ("planning", "drafting") or session_open(ses)):
            return wait_session(root)
        if not waiting:
            print("HOIST: no decision is waiting. Carry on.")
            return
        did = waiting[0]["id"]
    f = decisions_dir(root) / f"{did}.json"
    if not f.exists():
        sys.exit(f"No decision {did} in {project}.")
    dec = json.loads(f.read_text())
    k = catalog()["kinds"][dec["kind"]]
    line = "-" * 64
    if dec["status"] == "open":
        print(f"{line}\nHOIST: {dec.get('agent', 'Your agent')} is paused for a decision that is hard to undo\n"
              f"  Decision:   {k['title']} ({DOOR_WORDS.get(k['door'], '')})\n"
              f"  Agent was adding: `{dec['trigger']['package']}`\n"
              f"  Decide at:  {URL}/#/decide/{did}\n"
              f"  Waiting for you. The agent continues as soon as you choose.\n{line}", flush=True)
    while (dec := json.loads(f.read_text()))["status"] == "open":
        time.sleep(1)
    opt = k["options"].get(dec.get("choice") or "", {})
    print(f"{line}\nHOIST: decided. {'Parked for now' if dec['status'] == 'parked' else opt.get('n', dec.get('choice'))}"
          f" (record: {dec.get('record', '')})\n{line}")
    print(outcome_message(dec, k, dec["trigger"]["package"]))


def abandon_decision(root, did):
    """The owner sent one decision back to chat. Records an abandoned outcome so `hoist wait` unblocks."""
    ses = load_session(root)
    ids = [d["id"] for d in ((session_state(root) or {}).get("plan") or {}).get("decisions", [])]
    if not ses or did not in ids:
        return None
    ses["outcomes"][did] = {"choice": None, "mode": "abandoned", "record": "",
                            "note": "The owner sent this back to chat."}
    save_session(root, ses)
    return session_state(root)


def session_open(ses):
    asks = [d["id"] for d in ((ses.get("plan") or {}).get("decisions") or []) if d.get("mode") == "ask"]
    return ses["status"] == "ready" and any(a not in ses.get("outcomes", {}) for a in asks)


def wait_session(root):
    line = "-" * 64
    ses = session_state(root)
    print(f"{line}\nHOIST: paused while you make this task's lasting decisions\n  Task:       {ses['task']}\n"
          f"  Decide at:  {URL}/#/session\n  " + ("Your agent drafted them" if ses.get("drafter") == "agent" else "Muse Spark prepares them first")
          + f"; the agent continues when you're done.\n{line}", flush=True)
    error_since, checked = None, 0.0
    while True:
        if time.time() - checked > 5:  # the page must show this project; take it back if another project's page holds the port
            checked = time.time()
            if not serving(root) and ensure_server(root):
                print(f"HOIST: the decision page now shows this project: {URL}/#/session", flush=True)
                webbrowser.open(f"{URL}/#/session")
        ses = session_state(root)
        if ses["status"] == "error":
            if not error_since:
                error_since = time.time()
                print("HOIST: Muse Spark hit a problem; the page offers Try again. Still waiting.", flush=True)
            elif time.time() - error_since > 60:
                print(f"HOIST: Muse Spark couldn't prepare the decisions ({ses.get('error')}). Ask the user in chat instead.")
                return
        else:
            error_since = None
        if ses["status"] == "ready" and not session_open(ses):
            break
        time.sleep(1)
    print(f"{line}\nHOIST: decided\n{line}")
    out = ses.get("outcomes", {})
    for d in ses["plan"]["decisions"]:
        o, dr = out.get(d["id"]), ses["drafts"].get(d["id"]) or {}
        if d.get("mode") == "log":
            continue
        if o and o.get("mode") == "parked":
            print(f"- {d['title']}: not decided yet; keep it easy to replace ({o['record']})")
        elif o and o.get("mode") == "abandoned":
            print(f"- {d['title']}: sent back to chat — ask the user there instead")
        elif o and o.get("choice"):
            name = next((x["name"] for x in dr.get("options", []) if x["id"] == o["choice"]), o["choice"])
            print(f"- {d['title']}: {name} ({o['record']})" + (f"\n    Condition from the user: {o['note']}" if o.get("note") else ""))
        else:
            print(f"- {d['title']}: default, {d.get('default')}")
    print("Hoist: these are the user's decisions for this task. Follow them exactly, ignore any earlier form answers, "
          "and continue the original task. Choices the agent makes on its own can be noted in the final message.")


# ---------- Muse Spark writes the content; this code sets the contract and checks it ----------
MAX_ASK = int(os.environ.get("HOIST_MAX_ASK", "3"))  # decision-fatigue budget: questions to the person per task

PLAN_SYSTEM = """You are Hoist. An AI agent is about to work on a task for a person. List the lasting decisions
this task will force: choices that are costly to undo later. The project may be software, a design system,
writing, data, or anything else; use the evidence to tell which.

Rules for decisions:
- Only decisions this task needs now. Skip anything already decided in the recorded decisions.
- A config file shows what exists today, not what is right or final. If a lasting choice (hosting, a vendor) is only implied
  by a file and no recorded decision covers it, treat it as a decision to confirm, not a fixed constraint, and do not let it
  frame the other decisions.
- Usually 2 to 6 decisions. Order them so a decision comes after the ones it depends on.
- Each decision has one clear scope. Two decisions must not overlap: if one choice is part of another, merge them.
- door: 3 = one-way (redo most of the work to undo), 2 = heavy (days to undo), 1 = two-way (an afternoon).
- owner: "you" when the right answer depends on the person's goals, users, money, risk, or taste.
  "agent" when a competent practitioner would pick the same sensible default without asking.
- mode: "ask" for a one-way or heavy door owned by the person; "default" when a safe default exists that the
  person can review later; "log" for two-way doors the agent can just make.
- default: the safe default in a few plain words. why: one plain sentence on why it matters for this task.

Profile questions: 2 to 4 questions about the person and their project, asked once and used by every decision,
so the person is never asked the same thing twice. Rules:
- About their situation, audience, plans, constraints, or taste. Things they know without expertise.
- Never about products or technologies, and never name a vendor, host, or product in the question or its answers.
  Never ask for numbers they cannot know. No invented scenarios.
- Each one must matter to at least one "ask" decision; list which in used_by.
- 2 to 4 short answers each, plus beginner_note (one sentence explaining any term, or empty).
- assumed: the person will see your guess first and only correct it if it's wrong, so guess honestly from the
  evidence; when the evidence says nothing, pick the most common case and say so in basis.

Reply with JSON only:
{"task_summary": str,
 "profile": [{"id": "kebab-case", "text": str, "why": "one sentence: what it changes", "beginner_note": str,
   "answers": [str], "assumed": "the answer you think most likely, copied exactly from answers",
   "basis": "one short sentence: what in the task or project makes you assume it", "used_by": [decision ids]}],
 "decisions": [{"id": "kebab-case", "title": "plain verb phrase", "scope": "one sentence: what this decision covers and what it leaves to others",
   "door": 1|2|3, "owner": "you"|"agent", "mode": "ask"|"default"|"log", "default": str, "why": str, "depends_on": [ids]}]}"""

LEAN_SYSTEM = """You are Hoist. You help a person make one decision that an AI agent is about to make for them and
that is hard to undo. The person is smart but may not know the field. Write the way a patient expert explains
something to a friend: short sentences, plain words, no hype, no marketing adjectives, no scores or percentages.

You get the task, the project evidence, the plan of decisions for this task, and the profile questions the
person answers once for all of them. Stay inside this decision's scope. Treat the other decisions as handled
elsewhere: if this one depends on a decision not made yet, assume its default and say so in assumes.

Contract (reply with JSON only):
{"question": "the decision as a plain question about their project, not about product names",
 "why_now": "one sentence: why this has to be decided now",
 "undo": "one sentence: what undoing it later would involve",
 "assumes": "one sentence on what this takes as given from other decisions, or empty",
 "door": 1|2|3,
 "micro_label": "2 to 4 words naming what the comparison bars measure, e.g. ops burden",
 "analogy": "one everyday sentence that captures the shape of this decision: what is cheap now and expensive to change later",
 "kind": "tech-choice"|"vendor-select"|"build-vs-buy"|"product-bet"|"migration"|"process-change",
 "risks": [{"text": "what could go wrong with this decision, one short sentence", "likelihood": "low"|"medium"|"high",
   "impact": "low"|"medium"|"high", "mitigation": "one short sentence: what keeps it small"}],
 "confirm": ["at most 2 plain checks the person can see within a month that show the choice is working"],
 "profile_effects": [{"profile_id": "id from the profile", "answers": [{"label": "exact answer text from the profile",
   "effects": [{"option": "option id", "dir": "favors"|"against", "reason": "short"}]}]}],
 "questions": [{"id": "kebab-case", "text": "...", "why": "one sentence: what the answer changes",
   "beginner_note": "one sentence explaining any term in the question, or empty",
   "answers": [{"label": "short answer", "effects": [{"option": "option id", "dir": "favors"|"against", "reason": "short"}]}]}],
 "options": [{"id": "kebab-case", "name": "...", "plain_name": "2 to 5 everyday words, no technical terms",
   "analogy": "one sentence comparing this option to something from everyday life, matching how the trade-off works",
   "story": {"now": "one sentence: what it is like this week", "later": "one sentence: what it is like in 6 months"},
   "journey": ["exactly 4 short steps of what physically happens with this option, in order, plain words"],
   "micro": "0 to 10: where this option sits on micro_label. A shape for bars, not a number shown to the person",
   "summary": "one line",
   "good": [{"when": "now"|"later", "text": "..."}], "bad": [{"when": "now"|"later", "text": "..."}],
   "ruled_out": "" or "reason it cannot work here"}],
 "default_option": "option id", "default_reason": "one sentence",
 "agent_pick": "option id or empty",
 "lean": {"why": "one sentence: why the agent leans toward its pick, in plain words",
   "assumptions": ["at most 3 plain sentences about the person this lean depends on"],
   "flips": ["at most 2 conditions under which another option would fit better, as 'if ...' clauses"]},
 "evidence": [{"source": "file name" | "task" | "profile" | "inferred", "detail": "..."}]}

Rules for questions:
- Use the profile first: map each relevant profile answer to effects in profile_effects. Do not ask a profile question again.
- Add at most 1 question of your own, only if no profile question decides this. Same standards as the profile:
  about their situation, never about technology, no numbers they cannot know, no invented scenarios.
- Every answer lists at least one effect with a reason.
Rules for options:
- 2 to 4 options that could really work, at the same level (compare like with like). Include the agent's pick.
- Prefer kinds of solution over brand names. Name a product only when it is the usual concrete choice, and then fill check_current.
- Do not frame the question or the options around one vendor or host. The question names the need, not a platform.
  If an option only works well on one host, say so as a downside instead of making that host the premise.
- A config file shows what exists today, not a fixed constraint, unless a recorded decision says so.
- Put options that cannot work given the evidence in ruled_out with the reason instead of leaving them as weak choices.
- Every option has at least one bad item and at least one item about later.
Rules for kind, risks and confirm:
- kind names the shape of the decision, which picks the canvas it is shown on: tech-choice (an approach or library),
  vendor-select (a supplier or hosted tool), build-vs-buy (make it, buy it, or adopt open source), product-bet (which
  initiative to fund), migration (moving from A to B), process-change (how people work).
- At most 3 risks, specific to this project. Likelihood and impact are words, never numbers.
- confirm items are observations, not activities ("saves still load after a redeploy", not "ship the feature").
Rules for the lean:
- lean.why explains the pick in one sentence a newcomer understands. Leave lean out when agent_pick is empty.
- Each assumption is about the person's situation (budget, team, patience, scale), never about a product.
  The person confirms or challenges each one; challenged assumptions mark the lean as uncertain.
- Each flip is a concrete condition under which another option would fit better.
Rules for the walk-through (journeys, bars):
- journey is the mechanism as 4 physical steps (what moves where, in order). It teaches how the option works, not features.
- micro is a 0 to 10 shape for the comparison bars, judged across options, never precise.
  micro_label names the dimension honestly (burden, cost shape, lock-in). Bars carry no numbers on screen.
Rules for analogies and stories:
- An analogy maps how the trade-off works (what is shared, what is expensive to move, who maintains it), using
  everyday objects (filing cabinets, notebooks, keys, shops). Never use a technical word in an analogy or a plain_name.
- Use one family of analogies across the options, so they compare (for example: a shared cabinet, a notebook each,
  a box of loose cards).
- story.now and story.later describe what living with it is like for this person, not features. Later is honest
  about the cost.
Reply with the lean draft only: no numbers, trajectory, learn, check_current, or growth — those come in a later round."""


ADVOCATE_SYSTEM = """You stress-test one decision a person is about to make, in the voice of the persona the prompt names.
Plain words, short sentences, specific to this project. Reply with the JSON the prompt asks for and nothing else."""


DEEP_SYSTEM = """You are Hoist. A person is deciding one hard-to-undo choice and just opened the deep dive.
You get the lean draft (options, stories, journeys) plus project evidence. Write ONLY the deep
material as JSON: concrete numbers, the growth shape, what each option is, and what to verify.

Contract (reply with JSON only):
{"growth": {"title": "chart title in plain words", "now": "label for today, e.g. today", "later": "label for the future, e.g. at 10x"},
 "deep_options": [{"id": "option id copied exactly from the draft",
   "numbers": [["label", "value"], "2 to 4 rows of concrete scale or cost facts; write estimate when estimated, never invent precision"],
   "trajectory": ["0 to 10 now", "0 to 10 later: where this option heads on the growth chart. Shapes, not forecasts"],
   "learn": {"what": "two plain sentences describing what it is and how it works", "living_with": "two sentences on what day-to-day life with it is like",
     "terms": [{"term": "...", "meaning": "one line"}], "docs_url": "official documentation home page, or empty if unsure"},
   "check_current": "if the option names a product, vendor, plan, or price: one sentence on what to confirm is still true before relying on it; else empty"}]}

Rules:
- One entry per option in the draft, with the id copied exactly. No other options.
- numbers are concrete facts a newcomer can picture (reads per second, who does the work, what the bill follows).
  Mark guesses as estimates. Never show scores, ratings, or percentages.
- trajectory values are 0 to 10 shapes for the growth chart, judged against each other, never precise.
- learn describes the option itself. Never write "you will learn".
- terms: up to 4 terms the option's text uses that a newcomer may not know.
- Short sentences, plain words, no hype, no marketing adjectives."""


def project_context(root, task, limit=9000):
    import hoist_audit
    parts = [f"Task: {task}", f"Project folder: {root.name}"]
    recs = [p for p in sorted(records_dir(root).glob("[0-9][0-9][0-9][0-9]-*.md"))]
    if recs:
        parts.append("Recorded decisions:\n" + "\n".join(f"- {p.read_text().split(chr(10) + '# ', 1)[-1].splitlines()[0]}" for p in recs))
    parts.append(hoist_audit.pack(root)[:limit])
    return "\n\n".join(parts)


def muse_json(system, prompt, label, max_output=8000):
    """One Muse Spark call that must return JSON. A reply that is cut off or not valid JSON gets one retry."""
    import hoist_audit
    problem = ""
    for attempt in (1, 2):
        ask = prompt if attempt == 1 else (prompt + f"\n\nYour last reply could not be used ({problem}). "
                                           "Reply again with one complete, valid JSON object and nothing else.")
        text, finish = hoist_audit.ask_muse(system, ask, label if attempt == 1 else label + ":retry", max_output=max_output)
        if finish != "stop":
            problem = f"it stopped early: {finish}"
            continue
        try:
            return hoist_audit.parse(text)
        except ValueError as e:  # json.JSONDecodeError is a ValueError
            problem = f"invalid JSON: {e}"
    sys.exit(f"Muse Spark's reply was unusable twice ({problem}). Run it again.")


VENDORS = ("vercel", "netlify", "aws", "azure", "gcp", "google cloud", "heroku", "fly.io", "render", "railway", "supabase", "neon",
           "planetscale", "turso", "mongodb", "firebase", "clerk", "auth0", "stripe", "tailwind", "radix", "shadcn")


def check_draft(d, profile=None):
    """Lean-draft quality rules; returns problems in plain words (empty = passes). Deep material has check_deep."""
    problems = []
    if profile:
        known = {q["id"]: set(q.get("answers", [])) for q in profile}
        if len(d.get("questions") or []) > 1:
            problems.append(f"asks {len(d['questions'])} questions of its own; at most 1 when profile questions exist")
        for pe in d.get("profile_effects") or []:
            if pe.get("profile_id") not in known:
                problems.append(f"profile_effects uses unknown profile question '{pe.get('profile_id')}'")
                continue
            for a in pe.get("answers") or []:
                if a.get("label") not in known[pe["profile_id"]]:
                    problems.append(f"profile answer '{a.get('label')}' is not one of the profile's answers")
                for e in a.get("effects") or []:
                    if e.get("option") not in {o.get("id") for o in d.get("options") or []}:
                        problems.append(f"profile answer '{a.get('label')}' points at unknown option '{e.get('option')}'")
        if not d.get("profile_effects") and not d.get("questions"):
            problems.append("nothing the person says changes the ranking: map profile answers to effects")
    opts = d.get("options") or []
    ids = {o.get("id") for o in opts}
    viable = [o for o in opts if not o.get("ruled_out")]
    if not 2 <= len(viable) <= 4:
        problems.append(f"needs 2 to 4 workable options, has {len(viable)}")
    for o in viable:
        if not o.get("bad"):
            problems.append(f"option '{o.get('id')}' has no downside")
        if not any(x.get("when") == "later" for x in (o.get("good") or []) + (o.get("bad") or [])):
            problems.append(f"option '{o.get('id')}' says nothing about later")
        if not (o.get("plain_name") and o.get("analogy") and (o.get("story") or {}).get("now") and (o.get("story") or {}).get("later")):
            problems.append(f"option '{o.get('id')}' needs plain_name, analogy, and story now/later")
        journey = o.get("journey") or []
        if len(journey) != 4 or any(not str(s).strip() for s in journey):
            problems.append(f"option '{o.get('id')}' needs a journey of 4 steps")
        if not isinstance(o.get("micro"), (int, float)) or isinstance(o.get("micro"), bool) or not 0 <= o["micro"] <= 10:
            problems.append(f"option '{o.get('id')}' needs micro 0 to 10")
    qs = d.get("questions") or []
    if len(qs) > 3:
        problems.append(f"asks {len(qs)} questions; at most 3")
    for q in qs:
        if not 2 <= len(q.get("answers") or []) <= 4:
            problems.append(f"question '{q.get('id')}' needs 2 to 4 answers")
        for a in q.get("answers") or []:
            effects = a.get("effects") or []
            if not effects:
                problems.append(f"answer '{a.get('label')}' changes nothing")
            for e in effects:
                if e.get("option") not in ids:
                    problems.append(f"answer '{a.get('label')}' points at unknown option '{e.get('option')}'")
    if not d.get("analogy"):
        problems.append("the decision needs an everyday analogy")
    if not str(d.get("micro_label") or "").strip():
        problems.append("the decision needs micro_label for the comparison bars")
    if d.get("default_option") not in {o.get("id") for o in viable}:
        problems.append("default_option is not a workable option")
    if d.get("agent_pick") and d["agent_pick"] not in {o.get("id") for o in viable}:
        problems.append(f"agent_pick '{d['agent_pick']}' is not a workable option")
    lean = d.get("lean") or {}
    if lean and not d.get("agent_pick"):
        problems.append("lean without agent_pick: no pick, no lean")
    if d.get("agent_pick") and lean and not lean.get("why"):
        problems.append("the lean needs one sentence on why the agent leans this way")
    assumptions = lean.get("assumptions") or []
    if len(assumptions) > 3:
        problems.append(f"the lean lists {len(assumptions)} assumptions; at most 3")
    if any(not str(a).strip() for a in assumptions):
        problems.append("the lean has an empty assumption")
    if len(lean.get("flips") or []) > 2:
        problems.append(f"the lean lists {len(lean['flips'])} flips; at most 2")
    if any(not str(f).strip() for f in (lean.get("flips") or [])):
        problems.append("the lean has an empty flip")
    asked = " ".join([str(d.get("question", "")), str(d.get("analogy", ""))]
                     + [str(o.get("plain_name", "")) + " " + str(o.get("analogy", "")) for o in d.get("options") or []] + [str(q.get("text", "")) for q in d.get("questions") or []]
                     + [str(a.get("label", "")) for q in d.get("questions") or [] for a in q.get("answers") or []]
                     + [str(a) for a in assumptions]).lower()
    named = sorted({b for b in VENDORS if re.search(r"\b" + re.escape(b) + r"\b", asked)})
    if named:
        problems.append(f"the question or answers name {', '.join(named)}: ask about the need, not a product")
    text = json.dumps(d).lower()
    for w in ("%", " score", "best-in-class", "industry-leading", "seamless", "blazing", "you will learn"):
        if w in text:
            problems.append(f"uses '{w.strip()}': no scores or marketing words")
    return problems


def check_deep(d):
    """Deep-material rules for one draft; returns problems in plain words (empty = passes)."""
    problems = []
    for o in [x for x in d.get("options") or [] if not x.get("ruled_out")]:
        if not (o.get("learn") or {}).get("what"):
            problems.append(f"option '{o.get('id')}' has no plain explanation")
        numbers = o.get("numbers") or []
        if not 1 <= len(numbers) <= 4 or any(not isinstance(n, (list, tuple)) or len(n) != 2
                                             or not str(n[0]).strip() or not str(n[1]).strip() for n in numbers):
            problems.append(f"option '{o.get('id')}' needs 1 to 4 number rows")
        traj = o.get("trajectory") or []
        if len(traj) != 2 or any(not isinstance(v, (int, float)) or isinstance(v, bool) or not 0 <= v <= 10 for v in traj):
            problems.append(f"option '{o.get('id')}' needs trajectory [now, later] 0 to 10")
    growth = d.get("growth") or {}
    if not (growth.get("title") and growth.get("now") and growth.get("later")):
        problems.append("the decision needs growth title/now/later labels")
    text = (json.dumps(d.get("growth") or {}) + json.dumps([o.get("numbers") for o in d.get("options") or []])).lower()
    for w in ("%", " score", "best-in-class", "industry-leading", "seamless", "blazing", "you will learn"):
        if w in text:
            problems.append(f"deep material uses '{w.strip()}': no scores or marketing words")
    for o in d.get("options") or []:  # keep only docs links that answer
        url = (o.get("learn") or {}).get("docs_url") or ""
        if url and not link_ok(url):
            o["learn"]["docs_url"] = ""
    return problems


def link_ok(url):
    if not url.startswith("https://"):
        return False
    try:
        req = urllib.request.Request(url, method="HEAD", headers={"User-Agent": "hoist"})
        with urllib.request.urlopen(req, timeout=5) as r:
            return r.status < 400
    except Exception:
        return False


def apply_budget(plan):
    """Decision fatigue: ask about at most MAX_ASK decisions; the rest get safe defaults the person can review."""
    asks = [d for d in plan.get("decisions", []) if d.get("mode") == "ask"]
    asks.sort(key=lambda d: -int(d.get("door", 2)))
    for d in asks[MAX_ASK:]:
        d["mode"], d["budget_note"] = "default", f"over the {MAX_ASK}-question budget; default recorded for review"
    return plan


def plan_input(root, task, hints=""):
    return project_context(root, task) + (f"\n\nThe agent was about to ask the person these questions; cover them as decisions:\n{hints}" if hints else "")


def make_plan(root, task, hints=""):
    prompt = plan_input(root, task, hints)
    p = apply_budget(muse_json(PLAN_SYSTEM, prompt, f"plan:{root.name}", max_output=4000))
    (root / ".hoist").mkdir(exist_ok=True)
    (root / ".hoist" / "plan.json").write_text(json.dumps({"task": task, **p}, indent=2))
    return p


def plan(task, project):
    root = Path(project).resolve()
    p = make_plan(root, task)
    print(f"\n{p.get('task_summary', task)}\n")
    if p.get("profile"):
        print("Asked once, used by every decision")
        for q in p["profile"]:
            print(f"  - {q['text']}  [{' / '.join(q.get('answers', []))}]\n      why: {q.get('why')}  (used by: {', '.join(q.get('used_by', []))})")
        print()
    for label, mode in (("Ask you", "ask"), ("Default, review later", "default"), ("Agent's call, logged", "log")):
        rows = [d for d in p["decisions"] if d.get("mode") == mode]
        if rows:
            print(label)
            for d in rows:
                print(f"  - {d['title']} ({DOOR_WORDS.get(int(d.get('door', 2)), '')})"
                      + (f"\n      default: {d['default']}" if mode != "ask" else "") + f"\n      why: {d['why']}"
                      + (f"\n      note: {d['budget_note']}" if d.get("budget_note") else ""))
            print()


def lean_input(root, which, task=""):
    """The decision, its neighbours, the profile and the project: identical for Muse Spark and for an agent drafting."""
    plan_file = root / ".hoist" / "plan.json"
    pl = json.loads(plan_file.read_text()) if plan_file.exists() else {}
    task = task or pl.get("task", "")
    entry = next((x for x in pl.get("decisions", []) if which in (x.get("id"), x.get("title"))), None)
    title = entry["title"] if entry else which
    out = root / ".hoist" / "drafts"; out.mkdir(parents=True, exist_ok=True)
    slug = (entry or {}).get("id") or re.sub(r"[^a-z0-9]+", "-", title.lower()).strip("-")[:50]
    others = []
    for x in pl.get("decisions", []):  # lean drafts run in parallel, so only plan defaults are visible here
        if x is entry:
            continue
        others.append(f"- {x['title']} ({x.get('mode')}): {x.get('scope', '')} Default if not decided: {x.get('default')}")
    prompt = (f"Decision to draft: {title}\n" + (f"Scope: {entry.get('scope')}\n" if entry else "")
              + ("Other decisions in this task, handled elsewhere:\n" + "\n".join(others) + "\n" if others else "")
              + ("Profile questions (asked once):\n" + json.dumps(pl.get("profile", []), indent=1) + "\n" if pl.get("profile") else "")
              + "\n" + project_context(root, task))
    return pl, entry, title, slug, task, prompt


def make_draft_lean(root, which, task=""):
    """Fast first pass: everything Glance and Compare need. Runs in parallel across decisions."""
    pl, entry, title, slug, task, prompt = lean_input(root, which, task)
    out = root / ".hoist" / "drafts"; out.mkdir(parents=True, exist_ok=True)
    d = muse_json(LEAN_SYSTEM, prompt, f"lean:{root.name}")
    problems = check_draft(d, pl.get("profile"))
    if problems:  # one repair round, then report honestly
        print(f"Quality check failed ({len(problems)}): {'; '.join(problems)}. Asking Muse Spark to fix it.", file=sys.stderr)
        d = muse_json(LEAN_SYSTEM, prompt + "\n\nYour last lean draft broke these rules; fix them:\n- " + "\n- ".join(problems)
                      + "\n\nLast draft:\n" + json.dumps(d), f"lean-fix:{root.name}")
        problems = check_draft(d, pl.get("profile"))
    path = out / f"{slug}.json"
    path.write_text(json.dumps({"id": slug, "title": title, "task": task, "problems": problems, "deep": False, **d}, indent=2))
    return d, problems, path


def merge_deep(dr, payload):
    """Fold one deep payload into a lean draft dict. Unknown option ids are ignored."""
    out = json.loads(json.dumps(dr))
    if isinstance(payload.get("growth"), dict):
        out["growth"] = payload["growth"]
    by_id = {o.get("id"): o for o in out.get("options", [])}
    for e in payload.get("deep_options") or []:
        o = by_id.get(e.get("id"))
        if not o:
            continue
        for k in ("numbers", "trajectory", "learn", "check_current"):
            if k in e:
                o[k] = e[k]
    out["deep"] = True
    return out


def deepen_draft(root, did):
    """Fill one lean draft's deep material (numbers, growth, learn). Returns the merged draft; cheap no-op when done."""
    f = root / ".hoist" / "drafts" / f"{did}.json"
    dr = json.loads(f.read_text())
    if dr.get("deep"):
        return dr
    task = dr.get("task", "")
    lean = {k: v for k, v in dr.items() if k not in ("deep", "problems", "deep_problems")}
    prompt = (f"Decision: {dr.get('title', did)}\nTask: {task}\n\nLean draft:\n{json.dumps(lean, indent=1)}\n\n"
              + project_context(root, task))
    payload = muse_json(DEEP_SYSTEM, prompt, f"deep:{root.name}:{did}")
    merged = merge_deep(dr, payload)
    problems = check_deep(merged)
    if problems:  # one repair round, then report honestly
        print(f"Deep check failed ({len(problems)}): {'; '.join(problems)}. Asking Muse Spark to fix it.", file=sys.stderr)
        payload = muse_json(DEEP_SYSTEM, prompt + "\n\nYour last deep material broke these rules; fix them:\n- " + "\n- ".join(problems)
                            + "\n\nLast deep material:\n" + json.dumps(payload), f"deep-fix:{root.name}:{did}")
        merged = merge_deep(dr, payload)
        problems = check_deep(merged)
    merged["deep_problems"] = problems
    f.write_text(json.dumps(merged, indent=2))
    return merged


def make_draft(root, which, task=""):
    """Full draft for the CLI: lean first, then deep inline."""
    d, problems, path = make_draft_lean(root, which, task)
    try:
        d = deepen_draft(root, path.stem)
        problems = list(problems) + [f"deep: {p}" for p in d.get("deep_problems", [])]
    except (Exception, SystemExit) as e:
        problems = list(problems) + [f"deep draft failed: {e}"]
        d = json.loads(path.read_text())
    return d, problems, path


def draft(which, task, project):
    root = Path(project).resolve()
    d, problems, path = make_draft(root, which, task)
    print(f"\n{d.get('question')}\n  why now: {d.get('why_now')}\n  undo:    {d.get('undo')}"
          + (f"\n  assumes: {d['assumes']}" if d.get("assumes") else ""))
    for pe in d.get("profile_effects", []):
        print(f"\n  uses profile '{pe['profile_id']}':")
        for a in pe.get("answers", []):
            print(f"     - {a['label']}: " + "; ".join(f"{e['dir']} {e['option']} ({e['reason']})" for e in a.get("effects", [])))
    for q in d.get("questions", []):
        print(f"\n  OWN QUESTION: {q['text']}\n     ({q.get('why')})" + (f"\n     new to this: {q['beginner_note']}" if q.get("beginner_note") else ""))
        for a in q.get("answers", []):
            print(f"     - {a['label']}: " + "; ".join(f"{e['dir']} {e['option']} ({e['reason']})" for e in a.get("effects", [])))
    for o in d.get("options", []):
        tag = f"  [ruled out: {o['ruled_out']}]" if o.get("ruled_out") else ""
        print(f"\n  OPTION {o['name']}: {o.get('summary')}{tag}")
        for g in o.get("good", []): print(f"     + ({g['when']}) {g['text']}")
        for b in o.get("bad", []): print(f"     - ({b['when']}) {b['text']}")
        lrn = o.get("learn") or {}
        print(f"     learn: {lrn.get('what', '')}" + (f"\n     check it's current: {o['check_current']}" if o.get("check_current") else "")
              + (f"\n     docs: {lrn['docs_url']}" if lrn.get("docs_url") else ""))
        print(f"     journey: {' → '.join(o.get('journey') or [])} · micro {o.get('micro')}")
    if d.get("agent_pick"):
        print(f"\n  lean: {d['agent_pick']}" + (f" — {(d.get('lean') or {}).get('why', '')}" if (d.get("lean") or {}).get("why") else ""))
        for a in (d.get("lean") or {}).get("assumptions", []):
            print(f"     assumes: {a}")
        for f in (d.get("lean") or {}).get("flips", []):
            print(f"     flips if: {f}")
    print(f"\n  default if you don't mind: {d.get('default_option')} ({d.get('default_reason')})")
    print(f"  quality check: {'passed' if not problems else 'still failing: ' + '; '.join(problems)}")
    print(f"  saved: {path.relative_to(root)}")


# ---------- sessions: a task's decisions, planned and drafted in the background ----------
def session_file(root):
    return root / ".hoist" / "session.json"


def load_session(root):
    f = session_file(root)
    return json.loads(f.read_text()) if f.exists() else None


def save_session(root, ses):
    (root / ".hoist").mkdir(exist_ok=True)
    session_file(root).write_text(json.dumps(ses, indent=2))


def ensure_key():
    """The page server may start without MODEL_API_KEY; read it from the macOS Keychain entry `hoist install` documents."""
    if os.environ.get("MODEL_API_KEY"):
        return True
    try:
        out = subprocess.run(["security", "find-generic-password", "-s", "hoist-meta-api", "-w"], capture_output=True, text=True, timeout=10)
    except (OSError, subprocess.SubprocessError):
        return False
    if out.returncode == 0 and out.stdout.strip():
        os.environ["MODEL_API_KEY"] = out.stdout.strip()
        return True
    return False


def run_session(root, task, hints="", resume=False):
    """Plan the task, then draft each decision the person is asked. Progress goes to .hoist/session.json for the page.
    With resume, keep the plan and finished drafts and only redo what failed."""
    old = load_session(root) if resume else None
    plan_file = root / ".hoist" / "plan.json"
    resume = bool(old and plan_file.exists())
    ses = old if resume else {"task": task, "drafted": [], "total": 0, "profile_answers": {}, "answers": {}, "outcomes": {},
                              "from_questionnaire": bool(hints)}
    ses.update(status="drafting" if resume else "planning", started=time.strftime("%Y-%m-%d %H:%M:%S"), error=None, failed=[])
    save_session(root, ses)
    try:
        if not ensure_key():
            raise RuntimeError("No Muse Spark key. Export MODEL_API_KEY before starting Muse Code, or on macOS save it with: "
                               "security add-generic-password -a \"$USER\" -s hoist-meta-api -w")
        if resume:
            p = json.loads(plan_file.read_text())
        else:
            shutil.rmtree(root / ".hoist" / "drafts", ignore_errors=True)
            p = make_plan(root, task, hints)
        asks = [d["id"] for d in p.get("decisions", []) if d.get("mode") == "ask"]
        ses.update(status="drafting", total=len(asks))
        save_session(root, ses)
        todo = [did for did in asks if did not in ses["drafted"]]
        with concurrent.futures.ThreadPoolExecutor(max_workers=min(4, len(todo) or 1)) as ex:
            futs = {ex.submit(make_draft_lean, root, did, ses["task"]): did for did in todo}
            for fut in concurrent.futures.as_completed(futs):
                did = futs[fut]
                try:
                    fut.result()
                    if did not in ses["drafted"]:
                        ses["drafted"].append(did)
                except (Exception, SystemExit):  # this decision falls back to its default on the page; the rest go on
                    ses["failed"].append(did)
                ses["current"] = next((x for x in todo if x not in ses["drafted"] and x not in ses["failed"]), None)
                save_session(root, ses)
        if asks and len(ses["failed"]) == len(asks):
            raise RuntimeError("Muse Spark couldn't write any of the decisions.")
        ses.update(status="ready", current=None)
    except (Exception, SystemExit) as e:  # muse_json exits on early stops; report it on the page instead
        ses.update(status="error", error=str(e) or e.__class__.__name__)
    save_session(root, ses)


def session_state(root):
    ses = load_session(root)
    if not ses:
        return None
    plan_file, drafts = root / ".hoist" / "plan.json", root / ".hoist" / "drafts"
    ses["plan"] = json.loads(plan_file.read_text()) if plan_file.exists() and ses["status"] != "planning" else None
    ses["drafts"] = {p.stem: json.loads(p.read_text()) for p in sorted(drafts.glob("*.json"))} if drafts.exists() else {}
    return ses


def start(task, project):
    """Start a session through the page server, so the page shows Muse Spark's progress live."""
    root = Path(project).resolve()
    if not ensure_server(root):
        sys.exit(f"Hoist couldn't start its page on {URL}. Is another project's Hoist running?")
    if effective_drafter(root) == "agent":
        start_agent_session(root, task)
        webbrowser.open(f"{URL}/#/session")
        print(f"HOIST: session started for \"{task}\". Run `{hoist_cmd()} brief` to draft the decisions, then `{hoist_cmd()} wait`.")
        return
    if not post_session(task):
        sys.exit("Hoist: couldn't start the session. Is the page server answering?")
    webbrowser.open(f"{URL}/#/session")
    print(f"HOIST: Muse Spark is preparing the decisions for \"{task}\". Follow along at {URL}/#/session")


# ---------- agent drafting: the agent (or a subagent it starts) writes the plan and drafts; Hoist checks them ----------
def hoist_cmd():
    return f"python3 {shlex.quote(str(HOME / 'hoist.py'))}"


def start_agent_session(root, task, hints=""):
    """A session the agent fills in through `hoist brief` / `hoist submit`; the page shows it as it arrives."""
    (root / ".hoist").mkdir(exist_ok=True)
    (root / ".hoist" / "plan.json").unlink(missing_ok=True)
    shutil.rmtree(root / ".hoist" / "drafts", ignore_errors=True)
    shutil.rmtree(root / ".hoist" / "agent", ignore_errors=True)
    save_session(root, {"task": task, "hints": hints, "drafter": "agent", "status": "planning", "drafted": [], "failed": [],
                        "total": 0, "attempts": {}, "profile_answers": {}, "answers": {}, "outcomes": {},
                        "from_questionnaire": bool(hints), "started": time.strftime("%Y-%m-%d %H:%M:%S"), "error": None})


def agent_session(root):
    ses = load_session(root)
    if not ses or ses.get("drafter") != "agent" or ses.get("status") not in ("planning", "drafting"):
        return None
    return ses


def brief(project):
    """Print the next thing for the agent to draft: the plan first, then one decision at a time."""
    root = Path(project).resolve()
    ses = agent_session(root)
    hc = hoist_cmd()
    if not ses:
        print("HOIST: nothing to draft. If the user has decisions open, run `" + hc + " wait`.")
        return
    work = root / ".hoist" / "agent"
    work.mkdir(parents=True, exist_ok=True)
    rule = "-" * 64
    if ses["status"] == "planning":
        out = work / "plan.json"
        print(f"{rule}\nHOIST BRIEF · step 1: plan the decisions for \"{ses['task']}\"\n{rule}\n"
              "You are drafting for Hoist. If you can start a subagent, hand it this whole brief so the drafting starts fresh, "
              "without your own preferences; otherwise do it yourself. Follow the contract exactly.\n")
        print(PLAN_SYSTEM + "\n\n" + rule + "\nINPUT\n" + rule + "\n" + plan_input(root, ses["task"], ses.get("hints", "")))
        print(f"\n{rule}\nWrite only the JSON object to {out}\nThen run: {hc} submit plan {shlex.quote(str(out))}\n{rule}")
        return
    pl = json.loads((root / ".hoist" / "plan.json").read_text())
    asks = [d["id"] for d in pl.get("decisions", []) if d.get("mode") == "ask"]
    todo = [a for a in asks if a not in ses["drafted"]]
    if not todo:
        print(f"HOIST: every decision is drafted. Run `{hc} wait` and let it finish.")
        return
    did = todo[0]
    _, _, title, _, _, prompt = lean_input(root, did, ses["task"])
    out = work / f"{did}.json"
    print(f"{rule}\nHOIST BRIEF · step {asks.index(did) + 2} of {len(asks) + 1}: draft \"{title}\" for the person\n{rule}\n"
          "Write it so a smart newcomer can decide. Do not decide for them: the page shows every option fairly, "
          "and your own pick goes only in agent_pick and lean.\n")
    print(LEAN_SYSTEM + "\n\n" + rule + "\nINPUT\n" + rule + "\n" + prompt)
    print(f"\n{rule}\nWrite only the JSON object to {out}\nThen run: {hc} submit draft {did} {shlex.quote(str(out))}\n{rule}")


def submit(kind, args, project):
    """Accept the agent's plan or one draft after the same checks Muse Spark's drafts get. Exit 1 with fixes to make."""
    import hoist_audit
    root = Path(project).resolve()
    ses = agent_session(root)
    hc = hoist_cmd()
    if not ses:
        sys.exit("HOIST: no session is waiting for drafts. Run `" + hc + " wait` if the user is deciding.")
    if not args:
        sys.exit("HOIST: say which file to submit.")
    try:
        d = hoist_audit.parse(Path(args[-1]).read_text())
    except (OSError, ValueError) as e:
        sys.exit(f"HOIST: couldn't read JSON from {args[-1]} ({e}). Write only the JSON object and submit again.")
    if kind == "plan":
        if ses["status"] != "planning":
            sys.exit("HOIST: the plan is already in. Run `" + hc + " brief` for the next step.")
        if not isinstance(d.get("decisions"), list) or not all(isinstance(x, dict) and x.get("id") and x.get("mode") for x in d["decisions"]):
            sys.exit("HOIST: the plan needs a \"decisions\" list, each with an id and a mode (ask, default or log). Fix it and submit again.")
        p = apply_budget(d)
        (root / ".hoist" / "plan.json").write_text(json.dumps({"task": ses["task"], **p}, indent=2))
        asks = [x["id"] for x in p["decisions"] if x.get("mode") == "ask"]
        ses.update(status="drafting" if asks else "ready", total=len(asks))
        save_session(root, ses)
        print(f"HOIST: plan accepted — {len(asks)} decision(s) for the person." + (f" Run `{hc} brief` for the first one." if asks else f" Nothing to ask; run `{hc} wait`."))
        return
    did = args[0] if len(args) > 1 else ""
    pl = json.loads((root / ".hoist" / "plan.json").read_text())
    asks = [x["id"] for x in pl.get("decisions", []) if x.get("mode") == "ask"]
    if did not in asks:
        sys.exit(f"HOIST: {did or 'that'} isn't one of this task's decisions ({', '.join(asks)}).")
    problems = check_draft(d, pl.get("profile"))
    tries = ses.setdefault("attempts", {}).get(did, 0) + 1
    ses["attempts"][did] = tries
    save_session(root, ses)
    if problems and tries < 2:  # one repair round, the same as Muse Spark gets
        print(f"HOIST: this draft breaks {len(problems)} rule(s). Fix them in {args[-1]} and submit again:\n- " + "\n- ".join(problems))
        sys.exit(1)
    _, _, title, slug, task, _ = lean_input(root, did, ses["task"])
    out = root / ".hoist" / "drafts"; out.mkdir(parents=True, exist_ok=True)
    (out / f"{slug}.json").write_text(json.dumps({"id": slug, "title": title, "task": task, "problems": problems, "deep": False,
                                                  "drafter": "agent", **d}, indent=2))
    if did not in ses["drafted"]:
        ses["drafted"].append(did)
    left = [a for a in asks if a not in ses["drafted"]]
    if not left:
        ses.update(status="ready", current=None)
    save_session(root, ses)
    note = f" with {len(problems)} open issue(s), kept in the draft" if problems else ""
    print(f"HOIST: \"{title}\" accepted{note}. " + (f"{len(left)} to go — run `{hc} brief`." if left
          else f"Every decision is on the page now. Run `{hc} wait` and let it finish."))


# ---------- install ----------
def install(project):
    root = Path(project).resolve()
    if not root.is_dir():
        sys.exit(f"No project folder at {root}. Create it (or cd into your project) and run install again.")
    hooks_file = root / ".muse" / "hooks.json"
    hooks_file.parent.mkdir(exist_ok=True)
    cfg = json.loads(hooks_file.read_text()) if hooks_file.exists() else {}
    hooks = cfg.setdefault("hooks", {})
    cmd = f"{shlex.quote(sys.executable)} {shlex.quote(str(HOME / 'hoist.py'))} gate"
    for event in list(hooks):  # drop earlier Hoist entries anywhere (older installs, test copies)
        hooks[event] = [e for e in hooks[event] if "hoist.py" not in json.dumps(e)]
        if not hooks[event]:
            del hooks[event]
    for event, matcher in (("UserPromptSubmit", None), ("PreToolUse", "*"), ("PostToolBatch", None)):
        keep = hooks.get(event, [])
        entry = {"hooks": [{"type": "command", "command": cmd, "timeout": HOOK_TIMEOUT}]}
        if matcher:
            entry = {"matcher": matcher, **entry}
        hooks[event] = keep + [entry]
    hooks_file.write_text(json.dumps(cfg, indent=2) + "\n")
    skill = root / ".agents" / "skills" / "hoist" / "SKILL.md"
    skill.parent.mkdir(parents=True, exist_ok=True)
    skill.write_text((HOME / "skill" / "SKILL.md").read_text())
    readme = records_dir(root) / "README.md"
    if not readme.exists():
        readme.write_text("# Decisions\n\nLasting decisions for this project, one MADR file each, written by Hoist.\n"
                          f"Browse them at {URL}/#/records while `python3 {HOME / 'hoist.py'} serve` is running.\n")
    gi = root / ".gitignore"
    lines = gi.read_text().splitlines() if gi.exists() else []
    if ".hoist/" not in lines:
        gi.write_text("\n".join(lines + [".hoist/"]) + "\n")
    print(f"Hoist installed in {root}")
    print(f"  hook:    {hooks_file.relative_to(root)} (UserPromptSubmit, PreToolUse, PostToolBatch)")
    print(f"  skill:   {skill.relative_to(root)}")
    print(f"  records: docs/decisions/")
    print("Restart Muse Code in this folder and trust it, so the hook loads.")
    print("Drafting: your agent writes the decisions (no key needed)." if not ensure_key() else
          "Drafting: your agent writes the decisions. A Muse Spark key is available: `hoist.py drafter muse` makes Muse Spark "
          "the independent drafter and turns on the live critic.")


def main():
    ap = argparse.ArgumentParser(description="Pause coding agents at decisions that are hard to undo, and record what you choose.")
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("install", help="Add Hoist to a project").add_argument("project", nargs="?", default=".")
    sub.add_parser("serve", help="Run the decision page").add_argument("project", nargs="?", default=".")
    sub.add_parser("gate", help="Muse Code hook entry point (payload on stdin)")
    w = sub.add_parser("wait", help="Wait for a decision, then print the outcome")
    w.add_argument("id", nargs="?", default=None, help="Decision ID; default: the open one"); w.add_argument("project", nargs="?", default=".")
    st = sub.add_parser("start", help="Plan and draft a task's decisions, then open the page")
    st.add_argument("task"); st.add_argument("project", nargs="?", default=".")
    pl = sub.add_parser("plan", help="Muse Spark: list the lasting decisions a task will force")
    pl.add_argument("task"); pl.add_argument("project", nargs="?", default=".")
    dr = sub.add_parser("draft", help="Muse Spark: write one decision for the person to make")
    dr.add_argument("title", help="Decision id from the plan, or a title"); dr.add_argument("--task", default=""); dr.add_argument("project", nargs="?", default=".")
    md_ = sub.add_parser("mode", help="Show or set how Hoist handles hard choices: ask (default) or autopilot")
    md_.add_argument("args", nargs="*", metavar="[ask|autopilot] [project]")
    dr_ = sub.add_parser("drafter", help="Show or set who drafts the decisions: agent (default, no key) or muse (Muse Spark key)")
    dr_.add_argument("args", nargs="*", metavar="[agent|muse] [project]")
    br = sub.add_parser("brief", help="For the agent: print the next plan or decision to draft")
    br.add_argument("project", nargs="?", default=".")
    sb = sub.add_parser("submit", help="For the agent: hand in the plan or one decision draft")
    sb.add_argument("kind", choices=("plan", "draft")); sb.add_argument("args", nargs="+", metavar="[ID] FILE")
    sb.add_argument("--project", default=".")
    lg = sub.add_parser("log", help="Record a decision the agent made on autopilot")
    lg.add_argument("title", help="The decision, as a short title"); lg.add_argument("--chose", required=True)
    lg.add_argument("--because", required=True); lg.add_argument("--options", default="", help='Other options considered, "A|B|C"')
    lg.add_argument("--project", default=".")
    args = ap.parse_args()
    if args.cmd == "install":
        install(args.project)
    elif args.cmd == "serve":
        serve(args.project)
    elif args.cmd == "start":
        start(args.task, args.project)
    elif args.cmd == "plan":
        plan(args.task, args.project)
    elif args.cmd == "draft":
        draft(args.title, args.task, args.project)
    elif args.cmd == "gate":
        sys.exit(gate())
    elif args.cmd == "mode":
        want = next((a for a in args.args if a in MODES), None)
        rest = [a for a in args.args if a not in MODES]
        if len(rest) > 1:
            sys.exit("usage: hoist.py mode [ask|autopilot] [project]")
        root = Path(rest[0] if rest else ".").resolve()
        if want:
            set_mode(root, want)
        m = get_mode(root)
        print(f"Hoist mode for {root.name}: {m}. " + ("Your agent makes hard-to-undo calls itself and Hoist records each one for you to review."
              if m == "autopilot" else "Hoist pauses your agent at hard-to-undo calls so you can decide."))
    elif args.cmd == "drafter":
        want = next((a for a in args.args if a in DRAFTERS), None)
        rest = [a for a in args.args if a not in DRAFTERS]
        if len(rest) > 1:
            sys.exit("usage: hoist.py drafter [agent|muse] [project]")
        root = Path(rest[0] if rest else ".").resolve()
        if want:
            set_config(root, "drafter", want)
        d, eff = get_drafter(root), effective_drafter(root)
        print(f"Hoist drafter for {root.name}: {d}. " + ("Your agent writes the decisions (a subagent if it can); Hoist checks them. No key needed."
              if eff == "agent" and d == "agent" else "Muse Spark writes the decisions, an independent second opinion." if eff == "muse"
              else "Muse Spark was asked for, but no key was found, so your agent drafts for now."))
    elif args.cmd == "brief":
        brief(args.project)
    elif args.cmd == "submit":
        submit(args.kind, args.args, args.project)
    elif args.cmd == "log":
        log_decision(args.title, args.chose, args.because, args.options, args.project)
    else:
        wait(args.id, args.project)


if __name__ == "__main__":
    main()
