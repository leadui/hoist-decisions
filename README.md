# Hoist

Coding agents make choices that take weeks to undo, often in a single line of a diff. Hoist stops the agent at those one-way doors, explains the options in plain language, lets you decide, and records the decision so any person or agent can see why later.

Built for the Meta Global AI Developer Hackathon with **Muse Code** (the agent Hoist guards) and **Muse Spark** (reads repos to find the decisions already made).

Try the decision page with sample data: https://leadui.github.io/hoist-decisions/

Read the pitch: https://leadui.github.io/hoist-decisions/landing.html

## How it works

1. You give Muse Code a task, for example "add user accounts with saved projects".
2. Muse Code is about to add a database package (say `mongoose`). Hoist's hook notices what changed, not what was typed, and pauses the agent.
3. Your browser opens a short decision page: a few questions about your project, one recommendation with its trade-off, the other options, and the evidence behind it.
4. You decide. Hoist writes a decision record to `docs/decisions/` and tells Muse Code what you chose. The agent continues with your choice.
5. If the agent later tries something that conflicts with a recorded decision, Hoist blocks it and cites the record.

Decision records use the [MADR](https://adr.github.io/madr/) format, with a one-line summary at the top so they read well on GitHub too.

## Install

Requires Python 3.9+ and [Muse Code](https://dev.meta.ai/resources/blog/build-with-muse-code). No other dependencies.

```bash
git clone git@github.com:leadui/hoist-decisions.git
python3 hoist-decisions/hoist.py install /path/to/your/project
```

This adds:

- `.muse/hooks.json`: the hook that pauses Muse Code at lasting decisions
- `.agents/skills/hoist/SKILL.md`: tells the agent how to work with Hoist
- `docs/decisions/`: where the records go
- `.hoist/` in `.gitignore`: local working state

Restart Muse Code in the project and trust the folder so the hook loads.

## Commands

```bash
python3 hoist.py serve [project]      # browse decisions at http://127.0.0.1:7317
python3 hoist.py wait ID [project]    # wait for a decision, then print the outcome
python3 hoist_audit.py <path-or-url>  # Muse Spark: find the decisions a repo has already made
```

`hoist_audit.py` needs `pip install openai` and a Muse Spark key in `MODEL_API_KEY`. Everything else runs on the standard library, on your machine. The decision page listens only on 127.0.0.1 and makes no API calls.

## Status

Built during the hackathon (Oct 26 to Nov 4, 2026) with Muse Code. Shipped: the
decision-moments session engine (interruption → expanding options → hyper-dive →
commit & send back to chat, MADR records), the sample-data demo and the landing
page above. Next: demo script + recorded run (Nov 2–3).
