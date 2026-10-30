# Hoist

You've got an idea and an agent to build it. Whatever you build, the agent will ask you things: option one, option two, option three. Some of those answers take weeks to undo. Hoist stops the agent at those questions, answers the questions you'd have before you ask them, lets you decide, and writes the decision down so the next agent (or future you) knows why.

- **Try the demo** (sample data, runs in the browser): pick an idea (cake pre-orders, dog-walk bookings or a paid newsletter) and decide its hard questions: https://leadui.github.io/hoist-decisions/
- **Read the pitch:** https://leadui.github.io/hoist-decisions/landing.html
- **Built on [Bento MADR](https://github.com/leadui/bento-madr)**, the decision-canvas library that started here.

Built for the Meta Global AI Developer Hackathon with **Muse Code** (the agent Hoist guards) and, optionally, **Muse Spark** (an independent drafter and critic). No API key is needed: by default your agent drafts the decisions and Hoist checks them.

What Hoist stands for:

- **It's okay to pause.** A pause costs a minute; a wrong call can cost weeks.
- **It's okay to ask dumb questions.** Every option comes with an everyday analogy, what living with it is like, and the terms explained.
- **It's okay to take your time.** Decide later, send it back to chat, or pick for now. The record says why, so changing it later is a plan, not a regret.
- **It's not okay to say yes to everything.** When speed matters, autopilot lets the agent decide, and Hoist writes every call down for you to review.

## How it works

Hoist steps in at two moments.

**When the agent is about to ask you something hard to undo**, Hoist's skill has it ask one question first: *"These are hard to change later. How do you want to decide?"* with **Answer here** or **Decide with Hoist instead**. If you pick Hoist:

1. Your agent drafts the decisions for the page through `hoist brief` and `hoist submit`, handing the work to a fresh subagent when it can, so the options aren't shaped by its own favourite. Hoist checks every draft against its rules (plain words, fair options, an honest downside for each) and sends problems back to fix. With a Muse Spark key you can make Muse Spark the drafter instead.
2. Your browser opens the decision page. Each decision is one canvas: the options in plain words, your answers as a matrix that shows what would flip the pick, the risks, the agent's own lean, and a critic.
3. You pick and commit. Hoist writes one [MADR](https://adr.github.io/madr/) record per decision to `docs/decisions/`.
4. The agent, waiting on `hoist wait`, gets your decisions and carries on. The page tells you it's okay to go back to the terminal.

**When the agent is about to add a database package** (for example `npm install mongoose`), the hook pauses it before the install runs and opens a single decision page for that choice.

Records bind afterwards: if the agent later tries something that conflicts with a recorded decision, Hoist blocks it and cites the record.

## Install

Requires macOS or Linux, Python 3.9+ (no packages), and [Muse Code](https://dev.meta.ai/resources/blog/build-with-muse-code). No API key needed.

In your project folder:

```bash
git clone https://github.com/leadui/hoist-decisions.git ~/hoist-decisions && python3 ~/hoist-decisions/hoist.py install .
```

Update later with `git -C ~/hoist-decisions pull`.

This adds to your project:

- `.muse/hooks.json`: the hook that pauses Muse Code at lasting decisions
- `.agents/skills/hoist/SKILL.md`: tells the agent how to work with Hoist
- `docs/decisions/`: where the records go
- `.hoist/` in `.gitignore`: local working state

Restart Muse Code in the project and trust the folder so the hook loads.

**Try it:** ask Muse Code for something with real choices in it, such as *"let customers pre-order cakes online for pickup"*, and pick **Decide with Hoist instead** when it asks how you want to decide.

### Optional: Muse Spark

A key from [dev.meta.ai](https://dev.meta.ai) adds what an agent drafting for itself can't give you:

- **An independent drafter.** Muse Spark plans and drafts the decisions instead of the agent, a second opinion that doesn't grade the agent's own homework.
- **The live critic.** Ask a skeptic, a CFO, an on-call engineer and other personas to argue against your pick.
- **Starting a session from the page** instead of from the agent, and `hoist_audit.py`, which lists the decisions a repo has already made.

```bash
export MODEL_API_KEY=...                                         # in the shell you start Muse Code from
security add-generic-password -a "$USER" -s hoist-meta-api -w    # or, on macOS, once in the Keychain
python3 ~/hoist-decisions/hoist.py drafter muse .
```

`drafter agent` switches back. Without a key Hoist always falls back to the agent.

## Ask or autopilot

```bash
python3 hoist.py mode autopilot /path/to/your/project   # the agent decides; Hoist records each call
python3 hoist.py mode ask /path/to/your/project         # back to pausing (the default)
```

On autopilot the hook doesn't pause. When the agent adds a database package, Hoist writes a record of its pick (decided by the agent, low confidence, revisit before building on it) and lets it continue. For any other hard call, the agent records it itself:

```bash
python3 hoist.py log "Choose sign-in" --chose "Email and password" --because "it works on every device" --options "Email and password|Magic link|Google sign-in"
```

Recorded decisions bind in both modes. Any agent that can run a shell command can use `hoist log`, not only Muse Code.

## Commands

```bash
python3 hoist.py install [project]               # add Hoist to a project
python3 hoist.py serve [project]                 # the decision page and records at http://127.0.0.1:7317
python3 hoist.py wait [ID] [project]             # wait for the open decision, then print what was chosen
python3 hoist.py mode [ask|autopilot] [project]  # show or set the mode
python3 hoist.py log TITLE --chose X --because Y [--options "A|B"] [--project DIR]
python3 hoist.py drafter [agent|muse] [project]  # who drafts: the agent (default) or Muse Spark (needs a key)
python3 hoist.py brief [project]                 # for the agent: what to draft next
python3 hoist.py submit plan FILE | submit draft ID FILE   # for the agent: hand in the plan or one draft
python3 hoist_audit.py <path-or-url>             # Muse Spark: list the decisions a repo has already made (needs: pip install openai)
```

The hook (`hoist.py gate`) and the page server start on their own; you rarely need `serve` or `wait` by hand.

## Privacy and cost

- The decision page and its server listen on 127.0.0.1 only.
- By default nothing leaves your machine beyond what your agent already reads and sends: the agent drafts, Hoist checks locally.
- With `drafter muse`, sessions and the critic send Muse Spark the task, the titles of existing decision records, the folder layout, and an excerpt of the project's manifest, config and schema files (for example `package.json`, Dockerfiles, CI workflows, Prisma or SQL schemas, READMEs, `.env.example`), about 9,000 characters in all. Never `.env` and never application source files. The full list is `EVIDENCE` in `hoist_audit.py`.
- Every Muse Spark call (only with a key) is logged to `~/.hoist/spend.json` with its cost, and calls are refused once the ledger reaches $25. Delete or edit the ledger to reset it.
- The hosted demo uses recorded sample data and makes no API calls. Its three ideas are real Muse Spark sessions, recorded through Hoist's own pipeline and checked by its rules.

## Configuration

| Variable | Default | What it does |
|---|---|---|
| `MODEL_API_KEY` | — | Optional Muse Spark key (or the Keychain entry `hoist-meta-api` on macOS) |
| `HOIST_DRAFTER` | `agent` | Overrides the project's drafter: `agent` or `muse` |
| `HOIST_MODE` | `ask` | Overrides the project's mode: `ask` or `autopilot` |
| `HOIST_PORT` | `7317` | Port for the local decision page |
| `HOIST_MODEL` | `muse-spark-1.1` | Muse Spark model |
| `HOIST_MAX_ASK` | `3` | Most decisions Hoist asks you per task; the rest use safe defaults and are recorded |

## Troubleshooting

- **The agent never pauses.** Restart Muse Code in the project and trust the folder; hooks load at start.
- **The page waits on "your agent is writing this moment".** The agent drafts through `hoist brief` and `hoist submit`; if it stopped, ask it to run `hoist brief` and carry on.
- **You set `drafter muse` but the agent still drafts.** Hoist didn't find a key: export `MODEL_API_KEY` in the shell you start Muse Code from (or add the Keychain entry), then restart Muse Code.
- **The page doesn't open.** Run `python3 hoist.py serve /path/to/project` and open http://127.0.0.1:7317. Hoist serves one project at a time on that port: when you work in another project, its page takes the port over by itself (the other project's session stays on disk). If a program that isn't Hoist holds the port, set `HOIST_PORT`.
- **Start over.** Delete the project's `.hoist/` folder. Records in `docs/decisions/` are yours to keep or remove.

## Repository

- `hoist.py`: the hook, the local server, sessions, records, and the CLI (standard library only)
- `hoist_audit.py`: Muse Spark client, spend ledger, and the repo audit
- `skill/SKILL.md`: the agent skill that `install` copies into projects
- `catalog.json`: the decision kinds the hook guards today (database)
- `site/`: the decision page (`index.html`), the landing page, and the sample data; deployed to GitHub Pages
- `site/vendor/bento-madr/`: a pinned copy of Bento MADR; update with `scripts/update-bento.sh <tag>`, don't edit it. Hoist's own compartments live in `site/hoist-bento.js`
- `docs/decisions/`: Hoist's own decision records
- `test/`: standard-library tests; run each with `python3 test/test_<name>.py`

## Status

Built during the hackathon (Oct 26 to Nov 4, 2026) with Muse Code. Shipped: the live session flow (drafted by your agent, or by Muse Spark with a key), Bento MADR canvases with a critic and kind-shaped layouts, MADR records that block conflicting changes, autopilot, the sample-data demo, and the landing page.

## License

MIT
