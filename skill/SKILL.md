---
name: hoist
description: Use before choosing anything in this project that is hard to undo (database, hosting, sign-in provider, language or framework, data format), whenever a step is blocked by a message that starts with "Hoist:", and whenever .hoist/decisions has an open decision. Hoist explains the options to the user, records the decision in docs/decisions, and tells you what was chosen so you can carry on.
---

# Hoist

This project records its lasting decisions in `docs/decisions/`, one MADR file each. Hoist asks the user on a local page and tells you the result.

## When a decision is waiting

If a step is blocked with a message starting "Hoist: paused", or `.hoist/decisions/` has a decision with `"status": "open"`:

1. Tell the user in one line: "Hoist needs your decision: <title>. Decide at <url>."
2. Run the wait command from the message, or `python3 <path to hoist.py> wait` (it finds the open decision). Let it run until it finishes. If it is moved to the background, keep checking its output; do not end your turn while it is still waiting.
3. When it finishes, it prints what the user chose. Follow that exactly and continue the original task without asking the user to say "continue".

## Other rules

- Before choosing a database, hosting, sign-in provider, framework, or data format, read `docs/decisions/`. If a decision exists, follow it.
- If a step is blocked with a message that starts with "Hoist:" and names a choice, do exactly what it says, then continue the original task.
- Do not pick another option yourself while a decision is waiting.
- Do not work around Hoist: do not edit `.muse/hooks.json`, `.hoist/`, or files in `docs/decisions/`, and do not inspect the hook to find a way past it.
- Choices that are easy to undo (a helper library, a test tool) are yours to make. Mention them in your final message.
