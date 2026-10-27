#!/usr/bin/env python3
"""hoist: pause a coding agent at decisions that are hard to undo, decide with the user, record the choice.

Commands:
  python3 hoist.py install [project]   add Hoist to a project (Muse Code hook, skill, docs/decisions)
  python3 hoist.py serve [project]     run the decision page on http://127.0.0.1:7317
  python3 hoist.py gate                Muse Code hook entry point (reads the hook payload on stdin)
  python3 hoist.py wait ID [project]   wait until decision ID is made, then print the outcome

Standard library only. The page and its server listen on 127.0.0.1 and never call an API.
"""
import argparse, json, os, re, shlex, shutil, socket, subprocess, sys, threading, time, urllib.request, webbrowser
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
    who = "chose" if dec.get("mode") == "chosen" else "let Hoist pick"
    skip = f"Do not add `{pkg}`. " if pkg not in k["packages"].get(dec.get("choice"), []) else ""
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


def picked_hoist(answers):
    return any(a.get("selected_label") == HOIST_PICK or HOIST_PICK in (a.get("selected_labels") or []) for a in answers)


def questionnaire_handoff(payload, root):
    """PostToolBatch: the only hook that sees the questionnaire (PreToolUse and PostToolUse skip it).
    When the person picked Hoist, start a session with the agent's questions as hints and open the page."""
    for call in payload.get("tool_calls") or []:
        if "request_user_input" not in str(call.get("tool_name")) or not picked_hoist(questionnaire_answers(call)):
            continue
        questions = (call.get("tool_input") or {}).get("questions") or []
        hints = "\n".join("- " + str(q.get("question", "")) + " Options the agent offered: "
                          + ", ".join(str(o.get("label", "")) for o in q.get("options") or [] if o.get("label") != HOIST_PICK)
                          for q in questions)
        task_file = root / ".hoist" / "last_task.txt"
        task = task_file.read_text().strip() if task_file.exists() else "The current task"
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
    if port_open():  # something else holds the port, likely a server for another project
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


def serving(root):
    try:
        with urllib.request.urlopen(f"{URL}/api/state", timeout=1) as r:
            return json.loads(r.read()).get("root") == str(root)
    except (OSError, ValueError):
        return False


# ---------- the local page ----------
def make_handler(root):
    allowed = {f"http://127.0.0.1:{PORT}", f"http://localhost:{PORT}"}

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
            if path == "/api/state":
                records = [{"file": p.name, "markdown": p.read_text()} for p in sorted(records_dir(root).glob("[0-9][0-9][0-9][0-9]-*.md"))]
                return self.send(200, {"project": root.name, "root": str(root), "live": True, "decisions": load_decisions(root),
                                       "records": records, "session": session_state(root)})
            self.send(404, {"error": "not found"})

        def do_POST(self):
            if self.headers.get("Origin") not in allowed:
                return self.send(403, {"error": "Requests must come from the Hoist page."})
            body = json.loads(self.rfile.read(int(self.headers.get("Content-Length", 0))) or "{}")
            if self.path == "/api/session":
                ses = load_session(root)
                if ses and ses["status"] in ("planning", "drafting"):
                    return self.send(409, {"error": "Muse Spark is still preparing the last task."})
                task = str(body.get("task", "")).strip()[:500]
                if not task:
                    return self.send(400, {"error": "Describe the task first."})
                hints = str(body.get("hints", ""))[:4000]
                threading.Thread(target=run_session, args=(root, task, hints), daemon=True).start()
                time.sleep(0.2)
                return self.send(200, session_state(root))
            if self.path == "/api/session/answers":
                ses = load_session(root)
                if not ses:
                    return self.send(404, {"error": "No session."})
                ses["profile_answers"].update(body.get("profile_answers", {}))
                for k, v in (body.get("answers") or {}).items():
                    ses["answers"].setdefault(k, {}).update(v)
                save_session(root, ses)
                return self.send(200, session_state(root))
            m = re.fullmatch(r"/api/session/decisions/([a-z0-9-]{1,60})", self.path)
            if m:
                ses = load_session(root)
                if not ses or m.group(1) not in ses.get("drafted", []) + [x["id"] for x in (session_state(root).get("plan") or {}).get("decisions", [])]:
                    return self.send(404, {"error": "No such decision in this task."})
                slug = re.sub(r"[^a-z0-9-]+", "-", str(body.get("slug", "decision")).lower()).strip("-")[:60] or "decision"
                name = f"{next_id(root)}-{slug}.md"
                (records_dir(root) / name).write_text(str(body.get("markdown", "")))
                ses["outcomes"][m.group(1)] = {"choice": body.get("choice"), "mode": body.get("mode"), "record": f"docs/decisions/{name}"}
                save_session(root, ses)
                return self.send(200, session_state(root))
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


