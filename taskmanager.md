# Hoist — taskmanager.md
> Read first. Optimized so a cold agent is productive after one read.
`scope: project`

## Now — where we are (resume here)
- State: `hoist_audit.py` works end to end except the live Muse Spark call, which has not run yet (tested with `--dry-run` and `--from-json test/sample_reply.json`). Validate gate passes. Dry run on excalidraw: 55 files, ~16k input tokens, worst case $0.07. Known gap, left as is by the owner: `firebase-project/firebase.json` is not in `EVIDENCE`.
- 2026-10-26: design settled on **map + decision card + evidence graph**, with **Muse Code** as the agent. Interactive prototype: [Hoist Decision Card](https://claude.ai/artifact/8BNdWnry1pnz3mHF1sWxt1). Demo script updated to match: [Hoist Demo Script](https://claude.ai/artifact/Y845JAaHCn1mVGiS9GTg98).
- Next (go/no-go, due Wed Oct 28):
  1. Real scan of https://github.com/excalidraw/excalidraw, then one of the owner's repos. Judge whether `graph.md` is believable.
  2. Prove a Muse Code `PreToolUse` hook can block a tool call. Its stdin format and how it blocks are not documented on the page we read. If this fails, fall back to Claude Code.
- Schedule: scans + hook test Oct 27–28 · catalog + engine Oct 29 · decision page Oct 30 · skill + hook + Muse Spark questions Oct 31 · pivot Nov 1 · benchmark + README Nov 2 · record Nov 3.
- 2026-10-27: public repo at https://github.com/leadui/hoist-decisions (remote `origin`, SSH, `main` pushed). Commits use Oliveway <lead.with.oleg@gmail.com>. GitHub Pages: `site/index.html` (the decision card prototype, sample data) is published by `.github/workflows/pages.yml` to https://leadui.github.io/hoist-decisions/ once the repo's Settings → Pages → Source is set to "GitHub Actions". Pages is public: no password option on a personal account, and the page makes no API calls, so no key is ever in it. Owner is turning on secret protection and push protection (Settings → Advanced Security).
- Open: the owner hasn't named their own repo for the audit test yet.
- Deadline: submission closes **Wed Nov 4, 8:00 PM Central** (9:00 PM ET). Record the demo by Tue Nov 3.
- Reconcile with git if this disagrees (git wins).

## What Hoist is
Agents ask questions you can't answer. Hoist turns them into decisions you understand.

When a coding agent reaches a choice that is costly to undo (a one-way door), Hoist pauses it and opens a decision card: what's being decided, what it costs to undo, questions about you (not about the tech), each option's gains and costs, what decides it, and what would flip it. Every proposal can be traced back to its evidence. The choice is recorded as an ADR, and the record updates when plans change. Entry for the Meta Global AI Developer Hackathon, Indie developer track (judged on creativity, technical ambition, and whether it works), theme "Build for your world". Meta tools doing real work: Muse Spark (audit, questions, inferred facts, record prose) and Muse Code (the agent Hoist guards).

### What the user sees (three layers)
1. **Glance (5 seconds):** the decision as a question, door badge, best fit and where the agent's own pick ranks (in words, never a score), a confidence badge with its reasons, and who is accountable (Proposed by Muse Code · Analyzed by Muse Spark · Decided by you).
2. **Decide (30 seconds):** "About you" questions; already-known facts (from ADRs); considered options ranked Best fit / Runner-up / Third, each with "Strong on / Weak on" and "Good, because / Bad, because" consequences tagged Now or Later; options that fail a hard limit shown as **Ruled out** with the reason and source; a "Close call" tag when the top two are near; top 3 deciding factors; "Would flip if" with a Try-it what-if; how Hoist keeps the decision true; a live **record preview**; then Select an option and three exits: Record, No preference (best fit recorded as delegated, low confidence, revisit), Ask me later (recorded as proposed with a short-term placeholder).
3. **Trust (on demand):** clicking Evidence on any option (including a ruled-out one) opens a graph, Sources → Facts → What matters → Option. Sources are tagged seen in repo, your answer, agent's task, docs, or inferred by Muse Spark (dashed). Edges are green when they help, red when they hurt, and thicker when they count more. Clicking a node highlights its path and shows the file snippet, answer, or doc link. The raw weights and ratings sit in a collapsed "How Hoist ranked this" section.

Left rail: the decision map (recorded, deciding now, open and blocked), then **Decided by your agent**: two-way doors Muse Code settled on its own, each as a Y-statement with "Looks right" and "Open as a card". The card is where you decide; the rail is context and review.

### Pieces, in build order
1. **Audit** (`hoist_audit.py`, done): Muse Spark reads a repo's manifests, CI and deploy config, infers its lasting decisions, tags each seen / inferred / unknown, and writes `docs/decisions/ADR-NNN-*.md` plus `graph.md` (Mermaid). To do: use catalog ids where a decision matches, and also write `docs/decisions/hoist.json`.
2. **Catalog + engine** (todo, port `model` / `deciding` / `flips` / `buildGraph` from the decision card prototype): `catalog.json` holds ~6 decision kinds (language, database, hosting, CI, auth, where code lives) with options, factor scores, "You get / You give up" text, questions, and doc facts with links. The engine turns answers into weights, ranks the options, picks the top 3 deciding factors, re-scores every alternative answer to find flips, and emits the evidence graph. No LLM in the math. Outside the catalog: ask, record, no ranking.
3. **Decision page** (todo): `hoist ui` serves one local HTML page with Python's `http.server` (no build step), containing the map rail, the decision card, and the evidence sheet. Answers post back to the CLI. A plain-text card in the terminal is the fallback.
4. **Muse Code skill + hook** (todo): the skill goes in `.claude/skills/hoist/SKILL.md`, which Muse Code also scans, so one skill serves both agents. Commands `/hoist-audit`, `/hoist-next`, `/hoist-pivot`. The hook goes in `.muse/hooks.json` on `PreToolUse`: a cheap fixed pre-filter (installs of database or queue drivers, edits to manifests, schema or migrations, Dockerfiles, deploy config) routes only risky actions to the ladder (two-way door → just do it; contradicts an ADR → block and cite it; new one-way door → open the decision card).
5. **Muse Spark in the catch** (todo): rewrites catalog questions in the project's own terms, pre-fills answers it can see in the code, adds inferred facts (shown as inferred in the evidence graph), and writes the ADR prose. Every call goes through the spend guardrails.
6. **Pivot** (todo): a new ADR version links the old one ("Supersedes"), and dependents in `hoist.json` get marked for review. Demo pivot: "client needs data on their own servers" moves hosting to a server they run. Database depends on hosting, so it is flagged, and its best fit flips from Managed Postgres to self-hosted.
7. **Benchmark** (todo): 10 project-setup tasks in Muse Code, with and without Hoist. Count lasting choices made without asking (audit before and after each task, new door ≥2 decisions with no ADR), and count false alarms. Report the real numbers. Muse Code runs on Muse Spark, so dry-run one task first and check the spend.

References: [Hoist Decision Card](https://claude.ai/artifact/8BNdWnry1pnz3mHF1sWxt1) (current design, sample data) · [Hoist Decision Graph](https://claude.ai/artifact/HWDhfxZegz6TSjTpHd2Pyj) (earlier prototype: original engine and pivot flow) · [Hoist Demo Script](https://claude.ai/artifact/Y845JAaHCn1mVGiS9GTg98).

## Onboarding — get productive
- Setup: Python 3.12 venv in `.venv` with `openai` installed (`.venv/bin/python`). The system `python3` is 3.9, which is too old for the house style. `export MODEL_API_KEY=...` (from dev.meta.ai; never commit it, never print it).
- Free check: `.venv/bin/python hoist_audit.py <path-or-git-url> --dry-run` (prints evidence count, token estimate, worst-case cost; saves prompt to `.hoist/last_prompt.txt`)
- Real scan: `.venv/bin/python hoist_audit.py <path-or-git-url>` → local repo writes to `<repo>/docs/decisions/`; URL writes to `./hoist-out/<name>/`
- Re-render without an API call: `.venv/bin/python hoist_audit.py <target> --from-json .hoist/last_response.json`
- Validate gate: `.venv/bin/python -m py_compile hoist_audit.py` and `.venv/bin/python hoist_audit.py https://github.com/excalidraw/excalidraw --from-json test/sample_reply.json --out test/out` must succeed.
- Layout: `hoist_audit.py` (scanner) · `test/sample_reply.json` (hand-written fixture, not a real model reply) · `site/index.html` (decision card prototype for GitHub Pages; edit here, then republish the artifact copy if needed) · `.github/workflows/pages.yml` (Pages deploy) · `.hoist/` (local prompts, replies; gitignored) · `~/.hoist/spend.json` (spend ledger)

## Muse Spark API
- OpenAI-compatible. Base URL `https://api.meta.ai/v1`, key in `MODEL_API_KEY`, OpenAI SDK with `base_url` and `api_key` passed explicitly.
- Model: `muse-spark-1.1` (Meta's guide). Try `muse-spark-1.3` via `--model` or `HOIST_MODEL`; fall back to 1.1 if it errors.
- `reasoning_effort` (minimal…xhigh) sent via `extra_body`; reasoning tokens bill as output. Use low effort for the audit and minimal for per-action checks.
- Pricing used for estimates: $1.25 / 1M input, $4.25 / 1M output (Meta's published starting rates). Check against the billing page after the first call.
- Docs: https://dev.meta.ai/resources/blog/build-with-muse-spark
- Not yet verified: whether Muse Spark accepts image input (not needed for the current plan).

## Muse Code (the agent Hoist guards)
- Meta's terminal coding agent. Reads `AGENTS.md`, falls back to `CLAUDE.md`.
- Skills: `<repo>/.agents/skills/<id>/SKILL.md`; also scans `.claude/skills` and `.codex/skills`. CLI: `muse skills list | inspect | validate`.
- Hooks: `<repo>/.muse/hooks.json`, one event per hook (`PreToolUse`, `PostToolUse`, `UserPromptSubmit`, `SessionStart`, `Stop`, …). Project hooks run only after the folder is trusted. Commands run in the shell outside the sandbox.
- MCP: `mcp_servers` block in settings; `stdio` or `streamable_http`.
- Unknown until tested: the hook's stdin JSON and how it blocks a call (exit code or output). The third-party issue yokoten-labs/yokoten#5 says this was still unverified.
- Docs: https://dev.meta.ai/docs/muse-code/extending · https://dev.meta.ai/resources/blog/build-with-muse-code

## Spend guardrails (the Meta console only has notifications)
- $150 in credits total. Keep these defaults unless the owner says otherwise:
  - `--max-cost 0.50` refuses any single call whose worst case exceeds it
  - `--max-output 12000` caps output plus reasoning tokens
  - `--budget 25` refuses once the ledger total reaches it
- Every new code path that calls Muse Spark must go through the same estimate → check → ledger flow.
- Dry-run before any new kind of call. Never loop API calls without a cap. Muse Code benchmark runs also spend credits, so track them.

## Code style — match the house style
- Python 3.10+, single-file scripts, standard library first. Only third-party dependency: `openai`, imported lazily inside the function that calls the API.
- `argparse` CLI with plain-language help strings; guardrail flags have safe defaults.
- User-facing messages: one line, plain words, say what happened and what to do next (e.g. "Stopped: worst case $0.61 is above --max-cost $0.50.").
- Decision records: see **Decision records (output format)** below. `hoist_audit.py` still writes the older layout; move it to that format when the engine lands.
- Graph: Mermaid `graph LR` with classDefs red/amber/green for one-way/heavy/two-way doors, dashed for unknown.
- Door scale: 1 two-way (an afternoon), 2 heavy (days), 3 one-way (rewrite).
- Decision page look: Geist + Geist Mono, neutral grays with one green accent; red and amber are reserved for door levels. Copy speaks to the user ("You get", "You give up"), no jargon in questions. Respect `prefers-reduced-motion`. Light and dark themes.

## Decision records (output format)
Every decision an agent makes is recorded. How much gets written depends on the door (sources: Olaf Zimmermann, "How to create ADRs — and how not to" and "The MADR template explained and distilled", Medium).

| Door | Who decides | What Hoist writes |
|---|---|---|
| 1 two-way | Muse Code, on its own | One Y-statement line in `docs/decisions/agent-log.md`, marked `not reviewed` until the owner says "Looks right" or opens it as a card |
| 2 heavy | The owner, via the card | MADR light: front matter, title, Context and Problem Statement, Considered Options, Decision Outcome with Consequences |
| 3 one-way | The owner, via the card | Full MADR (below) |

**Files:** `docs/decisions/NNNN-<title-slug>.md` (4-digit number, title states the problem and the choice, e.g. `0004-store-saved-projects-in-postgres.md`) and `docs/decisions/agent-log.md`.

**Y-statement** (agent log line): `In the context of <where>, facing <concern>, Muse Code chose <option> over <other option>, to achieve <quality>, accepting <downside>.` followed by `· two-way · not reviewed` and the date.

**Full MADR, with Hoist's fields in the front matter:**
```markdown
---
status: proposed | accepted | rejected | deprecated | superseded by NNNN
date: YYYY-MM-DD
door: two-way | heavy | one-way
proposed-by: Muse Code (<the task it was doing>)
consulted: Muse Spark (repo analysis, questions)
deciders: project owner | Hoist, delegated by the project owner (no preference)
confidence: high | medium | low
depends-on: [NNNN-slug]
supersedes: NNNN-slug        # only on a pivot
---
# <Title: problem and choice>

## Context and Problem Statement      — the decision as a question, with what the repo shows
## Decision Drivers                   — each tagged (your answer) / (seen in repo) / (docs) / (inferred)
## Considered Options                 — chosen option first; then "Ruled out: <option>, because <reason>"
## Decision Outcome                   — "Chosen: <option>, because <justification>"
### Consequences                      — "Good, because …" and "Bad, because …", now and later
### Confirmation                      — how Hoist keeps it true (hook, `hoist check` in CI) + checklist
## Pros and Cons of the Options       — Good/Bad for every other option; mark the agent's original pick
## More Information                   — confidence and its reasons, revisit conditions (the flips), evidence links
```

**Rules, so records avoid the named anti-patterns** (apply to the card and to Muse Spark's prompts):
- No fit numbers anywhere the user reads: rank words, "Strong on / Weak on", "Matters a lot / Matters / Minor". Numbers only order options internally and appear only under "How Hoist ranked this" (avoids *Pseudo-accuracy*).
- At least two viable options, compared at the same level (engines with how they are hosted, not a product against a file format). An option that fails a hard limit is listed as Ruled out with its reason and source, never as a low-ranked option (avoids *Dummy Alternative*).
- Every option, including the chosen one, has at least one "Bad, because", and at least one consequence tagged Later (avoids *Fairy Tale*, *Free Lunch Coupon*, *Sprint*). Include running and maintaining it, not only building it (avoids *Tunnel Vision*).
- Plain, factual wording; every claim cites a file, an answer, or a doc link; no marketing adjectives (avoids *Sales Pitch*). Keep records short; detail designs go elsewhere (avoids *Mega-ADR*).
- Confidence is always stated with its reasons: medium when any driver is inferred or the top two are a close call; low when delegated or based on a what-if; high only when every driver is seen or answered and the winner is clear.
- "Ask me later" writes `status: proposed` with the short-term placeholder and a revisit point, so a deferred decision is still recorded.

## Working loop
- One step at a time: implement → verify (it actually runs) → validate (gate above) → commit → update Now.
- Repo must be public on GitHub. Commit messages say what was built during the event.
- New ideas → Backlog, not the current step.

## Decisions (dated, append-only — the "why")
- 2026-10-26 — Ship as an agent skill plus CLI, not a web app: zero new UI, installs into tools people already use (the Ponytail / Reverse Engineer Anything pattern).
- 2026-10-26 — Domain is project-setup decisions, not health plans: avoids the "medical advice" red flag the organizers named and fits "Build for your world".
- 2026-10-26 — Scans run locally on the user's own key; no hosted backend, so no paying for strangers' calls.
- 2026-10-26 — Ranking and flip points are deterministic code; the LLM only reads repos and writes plain language. Avoids the "chat wrapper" label.
- 2026-10-26 — Records are ADR Markdown files in the repo, so any agent or person can read decision history without Hoist installed.
- 2026-10-26 — Options, factors and scores come from a hand-written catalog of ~6 decision kinds. Outside the catalog: ask, record, no ranking. Keeps the math defensible.
- 2026-10-26 — The audit uses catalog ids when a decision matches, so audit and engine share one graph.
- 2026-10-26 — In the catch step, Muse Spark rewrites catalog questions in the project's own terms and pre-fills answers it can see in the code. Scores stay in code. Gives Muse visible work in the demo.
- 2026-10-26 — Pivot demo: "client needs data on their own servers" pivots hosting to self-hosted. In the graph, database and CI depend on hosting, so both get flagged and the managed-database pick flips.
- 2026-10-26 — Demo catch scene runs in a fresh small app with no database yet, so the hook has something real to stop.
- 2026-10-26 — The problem is understanding, not only stopping: the owner answered "No preference" to four agent-style multiple-choice questions because none said what each choice meant for them. Every Hoist question now shows the undo cost, gains and costs per option, what decides it, what would flip it, and what "no preference" does.
- 2026-10-26 — UI is a local decision page (map rail + decision card + evidence graph), replacing "zero new UI". Node graphs show how decisions connect; a card is where a decision gets made. Patterns borrowed: TurboTax-style questions about you, Wirecutter-style best fit with trade-offs, Terraform-style consequences before you commit. A terminal text card is the fallback.
- 2026-10-26 — Every proposal can be traced to its evidence (sources → facts → factors → proposal), with each source tagged as seen, your answer, agent's task, docs, or inferred by Muse Spark. This answers "why should I trust this ranking?" and shows Muse Spark's work.
- 2026-10-26 — Muse Code is the agent in the demo, so every tool on screen is Meta's. One SKILL.md in `.claude/skills` serves both Muse Code and Claude Code. If the Muse Code hook can't block a call by Oct 28, demo in Claude Code.
- 2026-10-26 — "No preference" is a real answer: Hoist records the best fit as delegated and adds a Revisit line, so silence is never a silent choice.
- 2026-10-26 — Reviewed against Olaf Zimmermann's ADR guidance. Fit scores are hidden from the user: weighted scoring shown as numbers is the "Pseudo-accuracy" anti-pattern. The deterministic math stays, because it produces the ranking and the flips, but the user sees rank words and trade-offs.
- 2026-10-26 — Every agent decision is recorded, sized by door: Y-statements in `agent-log.md` for two-way doors the agent settles alone, MADR light for heavy doors, full MADR for one-way doors. Records carry accountability (proposed by, consulted, deciders), confidence with reasons, and a Confirmation section saying how Hoist enforces them.
- 2026-10-26 — Options that can't work in context are shown as Ruled out with a source, and replaced by a real alternative (hosted SQLite instead of a SQLite file on Vercel), so the comparison is honest.

## Backlog
- MCP server exposing get_project / open_decision / answer / what_if / commit / pivot
- Git pre-commit hook and GitHub Action that run the same check on PRs (comment: "adds MongoDB; ADR-002 says Postgres")
- One-page landing site on GitHub Pages (only after the demo is recorded; for the "most viral" bonus)
- Support other agents (Codex, Gemini CLI, Cursor rules files)
- Add `firebase.json` and similar backend config files to the audit's `EVIDENCE` list
- Consider making each ADR's front matter the source of truth and `hoist.json` a cache built from it (no second file to keep in sync). The MADR authors also published a YAML variant, YADR (March 2026).
