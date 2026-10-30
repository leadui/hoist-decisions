# Hoist

Coding agents make choices that take weeks to undo, often in a single line of a diff. Hoist stops the agent at those one-way doors, explains the options in plain language, lets you decide, and writes the decision down so any person or agent can see why later.

- **Try the demo** (sample data, runs in the browser): https://leadui.github.io/hoist-decisions/
- **Read the pitch:** https://leadui.github.io/hoist-decisions/landing.html
- **Built on [Bento MADR](https://github.com/leadui/bento-madr)**, the decision-canvas library that started here.

Built for the Meta Global AI Developer Hackathon with **Muse Code** (the agent Hoist guards) and **Muse Spark** (which drafts every decision you see).

What Hoist stands for:

- **It's okay to interrupt.** A pause costs a minute; a wrong database costs weeks.
- **It's okay to ask dumb questions.** Every option comes with an everyday analogy, what living with it is like, and the terms explained.
- **It's okay to take your time.** Decide later, send it back to chat, or pick for now. The record says why, so changing it later is a plan, not a regret.
- **It's not okay to say yes to everything.** When speed matters, autopilot lets the agent decide, and Hoist writes every call down for you to review.

## How it works

Hoist steps in at two moments.

**When the agent is about to ask you something hard to undo**, Hoist's skill has it ask one question first: *"These are hard to change later. How do you want to decide?"* with **Answer here** or **Decide with Hoist instead**. If you pick Hoist:

1. Hoist reads the task and the project, and Muse Spark plans which decisions really need you.
2. Your browser opens the decision page. Each decision is one canvas: the options in plain words, your answers as a matrix that shows what would flip the pick, the risks, the agent's own lean, and a critic you can call in.
3. You pick and commit. Hoist writes one [MADR](https://adr.github.io/madr/) record per decision to `docs/decisions/`.
4. The agent, waiting on `hoist wait`, gets your decisions and carries on. The page tells you it's okay to go back to the terminal.

**When the agent is about to add a database package** (for example `npm install mongoose`), the hook pauses it before the install runs and opens a single decision page for that choice.

Records bind afterwards: if the agent later tries something that conflicts with a recorded decision, Hoist blocks it and cites the record.

## Install

Requires macOS or Linux, Python 3.9+ (no packages), and [Muse Code](https://dev.meta.ai/resources/blog/build-with-muse-code). Live decisions also need a Muse Spark API key from [dev.meta.ai](https://dev.meta.ai).

```bash
git clone https://github.com/leadui/hoist-decisions.git
python3 hoist-decisions/hoist.py install /path/to/your/project
```

This adds to your project:

- `.muse/hooks.json`: the hook that pauses Muse Code at lasting decisions
- `.agents/skills/hoist/SKILL.md`: tells the agent how to work with Hoist
- `docs/decisions/`: where the records go
- `.hoist/` in `.gitignore`: local working state

Give Hoist your Muse Spark key, either way works:

```bash
export MODEL_API_KEY=...   # in the shell you start Muse Code from
security add-generic-password -a "$USER" -s hoist-meta-api -w   # or, on macOS, once in the Keychain
```

Then restart Muse Code in the project and trust the folder so the hook loads. Without a key the hook still pauses the agent, but the page can't draft the decisions.

**Try it:** ask Muse Code to *"add user accounts with saved projects"* and pick **Decide with Hoist instead** when it asks how you want to decide.

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
python3 hoist_audit.py <path-or-url>             # Muse Spark: list the decisions a repo has already made (needs: pip install openai)
```

The hook (`hoist.py gate`) and the page server start on their own; you rarely need `serve` or `wait` by hand.

## Privacy and cost

- The decision page and its server listen on 127.0.0.1 only.
- Live sessions send Muse Spark the task, the titles of existing decision records, the folder layout, and an excerpt of the project's manifest, config and schema files (for example `package.json`, Dockerfiles, CI workflows, Prisma or SQL schemas, READMEs, `.env.example`), about 9,000 characters in all. Never `.env` and never application source files. The full list is `EVIDENCE` in `hoist_audit.py`.
- Every Muse Spark call is logged to `~/.hoist/spend.json` with its cost, and calls are refused once the ledger reaches $25. Delete or edit the ledger to reset it.
- The hosted demo uses recorded sample data and makes no API calls.

## Configuration

| Variable | Default | What it does |
|---|---|---|
| `MODEL_API_KEY` | — | Muse Spark key (or the Keychain entry `hoist-meta-api` on macOS) |
| `HOIST_MODE` | `ask` | Overrides the project's mode: `ask` or `autopilot` |
| `HOIST_PORT` | `7317` | Port for the local decision page |
| `HOIST_MODEL` | `muse-spark-1.1` | Muse Spark model |
| `HOIST_MAX_ASK` | `3` | Most decisions Hoist asks you per task; the rest use safe defaults and are recorded |

## Troubleshooting

- **The agent never pauses.** Restart Muse Code in the project and trust the folder; hooks load at start.
- **The page says there's no Muse Spark key.** Export `MODEL_API_KEY` in the shell you start Muse Code from, or add the Keychain entry above, then restart Muse Code.
- **The page doesn't open.** Run `python3 hoist.py serve /path/to/project` and open http://127.0.0.1:7317. If the port is taken, set `HOIST_PORT`.
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

Built during the hackathon (Oct 26 to Nov 4, 2026) with Muse Code. Shipped: the live session flow with Muse Spark drafting, Bento MADR canvases with a critic and kind-shaped layouts, MADR records that block conflicting changes, autopilot, the sample-data demo, and the landing page.

## License

MIT
