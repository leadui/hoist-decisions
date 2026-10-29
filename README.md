# Hoist

Coding agents make choices that take weeks to undo, often in a single line of a diff. Hoist stops the agent at those one-way doors, explains the options in plain language, lets you decide, and records the decision so any person or agent can see why later.

What Hoist stands for:

- **It's okay to interrupt.** A pause costs a minute; a wrong database costs weeks.
- **It's okay to ask dumb questions.** Every option comes with an everyday analogy, what living with it is like, and the terms explained.
- **It's okay to take your time.** Decide later, send it back to chat, or pick for now. The record says why, so changing it later is a plan, not a regret.
- **It's not okay to say yes to everything.** When speed matters, autopilot lets the agent decide, and Hoist writes every call down for you to review.

Built for the Meta Global AI Developer Hackathon with **Muse Code** (the agent Hoist guards) and **Muse Spark** (reads repos to find the decisions already made).

Try the decision page with sample data: https://leadui.github.io/hoist-decisions/

Read the pitch: https://leadui.github.io/hoist-decisions/landing.html

## How it works

1. You give Muse Code a task, for example "add user accounts with saved projects".
2. Muse Code is about to add a database package (say `mongoose`). Hoist's hook notices what changed, not what was typed, and pauses the agent.
3. Your browser opens a short decision page: a few questions about your project, one recommendation with its trade-off, the other options, and the evidence behind it.
4. You decide. Hoist writes a decision record to `docs/decisions/` and tells Muse Code what you chose. The agent continues with your choice.
5. If the agent later tries something that conflicts with a recorded decision, Hoist blocks it and cites the record.

Decision records use the [MADR](https://adr.github.io/madr/) format, with a one-line summary at the top so they read well on GitHub too. Every moment and record is drawn with [Bento MADR](https://github.com/leadui/bento-madr) (see below).

## Ask or autopilot

```bash
python3 hoist.py mode autopilot /path/to/your/project   # the agent decides; Hoist records each call
python3 hoist.py mode ask /path/to/your/project         # back to pausing (the default)
```

On autopilot the hook doesn't pause. When the agent adds a database package, Hoist writes a record of its pick (decided by the agent, low confidence, revisit before building on it) and lets it continue. For any other hard call, the agent records it itself:

```bash
python3 hoist.py log "Choose sign-in" --chose "Email and password" --because "it works on every device" --options "Email and password|Magic link|Google sign-in"
```

Recorded decisions bind in both modes: a later install that conflicts with a record is blocked and the record is cited. Any agent that can run a shell command can use `hoist log`, not only Muse Code.

## Install

Requires Python 3.9+ and [Muse Code](https://dev.meta.ai/resources/blog/build-with-muse-code). No other dependencies.

```bash
git clone https://github.com/leadui/hoist-decisions.git
# SSH works too: git@github.com:leadui/hoist-decisions.git
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
python3 hoist.py wait [ID] [project]  # wait for a decision, then print the outcome
python3 hoist.py mode [ask|autopilot] [project]
python3 hoist.py log TITLE --chose X --because Y [--options "A|B"] [--project DIR]
python3 hoist_audit.py <path-or-url>  # Muse Spark: find the decisions a repo has already made
```

`hoist_audit.py` needs `pip install openai` and a Muse Spark key in `MODEL_API_KEY`. Everything else runs on the standard library. The decision page serves from 127.0.0.1 while Muse drafts each moment over the API.

## Built on Bento MADR

[Bento MADR](https://github.com/leadui/bento-madr) draws decision records as bento canvases: swappable compartments for the problem, the evidence, the verdict and what follows, with gaps left visibly empty. It started inside Hoist and now lives in its own repository ([catalog](https://leadui.github.io/bento-madr/)).

- Hoist uses a pinned copy in `site/vendor/bento-madr/`. Update it with `scripts/update-bento.sh v0.2.0` (any release tag); don't edit the copy.
- Hoist's own compartments, such as the agent's lean, live in `site/hoist-bento.js` and are added with the kit's `BentoKit.define()`.

## Status

Built during the hackathon (Oct 26 to Nov 4, 2026) with Muse Code. Shipped: the
decision-moments session engine (interruption → expanding options → hyper-dive →
commit & send back to chat, MADR records), the sample-data demo and the landing
page above. Next: demo script + recorded run (Nov 2–3).
