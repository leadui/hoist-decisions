# Bento Kit

Decision canvases built from swappable compartments. Two files, no dependencies.

A **template** is a fixed bento layout for one kind of decision. Each compartment in it is a **component**. A component can be swapped for another one from the same **family** without breaking the reading order.

## Install

```html
<link rel="stylesheet" href="bento-kit.css">
<script src="bento-kit.js"></script>

<div id="board"></div>
<script>
  BentoKit.render(document.getElementById('board'), 'build-vs-buy', decision);
</script>
```

The script defines a global `BentoKit`. Under CommonJS it also sets `module.exports`. For React, render into a ref inside `useEffect`, or use `BentoKit.toHTML()` with `dangerouslySetInnerHTML`. All decision text is escaped before rendering.

## Templates

| id | For |
|---|---|
| `tech-choice` | Picking a library, protocol, architecture or approach. Maps one-to-one onto MADR. |
| `vendor-select` | Choosing a supplier or SaaS tool, where facts, prices and lock-in matter. |
| `build-vs-buy` | Make, buy or adopt open source. A trend line shows when the cheapest option changes. |
| `product-bet` | Which initiative gets the team next quarter. Many candidates, two axes, kill criteria. |
| `migration` | Moving from A to B safely. The sequence, the gates and the rollback. |
| `process-change` | Changing how people work. Before and after, who carries it, and what would roll it back. |

To swap a compartment, pass the slot name and the new component:

```js
BentoKit.render(el, 'vendor-select', decision, { swap: { facts: 'matrix' } });
```

## Components and when to use them

| Family | Component | Use when | Avoid |
|---|---|---|---|
| evidence | `matrix` Weighted matrix | Judging options against named criteria with defensible ++ to −− ratings | Facts that are really numbers or words |
| evidence | `compare` Comparison table | Differences are facts in words, or before and after | More than 5 options |
| evidence | `bars` Metric bars | One to four numbers decide it | Numbers over time, invented scores |
| evidence | `line` Trend line | A quantity moves over time per option. Marks where a rival overtakes the chosen option | Fewer than four time points |
| evidence | `quadrant` 2×2 | 5–15 candidates traded off on two axes | Two or three options |
| evidence | `risks` Risk heat map | Nameable failure modes, each with a mitigation | Generic risks |
| verdict | `decision` Decision stamp | Always present, exactly once | Hedging |
| effects | `gains` / `costs` / `consequences` | What follows from the choice | An empty costs list |
| effects | `flip` Flip analysis | Any canvas with a matrix. Shows the smallest change that flips the choice | Invented precision |
| effects | `advocate` Devil's advocate | Before review | Treating the notes as verdicts |
| plan | `assumptions` | Bets under uncertainty: the belief, the test, and the kill criterion | Assumptions with no test |
| plan | `timeline` | The decision is a sequence with go/no-go gates | Detailed project plans |
| plan | `confirm` | Always. A number and a date | Activity measures |
| context | `problem`, `people`, `proscons`, `more` | Framing and detail | — |

`BentoKit.guide` holds these rules as data. `BentoKit.recommend({kind, evidence})` applies them. It never swaps out a core compartment (problem, decision, confirm, people).

`BentoKit.compose(decision, {kind, lead, skip, maxExtra, hideEmpty})` goes one step further and lets the data choose: it starts from the template for `kind`, fills each empty slot with a same-family compartment that has data, and appends full-width rows for evidence the template had no slot for (Gains and Costs win over the Consequences ledger; Flip is left out when the Decision stamp already shows it). `lead` puts one compartment on top, such as option cards people tap to pick; `hideEmpty` closes empty compartments instead of hatching them. It returns `{template, evidence, swaps, extra, empty, reasons}`; render `template` as usual. Hoist's decision moments use it with `lead: "proscons"`.

## Decision data

Every field is optional. A compartment with no data renders hatched, with a prompt saying what to add.

```js
{
  title, status, date,
  context: string | string[], question,
  options: [{id, name, desc}], chosen: optionId, because,
  criteria: [{id, name, weight: 0-3}], ratings: {criterionId: {optionId: -2..2}},
  attributes: [{name, values: {optionId: text}, best?: optionId}],
  metrics: [{name, unit, better: 'low'|'high', values: {optionId: number}}],
  series: {name, unit, better, x: [labels], values: {optionId: number[]}},
  quadrant: {x: {name, low, high, min, max}, y: {...}, labels: [tl, tr, bl, br], items: [{name, x, y, option?}]},
  risks: [{text, likelihood: 1-5, impact: 1-5, mitigation}],
  assumptions: [{text, test, killIf, status?}],
  timeline: [{when, what, gate?, state?: 'done'|'now'}],
  consequences: {good: [], bad: [], neutral: []},
  confirmation: [{metric, target, by, how}] | string[],
  people: {decided: [], responsible: [], consulted: [], informed: []},
  prosCons: {optionId: [{kind: 'good'|'bad'|'neutral', text}]},
  more: string[],
  advocate: {persona, verdict, strength, challenges: [{type, title, why}]}
}
```

See `samples.js` for six complete examples, and open `index.html` next to these files for the catalog (templates, components, chooser, devil’s advocate). The same catalog runs on the Hoist site as `site/bentomadr.html`.

## Devil's advocate

```js
const prompt = BentoKit.advocate.prompt(decision, 'cfo');   // send to any LLM, ask for JSON
decision.advocate = { ...await yourLLM(prompt), persona: 'cfo' };
BentoKit.render(el, 'vendor-select', decision, { swap: { costs: 'advocate' } });
```

The personas are `skeptic`, `cfo`, `oncall`, `maintainer`, `security`, `customer` and `rival`. Each reads the same record through a different lens and returns 3–5 challenges. The challenge types are missing option, unlisted cost, weak evidence, missing criterion, risk and open question.

## Extending

- **Add a component.** Assign `BentoKit.components.myId = {id, name, family, question, src, when, avoid, shape, needs: d => bool, empty, render: d => html}`. Escape any text you render with `BentoKit.util.esc` or `BentoKit.util.md`.
- **Add a template.** Assign `BentoKit.templates.myId = {id, name, for, cols, areas: [...rows], md: {cols, areas}, slots: [[area, componentId], ...]}`. Slots are listed in reading order, which is also the phone order.
- **Re-skin.** Override the `--bk-*` custom properties.