def serve(project):
    root = Path(project).resolve()
    print(f"Hoist decision page for {root.name}: {URL}  (Ctrl+C to stop)")
    ThreadingHTTPServer(("127.0.0.1", PORT), make_handler(root)).serve_forever()


def wait(did, project):
    root = Path(project).resolve()
    if not did:
        waiting = [d for d in load_decisions(root) if d["status"] == "open"]
        ses = session_state(root)
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


def session_open(ses):
    asks = [d["id"] for d in ((ses.get("plan") or {}).get("decisions") or []) if d.get("mode") == "ask"]
    return ses["status"] == "ready" and any(a not in ses.get("outcomes", {}) for a in asks)


def wait_session(root):
    line = "-" * 64
    ses = session_state(root)
    print(f"{line}\nHOIST: paused while you make this task's lasting decisions\n  Task:       {ses['task']}\n"
          f"  Decide at:  {URL}/#/session\n  Muse Spark prepares them first; the agent continues when you're done.\n{line}", flush=True)
    while True:
        ses = session_state(root)
        if ses["status"] == "error":
            print(f"HOIST: Muse Spark couldn't prepare the decisions ({ses.get('error')}). Ask the user in chat instead.")
            return
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
        elif o and o.get("choice"):
            name = next((x["name"] for x in dr.get("options", []) if x["id"] == o["choice"]), o["choice"])
            print(f"- {d['title']}: {name} ({o['record']})")
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
- Only decisions this task needs now. Skip anything already decided in the recorded decisions or visible in the project files.
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
- Never about products or technologies. Never ask for numbers they cannot know. No invented scenarios.
- Each one must matter to at least one "ask" decision; list which in used_by.
- 2 to 4 short answers each, plus beginner_note (one sentence explaining any term, or empty).

Reply with JSON only:
{"task_summary": str,
 "profile": [{"id": "kebab-case", "text": str, "why": "one sentence: what it changes", "beginner_note": str,
   "answers": [str], "used_by": [decision ids]}],
 "decisions": [{"id": "kebab-case", "title": "plain verb phrase", "scope": "one sentence: what this decision covers and what it leaves to others",
   "door": 1|2|3, "owner": "you"|"agent", "mode": "ask"|"default"|"log", "default": str, "why": str, "depends_on": [ids]}]}"""

DRAFT_SYSTEM = """You are Hoist. You help a person make one decision that an AI agent is about to make for them and
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
 "profile_effects": [{"profile_id": "id from the profile", "answers": [{"label": "exact answer text from the profile",
   "effects": [{"option": "option id", "dir": "favors"|"against", "reason": "short"}]}]}],
 "questions": [{"id": "kebab-case", "text": "...", "why": "one sentence: what the answer changes",
   "beginner_note": "one sentence explaining any term in the question, or empty",
   "answers": [{"label": "short answer", "effects": [{"option": "option id", "dir": "favors"|"against", "reason": "short"}]}]}],
 "options": [{"id": "kebab-case", "name": "...", "summary": "one line",
   "good": [{"when": "now"|"later", "text": "..."}], "bad": [{"when": "now"|"later", "text": "..."}],
   "learn": {"what": "two plain sentences describing what it is and how it works", "living_with": "two sentences on what day-to-day life with it is like",
     "terms": [{"term": "...", "meaning": "one line"}], "docs_url": "official documentation home page, or empty if unsure"},
   "check_current": "if the option names a product, vendor, plan, or price: one sentence on what to confirm is still true before relying on it; else empty",
   "ruled_out": "" or "reason it cannot work here"}],
 "default_option": "option id", "default_reason": "one sentence",
 "agent_pick": "option id or empty",
 "evidence": [{"source": "file name" | "task" | "profile" | "inferred", "detail": "..."}]}

Rules for questions:
- Use the profile first: map each relevant profile answer to effects in profile_effects. Do not ask a profile question again.
- Add at most 1 question of your own, only if no profile question decides this. Same standards as the profile:
  about their situation, never about technology, no numbers they cannot know, no invented scenarios.
- Every answer lists at least one effect with a reason.
Rules for options:
- 2 to 4 options that could really work, at the same level (compare like with like). Include the agent's pick.
- Prefer kinds of solution over brand names. Name a product only when it is the usual concrete choice, and then fill check_current.
- Put options that cannot work given the evidence in ruled_out with the reason instead of leaving them as weak choices.
- Every option has at least one bad item and at least one item about later.
- learn describes the option itself. Never write "you will learn".
- terms: up to 4 terms the option's text uses that a newcomer may not know."""


def project_context(root, task, limit=9000):
    import hoist_audit
    parts = [f"Task: {task}", f"Project folder: {root.name}"]
    recs = [p for p in sorted(records_dir(root).glob("[0-9][0-9][0-9][0-9]-*.md"))]
    if recs:
        parts.append("Recorded decisions:\n" + "\n".join(f"- {p.read_text().split(chr(10) + '# ', 1)[-1].splitlines()[0]}" for p in recs))
    parts.append(hoist_audit.pack(root)[:limit])
    return "\n\n".join(parts)


