---
name: hoist
description: Use before asking the user about, or choosing, anything in this project that is hard to undo (database, hosting, sign-in method, language or framework, data format, design tokens), whenever a step is blocked by a message that starts with "Hoist:", and whenever .hoist/decisions has an open decision. Hoist explains the options to the user in plain words, records the decision in docs/decisions, and tells you what was chosen so you can carry on.
---

# Hoist

This project records its lasting decisions in `docs/decisions/`, one MADR file each. Hoist asks the user on a local page and tells you the result.

## Before you ask the user about lasting choices

When you are about to ask the user to choose something hard to undo, first ask one question on its own, in its own questionnaire call, with nothing else in it:

- question: "<the choices, in plain words> are hard to change later. How do you want to decide?"
  (name the actual choices, for example "The database and the sign-in method are hard to change later. How do you want to decide?")
- options, in this order:
  1. label `Answer here`, description `Quick: I'll ask you the questions now.`
  2. label `Decide with Hoist instead`, description `Opens a page that explains each option in plain words and records your choice.`

Then:

- If the user picks `Answer here`, ask your real questions as usual.
- If the user picks `Decide with Hoist instead`, do not ask anything else. Hoist opens the page and prepares the decisions. Say in one line: "Hoist will walk you through these. Decide at http://127.0.0.1:7317/#/session." Then run `python3 <path to hoist.py> wait` (the path is in .muse/hooks.json) and let it finish. Do not end your turn while it waits; if it moves to the background, keep checking its output.
- When it finishes it prints the user's decisions. Follow them exactly and continue the original task without asking the user to say "continue".

If the user picks `Decide with Hoist instead` on any question in any form, treat the whole form as abandoned and do the same.

## When a decision is waiting

If a step is blocked with a message starting "Hoist: paused", or `.hoist/decisions/` has a decision with `"status": "open"`, or `.hoist/session.json` is still being prepared or decided:

1. Tell the user in one line where to decide.
2. Run the wait command from the message, or `python3 <path to hoist.py> wait` (it finds what is open). Let it finish; do not end your turn while it waits.
3. Follow what it prints and continue the original task.

If `hoist wait` says no decision is waiting right after the user picked Hoist, wait a few seconds and run it once more before falling back to asking in chat.

## Other rules

- Before choosing a database, hosting, sign-in method, framework, or data format, read `docs/decisions/`. If a decision exists, follow it.
- If a step is blocked with a message that starts with "Hoist:" and names a choice, do exactly what it says, then continue the original task.
- Do not pick another option yourself while a decision is waiting.
- Do not work around Hoist: do not edit `.muse/hooks.json`, `.hoist/`, or files in `docs/decisions/`, and do not inspect the hook to find a way past it.
- Choices that are easy to undo (a helper library, a test tool) are yours to make. Mention them in your final message.
