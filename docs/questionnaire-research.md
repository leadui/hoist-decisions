# Agentic questionnaires: how they work, and how Hoist applies them

Goal: improve human–AI collaboration so humans make **educated decisions** instead of
rolling a die on proposed options — from system design down to everyday questions.

Researched 2026-10-28 by a 4-agent crew (Muse mechanics, cross-agent comparison,
decision science, synthesis). Evidence-first: every claim below traces to repo code,
official docs, or cited research. Open questions are listed at the end, not buried.

## 1. The generic model: 7 stages, every agent

Every coding agent studied (Muse `request_user_input`, Claude `AskUserQuestion`,
Codex `request_user_input`, Gemini `ask_user`; Cursor is the exception) implements
the same seven stages. Agents differ only in schema details and hook visibility.

| Stage | What happens | Key variance |
|---|---|---|
| Trigger | Agent hits uncertainty it cannot resolve: ambiguous requirements, a costly fork, a missing preference | Hoist makes it explicit via skill ("ask a routing question first"), not model discretion |
| Construct | Agent builds a structured question payload | Portable shape: `questions[{header, question, options[{label, description}]}]`; caps cluster at 2–4 options |
| Present | Client renders the form (modal, chat card, headless surface) | Forms generally cannot be aborted mid-way, so routing must be a solo question |
| Choose | User picks labels (and optionally free text) | Recommended options surfaced explicitly (Muse `' (Recommended)'` suffix; Codex wants recommended first) |
| Validate/normalize | Labels normalized back to stable ids | Muse returns `selected_label`/`selected_labels` variants; Claude/Gemini preserve arrays; Codex guarantees at least an Other |
| Record | Answer written into the transcript as the tool result | Hook visibility differs (see §2) |
| Resume | Agent reads the answer and continues | Portable rule: follow the record exactly, no re-ask |

## 2. Per-agent mechanics

**Muse (inverted).** `request_user_input` never fires `PreToolUse`/`PostToolUse`.
`PostToolBatch` is the only witness, carrying `tool_calls[{tool_name, tool_input,
tool_response}]` with answers as a JSON string. Max 3 options per question; Hoist
injects only into single-select questions with fewer than 3 existing options and
skips multi-select. Resume is `hoist wait`: polls `session.json`, prints each
choice + record + note, agent follows exactly with no "continue" needed.

**Claude Code (easiest port).** `AskUserQuestion` takes 1–4 questions per call with
per-question `multiSelect`. `PreToolUse` fires for the question tool directly and
can answer it programmatically with `allow` + `updatedInput`. `-p` runs use
defer + resume. A skill routing question is optional here since hooks see the tool.

**Codex.** `request_user_input` takes 1–3 questions (`id`, `header` ≤ 12 chars),
2–3 options each, recommended first; non-empty options enforced and the client
auto-adds a free-form Other (`is_other=true`); no multi-select. Hooks live in
`.codex/hooks.json` (`PreToolUse`/`PermissionRequest`/`PostToolUse` + matchers).
Port mirrors the Muse pattern (skill routing + hook matcher); answer-injection
support unconfirmed.

**Gemini CLI.** `ask_user` types each question (`choice`/`text`/`yesno`); choice
needs 2–4 options with choice-only multi-select. `BeforeTool`/`AfterTool` hooks
with regex matchers in `settings.json` allow/deny. Note: `ask_user` is removed in
headless/ACP mode, so non-interactive runs need another path.

**Cursor (hardest).** No structured schema: clarification is conversational and
**non-blocking** — the agent keeps working while waiting. Route via
`.cursor/rules/*.mdc` + `preToolUse`/`postToolUse`/`stop` hooks (deny > ask > allow,
fail-open unless `failClosed`). Non-blocking questions break `hoist wait`
semantics; a stop-hook follow-up loop or polling is needed instead.

Muse-only assumptions to unwind for any port: `PostToolBatch` interception,
`.muse/hooks.json` + exit-2 block + 600 s hold, and wait-holds-turn semantics.

## 3. Educated vs random: what the science says

Questionnaires randomize when they ask preferences over undescribed options. They
educate when they teach the mechanism first, ask about the user, disclose
progressively, and require light engagement before showing the AI's lean.

