---
name: hoist
description: Use before choosing anything in this project that is hard to undo (database, hosting, sign-in provider, language or framework, data format), and whenever a step is blocked by a message that starts with "Hoist:". Hoist explains the options to the user, records the decision in docs/decisions, and tells you what was chosen.
---

# Hoist

This project records its lasting decisions in `docs/decisions/`, one MADR file each.

- Before choosing a database, hosting, sign-in provider, framework, or data format, read `docs/decisions/`. If a decision exists, follow it.
- If a step is blocked with a message that starts with "Hoist:", do exactly what the message says, then continue the original task. The message tells you what the user chose.
- If the message says a decision is waiting for the user, stop and tell the user to finish it on the Hoist page. Do not pick something else instead.
- Do not work around Hoist: do not edit `.muse/hooks.json`, `.hoist/`, or files in `docs/decisions/`, and do not inspect the hook to find a way past it.
- Choices that are easy to undo (a helper library, a test tool) are yours to make. Mention them in your final message.
