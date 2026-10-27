---
status: accepted
date: 2026-10-27
door: heavy
proposed-by: Claude Code, after live tests in Muse Code 1.4.13
consulted: Muse Code (built a first handoff prototype), Muse Code session logs
deciders: project owner
confidence: medium
---
# Interrupt Muse Code with a routing question, caught in PostToolBatch

> **Decision:** When the agent is about to ask about lasting choices, it first asks one question on its own ("Answer here" or "Decide with Hoist instead"); a Hoist pick is caught by a `PostToolBatch` hook, which starts a Hoist session and opens the page, and the agent waits with `hoist wait`. **Because** it is the only path that worked live: hooks can't see or change Muse Code's questionnaire before it is shown, but `PostToolBatch` receives its answers. **Accepted cost:** one extra question for people who answer in the terminal, and the option depends on the agent following the skill. **Revisit if** Muse Code lets hooks rewrite or replace the questionnaire, or adds a way to end a form early.

## Context and Problem Statement
Muse Code asks lasting questions in its own questionnaire (`request_user_input`), with short labels written for experts (for example "Postgres (Recommended) / SQLite / None of the above"). Hoist exists to replace that moment with a decision the person understands. How does Hoist take over that moment, and bring the decision back into the coding flow?

## Decision Drivers
- The interrupt should happen at the moment the agent asks, not only when it installs a package (owner's goal)
- What the person picks must reach the agent without them typing "continue" (live run, 2026-10-27)
- Picking Hoist should end the form at once (owner, after a live run where the form kept going)
- Only behavior proven in live runs counts; Muse Code's hook docs don't describe payloads or blocking

## Considered Options
1. Routing question first, caught in `PostToolBatch`
2. Hook adds "Decide with Hoist instead" to every question (`PreToolUse`), caught after the form (`PostToolUse`): Muse Code's own handoff prototype
3. Replace the questionnaire before it appears (`PostLLMCall`)
4. Start a Hoist session from every task prompt (`UserPromptSubmit`), with no questionnaire at all

## Decision Outcome
Chosen: option 1, because it is the only one shown to work end to end. In the live run on 2026-10-27 (task "lets review my options for the design system") the agent asked the routing question alone, the person picked Hoist, the page opened with Muse Spark's drafts, `hoist wait` printed the decisions when the person finished, and the agent read the records and carried on without being prompted.

### Consequences
- Good, because the pick is caught deterministically from the answers in `PostToolBatch`, which arrive as a JSON string in `tool_calls[].tool_response`.
- Good, because a Hoist pick opens a full session (profile questions once, Muse Spark drafts, "Learn more"), not the agent's bare options.
- Good, because "Answer here" keeps the terminal path for people who don't want a browser.
- Bad, because the routing question only appears if the agent follows the skill; it did in every run so far, but a hook can't enforce it.
- Bad, because `hoist wait` runs inside Muse Code's 5-minute command window; slower decisions rely on the agent checking the backgrounded command.

### Confirmation
- `PostToolBatch` with a Hoist pick starts a session and prints the wait instruction; "Answer here" is silent (replayed from the logged payload shape).
- `hoist wait` with no ID waits for the whole session and prints every choice with its record.
- [ ] Re-run the live test after each Muse Code upgrade.

## Pros and Cons of the Options
### Hook adds the option to every question
- Good, because it would work even when the agent ignores the skill.
- Bad, because `PreToolUse` never fires for `request_user_input`: checked in three separate runs, and an all-events log confirmed it. The option the person saw in the test came from the agent, not the hook.
- Bad, because `PostToolUse` doesn't fire for it either, so the pick was never caught and `hoist wait` found nothing.
- Bad, because a multi-question form can't be ended partway; the person had to step through the remaining questions.

### Replace the questionnaire before it appears
- Good, because the person would never see the bare form.
- Bad, because whether `PostLLMCall` can stop a turn is undocumented and untested.

### Start a session from every task prompt
- Good, because it covers every lasting decision in the task, including ones the agent wouldn't ask about.
- Bad, because it adds a planning step to every prompt, including small ones, and the owner preferred the interrupt, which already worked.

## More Information
- Evidence: the all-events hook log and the Muse Code session exports from 2026-10-27 (kept in the test project's `.hoist-test-backup/`).
- The package and file checks (`PreToolUse` on `bash`, `write_file`, `edit_file`) stay as a backstop for decisions the agent makes without asking.
- Option 3 is worth a probe after the demo is recorded.