| Finding | Source | Hoist application |
|---|---|---|
| Explanations alone don't cut AI overreliance; cognitive forcing (own judgment before the AI's) does | Bucinca et al. 2021, arXiv 2102.09692 | Teach in Compare **before** revealing the lean strip |
| Progressive disclosure: few key options first, rest on request; easier to learn, less error-prone | NN/g, Nielsen 2006 | Glance / Compare / Deep dive + hyper dive tiers |
| State the decision, options with benefits + harms from evidence, values clarification, SURE check | Ottawa Framework / IPDAS, decisionaid.ohri.ca | Generic blocks + assumption chips + review gate |
| One question per screen, plain language, branch on relevance | TurboTax interview pattern | Session asks one "about you" thing at a time |
| Wanted explanations are contrastive: "why P rather than Q" | Miller 2017 (via XAI reviews) | "Would flip if" + ghost rejected options + Ruled-out reasons |
| Working memory is hard-limited; one primary decision per screen | Sweller 1988 (via NN/g summaries) | Minimal lean strip, single commit per hyper dive |
| Decision time grows with option count; group and order options | Hick's law | Short option lists, "rejected: N" ghost expanders |
| List options/benefits/risks, star what matters, pick on values | Ottawa Personal Decision Guide | "About you" answers + assumption chips = values clarification |
| Describe the decision, list options, give positive AND negative features | IPDAS qualifying criteria, BMJ 2022 | Every option needs "Bad, because" — already in MADR rules |
| Mechanism beats attribute lists for perceived "educational-ness" | POC lesson 1 | Generic blocks carry mechanism/journey, not just pros/cons |
| Honesty labels raised trust | POC lesson 5 | Evidence tags + illustrative-or-real + path-tied confidence |
| Escape hatches beat charts for trust | POC lesson 6 | Escape row: delegate, skip-to-revisit, abandon |
| Voice must be authored spoken scripts, never page text read aloud | POC lesson 2 | Voice as authored block, replayable in hyper dive |
| Bare multiple-choice got "No preference" from ignorance | Owner finding, 2026-10-26 | Door/undo-cost line per decision |

Anti-overreliance rule: reserve forcing friction (engage before lean) for door-3
one-way decisions; keep reversible choices low-friction.

## 4. Hoist application model

**Trigger.** `UserPromptSubmit` saves the prompt. The skill forces one routing
question alone — Answer here vs Decide with Hoist — because a mid-form Hoist pick
cannot abort the form. On a Hoist pick, the `PostToolBatch` gate matches the label,
builds hints, starts a detached server on 127.0.0.1:7317, posts the session, opens
the page, and prints the wait command.

**Educate.** Generic blocks, tiered depth: idea/mechanism strips, options with
trade-offs (mandatory Bad-because each), evidence links tagged researched-live vs
unverified, authored second-person voice. One "about you" thing at a time.

**Choose.** Lean strip revealed after Compare engagement: authored "leans X — why"
+ "would flip if" + ≤3 Right/Change assumption chips (record-only, no re-ranking).
Door/undo-cost line per decision. Single commit per hyper dive.

**Record.** Commits POST answers/decisions; batch close writes MADRs with path-tied
confidence, Ruled-out reasons, ghost rejected options, and evidence tags — the
record explains both why and why-not.

**Resume / delegate / defer.** `hoist wait` prints choice + record + note; the agent
follows exactly. "Go with lean" delegates; the escape row (delegate, skip-to-revisit,
abandon) plus answered/skipped tabs and the review gate unblock the wait without
forcing a fake preference.

## 5. Build plan

Phased plan P0–P3 (now → Nov 3 recorded demo) with the visual loop and live
progress tracker: [plan.md](plan.md).

## 6. Open questions

Hook/schema: official `request_user_input` JSON schema (inferred from code/logs
only); whether `PostLLMCall` can replace a questionnaire; whether `updatedInput`
rewrite + `PostToolUse` stdout-to-agent works live in Muse; whether Gemini
`BeforeTool` can inject answers or only allow/deny; whether Cursor `preToolUse`
fires for its Ask tool and under what name; whether Codex `PreToolUse` can supply
answers programmatically. UX: primary-text confirmation for Sweller 1988 and Miller
2017; optimal lean-strip reveal timing untested with real users; no data on
pre-generated narration vs Web Speech. Demo scope excludes: multi-agent ports,
multi-select/full-form routing, mid-form abort, slow-decision polling beyond the
5-minute window.

## Sources

Repo: `hoist.py`, `skill/SKILL.md`, `docs/decisions/0001-*`, `taskmanager.md`,
`hoist-handoff/` (in `/Users/oliveway/CODE/hoist-decisions-muse`),
`examples/decision-moment.html`, POC `taskmanager.md` lessons.
Docs: [Claude user-input](https://code.claude.com/docs/en/agent-sdk/user-input),
[Claude hooks](https://code.claude.com/docs/en/hooks),
[Codex request_user_input spec](https://raw.githubusercontent.com/openai/codex/rust-v0.154.0/codex-rs/core/src/tools/handlers/request_user_input_spec.rs),
[Codex hooks](https://learn.chatgpt.com/docs/hooks.md),
[Gemini confirmation types](https://raw.githubusercontent.com/google-gemini/gemini-cli/main/packages/core/src/confirmation-bus/types.ts),
[Gemini ask-user](https://raw.githubusercontent.com/google-gemini/gemini-cli/main/packages/core/src/tools/ask-user.ts),
[Gemini hooks](https://geminicli.com/docs/hooks/reference/),
[Cursor agent](https://cursor.com/docs/agent/overview),
[Cursor hooks](https://cursor.com/docs/hooks),
[Cursor rules](https://cursor.com/docs/rules).
Research: Bucinca et al. 2021 (arXiv 2102.09692), NN/g progressive disclosure
(2006), Ottawa Decision Aids (decisionaid.ohri.ca), IPDAS/BMJ 2022, Miller 2017
via ar5iv 1811.01439, Laws of UX (Hick's law).
