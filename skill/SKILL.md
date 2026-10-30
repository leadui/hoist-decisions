---
name: hoist
description: Use before asking the user about, or choosing, anything in this project that is hard to undo (database, hosting, sign-in method, language or framework, data format, design tokens), whenever a step is blocked by a message that starts with "Hoist:", and whenever .hoist/decisions has an open decision. Hoist explains the options to the user in plain words, records the decision in docs/decisions, and tells you what was chosen so you can carry on.
---

# Hoist

This project records its lasting decisions in `docs/decisions/`, one MADR file each, drawn as Bento MADR canvases. Hoist asks the user on a local page and tells you the result.

It is fine to stop and ask. A hard-to-undo choice made quickly and silently costs the user far more than a pause. Do not guess on their behalf, and do not treat silence as a yes.

## Two modes

- **Ask** (the default): follow the sections below. Hoist pauses you at hard-to-undo choices and the user decides.
- **Autopilot**: the user has chosen speed. If a message says "Hoist is on autopilot", make hard-to-undo calls yourself, do not ask the routing question, and record every one of them right after you make it:

  `python3 <path to hoist.py> log "<the decision, as a short title>" --chose "<what you picked>" --because "<one plain sentence>" --options "<A|B|C>"`

  Recorded decisions still bind you on autopilot. `python3 <path to hoist.py> mode` shows the current mode.

## Before you ask the user about lasting choices

When you are about to ask the user to choose something hard to undo, first ask one question on its own, in its own questionnaire call, with nothing else in it:

- question: "<the choices, in plain words> are hard to change later. How do you want to decide?"
  (name the actual choices, for example "The database and the sign-in method are hard to change later. How do you want to decide?")
- options, in this order:
  1. label `Answer here`, description `Quick: I'll ask you the questions now.`
  2. label `Decide with Hoist instead`, description `Opens a page that explains each option in plain words and records your choice.`

Then:

- If the user picks `Answer here`, ask your real questions as usual.
- If the user picks `Decide with Hoist instead`, do not ask anything else. Hoist opens the page and tells you what to do next (the path to hoist.py is in .muse/hooks.json):
  - usually you draft the decisions for the page yourself: see **Drafting for Hoist** below, then run `python3 <path to hoist.py> wait`;
  - if Hoist says Muse Spark is preparing them, just run `python3 <path to hoist.py> wait`.
  Say in one line: "Hoist will walk you through these. Decide at http://127.0.0.1:7317/#/session." Do not end your turn while it waits; if it moves to the background, keep checking its output.
- When `wait` finishes it prints the user's decisions. Follow them exactly and continue the original task without asking the user to say "continue".

If the user picks `Decide with Hoist instead` on any question in any form, treat the whole form as abandoned and do the same.

## Drafting for Hoist

By default you write the decisions the user sees; Hoist checks them and shows them on the page.

1. Run `python3 <path to hoist.py> brief`. It prints exactly what to write next (first the plan, then one decision at a time), the rules, the project input, and the file to write.
2. Write the file yourself, right away and in one go. Do not start a subagent: it is several times slower, and the person is waiting.
3. Write only the JSON object to the file it names, then run the `submit` command it prints.
4. If `submit` lists problems, fix exactly those in the same file and submit again.
5. Repeat `brief` → write → `submit` until it says every decision is on the page. Then run `wait`.

Write for a smart newcomer and keep every option fair. Your own preference goes only in `agent_pick` and `lean`; never decide for the user.

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