def muse_json(system, prompt, label, max_output=8000):
    import hoist_audit
    text, finish = hoist_audit.ask_muse(system, prompt, label, max_output=max_output)
    if finish != "stop":
        sys.exit(f"Muse Spark stopped early (finish reason: {finish}). Run the command again.")
    return hoist_audit.parse(text)


def check_draft(d, profile=None):
    """Quality rules from the ADR guidance; returns problems in plain words (empty = passes)."""
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
        if not (o.get("learn") or {}).get("what"):
            problems.append(f"option '{o.get('id')}' has no plain explanation")
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
    if d.get("default_option") not in {o.get("id") for o in viable}:
        problems.append("default_option is not a workable option")
    text = json.dumps(d).lower()
    for w in ("%", " score", "best-in-class", "industry-leading", "seamless", "blazing", "you will learn"):
        if w in text:
            problems.append(f"uses '{w.strip()}': no scores or marketing words")
    for o in opts:  # keep only docs links that answer
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


def make_plan(root, task, hints=""):
    prompt = project_context(root, task) + (f"\n\nThe agent was about to ask the person these questions; cover them as decisions:\n{hints}" if hints else "")
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


def make_draft(root, which, task=""):
    plan_file = root / ".hoist" / "plan.json"
    pl = json.loads(plan_file.read_text()) if plan_file.exists() else {}
    task = task or pl.get("task", "")
    entry = next((x for x in pl.get("decisions", []) if which in (x.get("id"), x.get("title"))), None)
    title = entry["title"] if entry else which
    out = root / ".hoist" / "drafts"; out.mkdir(parents=True, exist_ok=True)
    slug = (entry or {}).get("id") or re.sub(r"[^a-z0-9]+", "-", title.lower()).strip("-")[:50]
    others = []
    for x in pl.get("decisions", []):
        if x is entry:
            continue
        f = out / f"{x['id']}.json"
        default = json.loads(f.read_text()).get("default_option") if f.exists() else x.get("default")
        others.append(f"- {x['title']} ({x.get('mode')}): {x.get('scope', '')} Default if not decided: {default}")
    prompt = (f"Decision to draft: {title}\n" + (f"Scope: {entry.get('scope')}\n" if entry else "")
              + ("Other decisions in this task, handled elsewhere:\n" + "\n".join(others) + "\n" if others else "")
              + ("Profile questions (asked once):\n" + json.dumps(pl.get("profile", []), indent=1) + "\n" if pl.get("profile") else "")
              + "\n" + project_context(root, task))
    d = muse_json(DRAFT_SYSTEM, prompt, f"draft:{root.name}")
    problems = check_draft(d, pl.get("profile"))
    if problems:  # one repair round, then report honestly
        print(f"Quality check failed ({len(problems)}): {'; '.join(problems)}. Asking Muse Spark to fix it.", file=sys.stderr)
        d = muse_json(DRAFT_SYSTEM, prompt + "\n\nYour last draft broke these rules; fix them:\n- " + "\n- ".join(problems)
                      + "\n\nLast draft:\n" + json.dumps(d), f"draft-fix:{root.name}")
        problems = check_draft(d, pl.get("profile"))
    path = out / f"{slug}.json"
    path.write_text(json.dumps({"id": slug, "title": title, "task": task, "problems": problems, **d}, indent=2))
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


def run_session(root, task, hints=""):
    """Plan the task, then draft each decision the person is asked. Progress goes to .hoist/session.json for the page."""
    ses = {"task": task, "status": "planning", "started": time.strftime("%Y-%m-%d %H:%M:%S"), "drafted": [], "total": 0,
           "profile_answers": {}, "answers": {}, "outcomes": {}, "from_questionnaire": bool(hints)}
    save_session(root, ses)
    try:
        if not ensure_key():
            raise RuntimeError("No Muse Spark key. Save it with: security add-generic-password -a \"$USER\" -s hoist-meta-api -w")
        shutil.rmtree(root / ".hoist" / "drafts", ignore_errors=True)
        p = make_plan(root, task, hints)
        asks = [d["id"] for d in p.get("decisions", []) if d.get("mode") == "ask"]
        ses.update(status="drafting", total=len(asks))
        save_session(root, ses)
        for did in asks:
            ses["current"] = did; save_session(root, ses)
            make_draft(root, did, task)
            ses["drafted"].append(did); save_session(root, ses)
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
    if not post_session(task):
        sys.exit("Hoist: couldn't start the session. Is the page server answering?")
    webbrowser.open(f"{URL}/#/session")
    print(f"HOIST: Muse Spark is preparing the decisions for \"{task}\". Follow along at {URL}/#/session")


# ---------- install ----------
def install(project):
    root = Path(project).resolve()
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
    else:
        wait(args.id, args.project)


if __name__ == "__main__":
    main()
