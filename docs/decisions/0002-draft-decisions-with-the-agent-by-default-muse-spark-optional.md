---
status: accepted
date: 2026-10-29
door: heavy
proposed-by: project owner, after the release review
consulted: Claude Code (built and tested the agent drafting loop)
deciders: project owner
confidence: medium
---
# Draft decisions with the agent by default; Muse Spark is an optional, independent drafter

> **Decision:** When the person picks "Decide with Hoist instead", the agent (or a fresh subagent it starts) drafts the plan and each decision through `hoist brief` and `hoist submit`, held to the same contracts and quality checks as Muse Spark; a Muse Spark key plus `hoist drafter muse` makes Muse Spark the drafter and turns on the live critic. **Because** people hesitate to hand an API key to a tool they just met, so Hoist has to work out of the box, while a second, independent model is still worth having one command away. **Accepted cost:** by default the options are drafted by the same model that already has a favourite, and the agent has a few more steps to follow. **Revisit if** most installs add a key anyway, or agent-drafted decisions turn out clearly weaker than Muse Spark's in live runs.

## Context and Problem Statement
Until now every decision session called Muse Spark to plan the task and draft the decisions, so Hoist needed an API key before it could do its main job. Asking for a key up front is a real barrier for a new tool, but taking Muse Spark out entirely would leave Hoist as little more than a skill. Who should draft the decisions the person sees?

## Decision Drivers
- Hoist should work right after install, with no key and nothing sent anywhere new (owner, release review)
- The person should still get a fair, plain-language comparison, not the agent's favourite with extras (Hoist's purpose)
- Muse Spark should stay valuable, and visible in the hackathon demo (Meta Global AI Developer Hackathon)
- The page, the records and the contracts must not fork into two versions

## Considered Options
1. The agent drafts by default; Muse Spark is optional (`hoist drafter muse`)
2. Muse Spark always drafts, so a key is required (how it worked until 2026-10-29)
3. The agent always drafts; no Muse Spark

## Decision Outcome
Chosen: option 1, because it removes the key barrier without dropping the independent second opinion. Both drafters get the same input (`plan_input`, `lean_input`), the same contracts (`PLAN_SYSTEM`, `LEAN_SYSTEM`) and the same `check_draft` rules with one repair round, so the page and the records don't care who drafted. Each decision on the page says who drafted it.

### Consequences
- Good, because Hoist works with no key, and by default nothing leaves the machine beyond what the agent already reads and sends.
- Good, because the brief tells the agent to hand the drafting to a subagent when it can: a fresh context drafts without the agent's own preferences.
- Good, because a key now buys clear extras: Muse Spark as the drafter, the live critic personas, starting a session from the page, and the repo audit.
- Bad, because a default draft comes from the model that already has a view on the answer; the rules (fair options, an honest downside for each) and the subagent advice reduce the bias but don't remove it.
- Bad, because the agent must follow a `brief` → `submit` → `wait` loop; like the routing question in 0001, the skill asks for it but a hook can't enforce it. `hoist wait` refuses to block while drafts are missing, so a skipped step fails loudly instead of hanging.

### Confirmation
- `test/test_agent_draft.py` runs the whole loop: the hook starts an agent session, `brief` serves the contracts, bad files and unknown ids are refused, problems come back as a fix list, the page state reaches ready, and the server refuses page-started sessions and the live critic without a key.
- An end-to-end run with the real CLI on 2026-10-29: the page showed "Your agent is writing this moment" and filled in live as each draft was submitted.
- [ ] Run a live Muse Code session with the default drafter before the demo is recorded.

## Pros and Cons of the Options
### Muse Spark always drafts
- Good, because an independent model drafts every decision, so the agent never shapes the options.
- Bad, because nothing works until the person creates and hands over an API key.

### The agent always drafts
- Good, because it is the simplest setup and needs no key at all.
- Bad, because it gives up the independent second opinion and the live critic, which are the clearest reasons to add Muse Spark.

## More Information
- How to switch: `python3 hoist.py drafter muse /path/to/project` (needs a key; without one Hoist falls back to the agent). The README's "Optional: Muse Spark" section lists what the key adds.
- Builds on [0001](0001-interrupt-muse-code-with-a-routing-question-and-posttoolbatch.md): the routing question still starts the session; only who drafts it changed.
