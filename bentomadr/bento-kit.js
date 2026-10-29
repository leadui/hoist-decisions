/*! Bento Kit v0.1 — decision canvases built from swappable compartments.
 *  No dependencies. Load bento-kit.css, then this file; it defines a global `BentoKit`
 *  (and `module.exports` under CommonJS bundlers).
 *
 *    BentoKit.render(element, templateId, decision, {swap: {slotArea: componentId}})
 *    BentoKit.renderComponent(element, componentId, decision)
 *    BentoKit.recommend({kind, evidence: [...]})   → {template, swaps, reasons}
 *    BentoKit.compose(decision, {kind, lead, skip, extras, hideEmpty}) → {template, evidence, swaps, extra, empty, reasons}
 *    BentoKit.advocate.prompt(decision, personaIds) → string for any LLM; .render(result) → html
 */
(function (root) {
  'use strict';

  /* ───────── helpers ───────── */
  const esc = s => String(s ?? '').replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
  const md = s => esc(s)
    .replace(/`([^`]+)`/g, '<code>$1</code>')
    .replace(/\*\*([^*]+)\*\*/g, '<strong>$1</strong>')
    .replace(/\[([^\]]+)\]\((https?:\/\/[^)\s]+)\)/g, '<a href="$2" target="_blank" rel="noopener">$1</a>');
  const arr = v => v == null ? [] : Array.isArray(v) ? v : [v];
  const opt = (d, id) => (d.options || []).find(o => o.id === id);
  const optName = (d, id) => opt(d, id)?.name ?? id;
  const SYM = {'2':'++','1':'+','0':'0','-1':'−','-2':'−−'};
  const sym = v => v == null ? '' : SYM[v];
  const WORD = {'2':'strong fit','1':'fit','0':'neutral','-1':'weak','-2':'conflict'};
  const WNAME = ['not counted', 'normal', 'important', 'critical'];
  const signed = n => n > 0 ? '+' + n : n < 0 ? '−' + Math.abs(n) : '0';
  const num = (n, unit) => {
    const s = Math.abs(n) >= 1000 ? n.toLocaleString('en-US', {maximumFractionDigits:0}) : String(+n.toFixed(2));
    if(!unit) return s;
    if(unit === '$' || unit === '€' || unit === '£') return unit + s;
    if(/^[$€£]k$/.test(unit)) return unit[0] + s + 'k';
    return s + (unit === '%' ? '%' : ' ' + unit);
  };
  const short = x => { const h = String(x).split(/[:;(,]| for | must | within | before | including | and | so /i)[0].trim(); const w = h.split(/\s+/); return w.length > 5 ? w.slice(0, 5).join(' ') + '…' : h; };
  function ticks(min, max, count = 5){
    if(min === max){ max = min + 1; }
    const raw = (max - min) / count, mag = 10 ** Math.floor(Math.log10(raw)), n = raw / mag;
    const step = (n < 1.5 ? 1 : n < 3 ? 2 : n < 7 ? 5 : 10) * mag;
    const lo = Math.floor(min / step) * step, hi = Math.ceil(max / step) * step, out = [];
    for(let v = lo; v <= hi + step / 1e6; v += step) out.push(+v.toFixed(10));
    return out;
  }
  const SERIES = ['var(--bk-s1)', 'var(--bk-s2)', 'var(--bk-s3)', 'var(--bk-s4)', 'var(--bk-s5)'];
  const seriesColor = (d, i) => {
    const ids = (d.options || []).map(o => o.id), ci = ids.indexOf(d.chosen);
    if(i === ci) return SERIES[0];
    const others = ids.map((_, k) => k).filter(k => k !== ci);
    return SERIES[1 + (others.indexOf(i) % 4)];
  };

  /* ───────── analysis ───────── */
  const weights = d => (d.criteria || []).map(c => c.weight ?? 1);
  function scores(d, W = weights(d), ov = null){
    return (d.options || []).map(o => {
      let sum = 0, n = 0;
      (d.criteria || []).forEach((c, ci) => {
        const v = ov && ov.c === c.id && ov.o === o.id ? ov.v : d.ratings?.[c.id]?.[o.id];
        if(v != null){ sum += v * W[ci]; n++; }
      });
      return {id: o.id, sum, n};
    });
  }
  function robustness(d){
    const os = d.options || [], cs = d.criteria || [], ci = os.findIndex(o => o.id === d.chosen), base = scores(d);
    if(ci < 0 || os.length < 2 || !base.some(t => t.n)) return null;
    const others = os.map((_, i) => i).filter(i => i !== ci);
    const runner = others.reduce((a, b) => base[b].sum > base[a].sum ? b : a);
    const margin = base[ci].sum - base[runner].sum;
    const loser = sc => { let w = -1; others.forEach(i => { if(sc[i].sum > sc[ci].sum && (w < 0 || sc[i].sum > sc[w].sum)) w = i; }); return w; };
    const W = weights(d), flips = [];
    cs.forEach((c, k) => {
      const tries = [0,1,2,3].filter(w => w !== W[k]).sort((a, b) => Math.abs(a - W[k]) - Math.abs(b - W[k]));
      for(const w of tries){ const W2 = [...W]; W2[k] = w; const l = loser(scores(d, W2)); if(l > -1){ flips.push({type:'weight', c:k, w, from:W[k], winner:l, cost:Math.abs(w - W[k])}); break; } }
    });
    cs.forEach((c, k) => os.forEach((o, oi) => {
      const cur = d.ratings?.[c.id]?.[o.id];
      const tries = [-2,-1,0,1,2].filter(v => v !== cur).sort((a, b) => Math.abs(a - (cur ?? 0)) - Math.abs(b - (cur ?? 0)));
      for(const v of tries){ const l = loser(scores(d, W, {c:c.id, o:o.id, v})); if(l > -1){ flips.push({type:'cell', c:k, oi, v, from:cur, winner:l, cost:Math.abs(v - (cur ?? 0))}); break; } }
    }));
    flips.sort((a, b) => a.cost - b.cost || (a.type === 'weight' ? -1 : 1));
    const min = flips.length ? flips[0].cost : 99;
    const verdict = margin < 0 ? 'contradicted' : min <= 1 ? 'fragile' : min <= 2 ? 'sensitive' : 'robust';
    const say = f => {
      const dr = `${short(cs[f.c].name)}`, win = os[f.winner].name;
      if(f.type === 'weight') return f.w === 0 ? `If ${dr} stopped counting, ${win} would win.` : `If ${dr} were ${WNAME[f.w]} instead of ${WNAME[f.from]}, ${win} would win.`;
      return `If ${os[f.oi].name} scored ${sym(f.v)} instead of ${f.from == null ? 'unrated' : sym(f.from)} on ${dr}, ${win} would win.`;
    };
    return {margin, runner: os[runner].id, verdict, flips: flips.slice(0, 3).map(f => ({...f, text: say(f)}))};
  }
  function crossover(d){
    const s = d.series; if(!s || !s.values || !d.chosen || !s.values[d.chosen]) return null;
    const c = s.values[d.chosen], better = s.better === 'high' ? 1 : -1;
    let first = null;
    Object.keys(s.values).filter(k => k !== d.chosen).forEach(k => {
      const o = s.values[k];
      for(let i = 1; i < c.length; i++){
        const a = (o[i-1] - c[i-1]) * better, b = (o[i] - c[i]) * better;
        if(a <= 0 && b > 0){ const t = a === b ? 0 : -a / (b - a); if(!first || i - 1 + t < first.at) first = {at: i - 1 + t, rival: k, i}; break; }
      }
    });
    return first;
  }

  /* ───────── component bits ───────── */
  const prompt = t => `<p class="bk-prompt">${t}</p>`;
  const list = (items, cls = '') => `<ul class="bk-list ${cls}">${arr(items).map(t => `<li>${md(t)}</li>`).join('')}</ul>`;
  const dots = w => `${'●'.repeat(w)}<span class="off">${'●'.repeat(3 - w)}</span>`;
  const VERDICT = {robust:'Robust', sensitive:'Sensitive', fragile:'Fragile', contradicted:'Contradicted'};

  function flipBlock(d){
    const r = robustness(d); if(!r) return '';
    return `<div class="bk-flip"><span class="bk-label">What would flip it?</span>
      <div class="bk-flip-top"><span class="bk-margin">${signed(r.margin)}</span><span>${r.margin >= 0 ? 'ahead of' : 'behind'} ${esc(optName(d, r.runner))}</span><span class="bk-verdict ${r.verdict}">${VERDICT[r.verdict]}</span></div>
      ${r.flips.length ? `<ul class="bk-flips">${r.flips.map(f => `<li>${esc(f.text)}</li>`).join('')}</ul>` : '<p>No single change to a weight or a rating hands the win to another option.</p>'}</div>`;
  }

  function lineSVG(d, W = 600){
    const s = d.series, keys = (d.options || []).map(o => o.id).filter(k => s.values[k]);
    W = Math.max(280, Math.round(W)); const H = Math.round(Math.min(320, Math.max(220, W * .42))), P = {l:52, r:16, t:18, b:34}, n = s.x.length;
    const all = keys.flatMap(k => s.values[k]);
    const T = ticks(Math.min(0, ...all), Math.max(...all));
    const y0 = T[0], y1 = T[T.length - 1];
    const X = i => P.l + (W - P.l - P.r) * (n === 1 ? .5 : i / (n - 1));
    const Y = v => P.t + (H - P.t - P.b) * (1 - (v - y0) / (y1 - y0));
    const grid = T.map(t => `<line class="grid" x1="${P.l}" x2="${W - P.r}" y1="${Y(t)}" y2="${Y(t)}"/><text x="${P.l - 8}" y="${Y(t) + 4}" text-anchor="end">${esc(num(t, s.unit))}</text>`).join('');
    const step = Math.ceil(n / 8);
    const xl = s.x.map((x, i) => i % step === 0 || i === n - 1 ? `<text x="${X(i)}" y="${H - P.b + 18}" text-anchor="middle">${esc(x)}</text>` : '').join('');
    const lines = keys.map(k => {
      const i = (d.options || []).findIndex(o => o.id === k), col = seriesColor(d, i), chosen = k === d.chosen;
      const pts = s.values[k].map((v, j) => `${X(j).toFixed(1)},${Y(v).toFixed(1)}`).join(' ');
      const last = s.values[k][n - 1];
      return `<polyline points="${pts}" fill="none" stroke="${col}" stroke-width="${chosen ? 3.2 : 2}" stroke-linejoin="round" stroke-linecap="round"/>`
        + `<circle cx="${X(n - 1)}" cy="${Y(last)}" r="${chosen ? 4.5 : 3.5}" fill="${col}"/>`;
    }).join('');
    const cx = crossover(d);
    let note = '';
    if(cx){
      const xi = X(cx.at), better = s.better === 'high' ? 'ahead' : 'cheaper';
      const label = `${short(optName(d, cx.rival))} is ${better} after ${s.x[Math.floor(cx.at)]}`;
      const est = label.length * 6.4, anchor = xi + est + 8 > W - P.r ? 'end' : 'start', dx = anchor === 'end' ? -6 : 6;
      note = `<line class="cross" x1="${xi}" x2="${xi}" y1="${P.t}" y2="${H - P.b}"/><text class="note" x="${xi + dx}" y="${P.t + 12}" text-anchor="${anchor}">${esc(label)}</text>`;
    }
    return `<svg class="bk-svg" viewBox="0 0 ${W} ${H}" width="${W}" height="${H}" role="img" aria-label="${esc(s.name)} over ${esc(s.x[0])} to ${esc(s.x[n - 1])}"><line class="axis" x1="${P.l}" x2="${P.l}" y1="${P.t}" y2="${H - P.b}"/>${grid}${xl}${note}${lines}</svg>`;
  }
  function lineChart(d){
    const s = d.series, keys = (d.options || []).map(o => o.id).filter(k => s.values[k]);
    const legend = `<p class="bk-legend">${keys.map(k => { const i = (d.options || []).findIndex(o => o.id === k); return `<span class="bk-key"><i style="background:${seriesColor(d, i)};height:${k === d.chosen ? 4 : 3}px"></i>${esc(optName(d, k))}${k === d.chosen ? ' (chosen)' : ''}</span>`; }).join('')}</p>`;
    return `<p class="bk-label">${esc(s.name)}${s.better ? ` · ${s.better === 'low' ? 'lower' : 'higher'} is better` : ''}</p>${legend}<div class="bk-fluid" data-bk-line>${lineSVG(d)}</div>`;
  }

  function quadrantChart(d){
    const q = d.quadrant, S = 420, P = {l:34, r:12, t:12, b:34}, w = S - P.l - P.r, h = S - P.t - P.b;
    const xr = [q.x.min ?? 0, q.x.max ?? 10], yr = [q.y.min ?? 0, q.y.max ?? 10];
    const X = v => P.l + w * (v - xr[0]) / (xr[1] - xr[0]), Y = v => P.t + h * (1 - (v - yr[0]) / (yr[1] - yr[0]));
    const mx = P.l + w / 2, my = P.t + h / 2, L = q.labels || [];
    const quads = `<rect class="qbg" x="${P.l}" y="${P.t}" width="${w / 2 - 1}" height="${h / 2 - 1}" rx="6"/><rect class="qbg" x="${mx + 1}" y="${P.t}" width="${w / 2 - 1}" height="${h / 2 - 1}" rx="6"/><rect class="qbg" x="${P.l}" y="${my + 1}" width="${w / 2 - 1}" height="${h / 2 - 1}" rx="6"/><rect class="qbg" x="${mx + 1}" y="${my + 1}" width="${w / 2 - 1}" height="${h / 2 - 1}" rx="6"/>`
      + [[P.l + 8, P.t + 16, 'start'], [P.l + w - 8, P.t + 16, 'end'], [P.l + 8, P.t + h - 8, 'start'], [P.l + w - 8, P.t + h - 8, 'end']].map(([x, y, a], i) => L[i] ? `<text class="qlbl" x="${x}" y="${y}" text-anchor="${a}">${esc(L[i])}</text>` : '').join('');
    const axes = `<text x="${P.l + w / 2}" y="${S - 8}" text-anchor="middle">${esc(q.x.name)} →</text><text x="${P.l}" y="${S - P.b + 14}" text-anchor="start">${esc(q.x.low || 'low')}</text><text x="${P.l + w}" y="${S - P.b + 14}" text-anchor="end">${esc(q.x.high || 'high')}</text>`
      + `<text transform="translate(14 ${P.t + h / 2}) rotate(-90)" text-anchor="middle">${esc(q.y.name)} →</text>`;
    const pts = (q.items || []).map(it => {
      const chosen = it.option && it.option === d.chosen, x = X(it.x), y = Y(it.y);
      const anchor = x > P.l + w * .7 ? 'end' : 'start', dx = anchor === 'end' ? -10 : 10;
      return `<circle cx="${x}" cy="${y}" r="${chosen ? 9 : 6}" fill="${chosen ? 'var(--bk-signal)' : it.option ? 'var(--bk-accent)' : 'var(--bk-muted)'}" stroke="var(--bk-tile)" stroke-width="2"/>`
        + `<text class="lbl${chosen ? ' strong' : ''}" x="${x + dx}" y="${y + 4}" text-anchor="${anchor}">${esc(it.name)}</text>`;
    }).join('');
    return `<svg class="bk-svg" viewBox="0 0 ${S} ${S}" style="max-width:520px" role="img" aria-label="${esc(q.y.name)} against ${esc(q.x.name)}">${quads}${axes}${pts}</svg>
      <p class="bk-legend"><span class="bk-key"><i style="background:var(--bk-signal);height:8px;width:8px;border-radius:50%"></i>Chosen</span><span class="bk-key"><i style="background:var(--bk-accent);height:8px;width:8px;border-radius:50%"></i>Considered option</span><span class="bk-key"><i style="background:var(--bk-muted);height:8px;width:8px;border-radius:50%"></i>Other candidate</span></p>`;
  }

  function heat(d){
    const rs = d.risks || [], cells = [];
    for(let im = 5; im >= 1; im--){
      cells.push(`<span class="ax">${im}</span>`);
      for(let li = 1; li <= 5; li++){
        const sc = li * im, band = sc >= 17 ? 4 : sc >= 10 ? 3 : sc >= 5 ? 2 : 1;
        const here = rs.map((r, i) => ({r, i})).filter(x => x.r.likelihood === li && x.r.impact === im);
        cells.push(`<span class="cell s${band}" title="Likelihood ${li}, impact ${im}">${here.map(x => `<span class="bk-dot">${x.i + 1}</span>`).join('')}</span>`);
      }
    }
    cells.push('<span></span>', ...[1,2,3,4,5].map(n => `<span class="ax">${n}</span>`));
    const sorted = rs.map((r, i) => ({r, i})).sort((a, b) => b.r.likelihood * b.r.impact - a.r.likelihood * a.r.impact);
    return `<div class="bk-heat" role="img" aria-label="Risk heat map, impact by likelihood">${cells.join('')}</div><div class="bk-heat-axes"><span>↑ Impact</span><span>Likelihood →</span></div>
      <ol class="bk-rlist">${sorted.map(({r, i}) => `<li><span class="bk-dot">${i + 1}</span><span>${md(r.text)}${r.mitigation ? `<small>Mitigation: ${md(r.mitigation)}</small>` : ''}</span></li>`).join('')}</ol>`;
  }

  /* ───────── components ─────────
     family: context · evidence · verdict · effects · plan
     Swap a slot only for a component of the same family: the template's reading order depends on it. */
  const C = {};
  const def = (id, spec) => { C[id] = {id, ...spec}; };

  def('problem', {core:true, name:'Problem statement', family:'context', question:'What problem are we solving?', src:'Context and problem statement',
    when:'Always first. Two or three short paragraphs, ending on the one question the decision answers.',
    avoid:'Background history nobody needs to decide. Put links in More information.',
    shape:'context: string | string[], question?: string',
    needs: d => arr(d.context).length > 0 || !!d.question,
    empty:'Describe the situation and end with the question this decision answers.',
    render: d => `<div class="bk-prose">${arr(d.context).map(p => `<p>${md(p)}</p>`).join('')}${d.question ? `<p class="bk-ask">${md(d.question)}</p>` : ''}</div>`});

  def('decision', {core:true, name:'Decision stamp', family:'verdict', hero:true, question:'What did we choose, and why?', src:'Decision outcome',
    when:'Every canvas has exactly one. It is the heaviest compartment, so place it where the eye lands after the evidence.',
    avoid:'Hedging. If nothing is chosen yet, leave it empty and let the hatching show the gap.',
    shape:'chosen: optionId, because: string, (criteria + ratings for the flip summary)',
    needs: d => !!d.chosen,
    empty:'Name the chosen option and say why, in terms of the drivers or evidence above.',
    render: (d, o) => `<p class="bk-chosen">${esc(optName(d, d.chosen))}</p>${d.because ? `<p class="bk-because"><b>Because</b>${md(d.because)}</p>` : ''}${o.flip === false ? '' : flipBlock(d)}`});

  def('matrix', {name:'Weighted matrix', family:'evidence', question:'What matters, and how does each option measure up?', src:'Criteria × options',
    when:'Options judged against named criteria where the honest answer is a judgement (++ to −−), not a measurement. Best with 2–5 options and 3–8 criteria.',
    avoid:'Facts that are really numbers or text (use Comparison table or Metric bars). Ratings nobody can defend: they make the totals look more certain than they are.',
    shape:'criteria: [{id, name, weight 0–3}], ratings: {criterionId: {optionId: −2…2}}',
    needs: d => (d.criteria || []).length > 0 && (d.options || []).length > 0,
    empty:'List the criteria that matter and rate each option against them.',
    render: d => {
      const os = d.options, cs = d.criteria, W = weights(d), sc = scores(d), best = Math.max(...sc.map(t => t.sum)), rated = sc.some(t => t.n);
      return `<div class="bk-scroll"><table class="bk-mx" style="--cols:${os.length}"><thead><tr><th></th>${os.map(o => `<th scope="col" class="bk-oh${o.id === d.chosen ? ' is-chosen' : ''}">${esc(o.name)}${o.id === d.chosen ? '<span class="bk-stamp">Chosen</span>' : ''}</th>`).join('')}</tr></thead>
        <tbody>${cs.map((c, k) => `<tr><th scope="row" class="bk-drv"><span class="bk-wt" role="img" aria-label="Weight: ${WNAME[W[k]]}">${dots(W[k])}</span><span class="bk-dn">C${k + 1}</span>${md(c.name)}</th>${os.map(o => {
          const v = d.ratings?.[c.id]?.[o.id]; const cls = v == null ? 'bk-vn' : v < 0 ? 'bk-vm' + (-v) : 'bk-v' + v;
          return `<td${o.id === d.chosen ? ' class="is-chosen"' : ''}><span class="bk-c ${cls}" role="img" aria-label="${esc(o.name)}: ${v == null ? 'not rated' : WORD[v]}">${sym(v) || '·'}</span></td>`; }).join('')}</tr>`).join('')}</tbody>
        <tfoot><tr><th scope="row" class="bk-drv bk-label">Weighted fit</th>${sc.map(t => `<td class="bk-tot${rated && t.sum === best ? ' best' : ''}">${t.n ? signed(t.sum) : '–'}${rated && t.sum === best ? '<small>best fit</small>' : ''}</td>`).join('')}</tr></tfoot></table></div>
        <p class="bk-legend"><span><b>++</b> strong fit</span><span><b>+</b> fit</span><span><b>0</b> neutral</span><span><b>−</b> weak</span><span><b>−−</b> conflict</span><span><b style="color:var(--bk-accent)">●●●</b> weight</span></p>`;
    }});

  def('compare', {name:'Comparison table', family:'evidence', question:'How do the options differ?', src:'Side-by-side facts',
    when:'Facts that are words, not scores: pricing model, data residency, licence, who owns it. Also before/after for process changes. Mark the best cell per row only when it is a fact, not an opinion.',
    avoid:'More than 5 options (readers stop comparing) or rows that are all the same. Numbers you want people to compare at a glance belong in Metric bars.',
    shape:'attributes: [{name, values: {optionId: string}, best?: optionId}]',
    needs: d => (d.attributes || []).length > 0 && (d.options || []).length > 0,
    empty:'List the facts that separate the options, one row per attribute.',
    render: d => { const os = d.options; return `<div class="bk-scroll"><table class="bk-cmpt" style="--cols:${os.length}"><thead><tr><th></th>${os.map(o => `<th scope="col" class="${o.id === d.chosen ? 'is-chosen' : ''}">${esc(o.name)}</th>`).join('')}</tr></thead>
      <tbody>${d.attributes.map(a => `<tr><th scope="row">${esc(a.name)}</th>${os.map(o => `<td class="${[o.id === d.chosen ? 'is-chosen' : '', a.best === o.id ? 'is-best' : ''].join(' ')}">${md(a.values?.[o.id] ?? '—')}</td>`).join('')}</tr>`).join('')}</tbody></table></div>`; }});

  def('bars', {name:'Metric bars', family:'evidence', question:'What do the numbers say?', src:'Key measures per option',
    when:'One to four numbers per option that really decide it: price, latency, setup days. Bars start at zero, so lengths stay honest.',
    avoid:'Numbers that change over time (use Trend line) or scores you invented (use Weighted matrix). Mixed units on one bar set.',
    shape:'metrics: [{name, unit, better: "low"|"high", values: {optionId: number}}]',
    needs: d => (d.metrics || []).length > 0,
    empty:'Add the one to four measurements that separate the options.',
    render: d => `<div class="bk-metrics">${d.metrics.map(m => {
      const ids = (d.options || []).map(o => o.id).filter(k => m.values[k] != null), vals = ids.map(k => m.values[k]), max = Math.max(...vals, 0) || 1;
      const best = m.better === 'high' ? Math.max(...vals) : m.better === 'low' ? Math.min(...vals) : null;
      return `<div class="bk-metric"><div class="bk-mh"><b>${esc(m.name)}</b><span>${m.better ? (m.better === 'low' ? 'Lower is better' : 'Higher is better') : ''}</span></div>
        ${ids.map(k => `<div class="bk-bar${k === d.chosen ? ' is-chosen' : ''}${m.values[k] === best ? ' is-best' : ''}"><span class="nm">${esc(optName(d, k))}</span><span class="bk-track"><span class="bk-fill" style="display:block;width:${(100 * Math.max(0, m.values[k]) / max).toFixed(1)}%"></span></span><span class="bk-val">${esc(num(m.values[k], m.unit))}</span></div>`).join('')}</div>`;
    }).join('')}</div>`});

  def('line', {name:'Trend line', family:'evidence', question:'How does it play out over time?', src:'Projection over time',
    when:'A quantity that moves over time per option: cumulative cost, adoption, load. The kit marks where a rival overtakes the chosen option, which is usually the moment to revisit.',
    avoid:'Fewer than four time points (use Metric bars). More than five options on one chart.',
    shape:'series: {name, unit, better: "low"|"high", x: string[], values: {optionId: number[]}}',
    needs: d => !!(d.series && d.series.x && Object.keys(d.series.values || {}).length),
    empty:'Add a series over time, such as cumulative cost per option by month.',
    render: d => lineChart(d)});

  def('quadrant', {name:'2×2 quadrant', family:'evidence', question:'Where does each candidate land?', src:'Two-axis trade-off',
    when:'Many candidates (5–15) traded off on two dimensions, such as impact and effort or risk and reward. Good for “which bet do we fund?”.',
    avoid:'Two or three options (a table is clearer). Axes that are really the same thing. Pretending positions are measured when they are guesses: label the axes honestly.',
    shape:'quadrant: {x: {name, low, high, min, max}, y: {…}, labels: [topLeft, topRight, bottomLeft, bottomRight], items: [{name, x, y, option?}]}',
    needs: d => !!(d.quadrant && (d.quadrant.items || []).length),
    empty:'Place the candidates on two axes, such as impact against effort.',
    render: d => quadrantChart(d)});

  def('risks', {name:'Risk heat map', family:'evidence', question:'What could go wrong?', src:'Likelihood × impact',
    when:'Plans with real failure modes: migrations, launches, vendor bets. Each risk gets a mitigation, or it is just worry.',
    avoid:'Generic risks that apply to every project. Scoring to two decimals: the grid is 1–5 on purpose.',
    shape:'risks: [{text, likelihood 1–5, impact 1–5, mitigation}]',
    needs: d => (d.risks || []).length > 0,
    empty:'List what could go wrong, how likely and how bad, and what you will do about it.',
    render: d => heat(d)});

  def('assumptions', {name:'Assumptions and kill criteria', family:'plan', question:'What would change our mind?', src:'Beliefs, tests and kill criteria',
    when:'Any bet made under uncertainty. Write the belief, how you will test it, and the result that makes you reverse. It turns “we were wrong” into a planned event.',
    avoid:'Assumptions with no test, or a kill criterion nobody will check.',
    shape:'assumptions: [{text, test, killIf, status?: "untested"|"holding"|"broken"}]',
    needs: d => (d.assumptions || []).length > 0,
    empty:'Write the beliefs this decision rests on, how you will test each, and what result would make you reverse.',
    render: d => `<div class="bk-asm">${d.assumptions.map(a => `<article>${a.status ? `<span class="bk-pill ${esc(a.status)}">${esc(a.status)}</span>` : ''}<b>${md(a.text)}</b><dl>${a.test ? `<dt>Test</dt><dd>${md(a.test)}</dd>` : ''}${a.killIf ? `<dt>Kill if</dt><dd class="kill">${md(a.killIf)}</dd>` : ''}</dl></article>`).join('')}</div>`});

  def('timeline', {name:'Timeline with gates', family:'plan', question:'How do we get there?', src:'Phases and go/no-go gates',
    when:'Decisions that are really a sequence: migrations, rollouts, pilots. Gates say what must be true before the next step.',
    avoid:'Detailed project plans. Five to seven steps is the ceiling for a canvas.',
    shape:'timeline: [{when, what, gate?, state?: "done"|"now"}]',
    needs: d => (d.timeline || []).length > 0,
    empty:'List the phases and the go/no-go gate between each.',
    render: d => `<ol class="bk-tl">${d.timeline.map(t => `<li class="${esc(t.state || '')}"><span class="when">${esc(t.when)}</span><span>${md(t.what)}</span>${t.gate ? `<span class="gate">${md(t.gate)}</span>` : ''}</li>`).join('')}</ol>`});

  def('confirm', {core:true, name:'Success measures', family:'plan', question:'How will we know it worked?', src:'Confirmation',
    when:'Always, ideally as a number with a date. This is what turns a decision into something you can check.',
    avoid:'Activity measures (“shipped”) in place of outcomes.',
    shape:'confirmation: [{metric, target, by, how}] | string[]',
    needs: d => arr(d.confirmation).length > 0,
    empty:'Name the measure, the target and the date that show this decision worked.',
    render: d => { const cs = arr(d.confirmation); return typeof cs[0] === 'string' ? `<div class="bk-prose">${cs.map(p => `<p>${md(p)}</p>`).join('')}</div>`
      : `<div class="bk-kpis">${cs.map(k => `<div class="bk-kpi"><span class="t">${esc(k.target)}</span><span class="m">${esc(k.metric)}</span>${k.by ? `<small>By ${esc(k.by)}</small>` : ''}${k.how ? `<small>${md(k.how)}</small>` : ''}</div>`).join('')}</div>`; }});

  const cq = (kind, label) => d => list(d.consequences?.[kind] || [], kind);
  def('consequences', {name:'Consequences ledger', family:'effects', question:'What follows from it?', src:'Consequences',
    when:'One compartment for gains, costs and neutral effects together, when space is tight.',
    avoid:'Leaving costs empty. Every real decision has one.',
    shape:'consequences: {good: [], bad: [], neutral: []}',
    needs: d => ['good','bad','neutral'].some(k => (d.consequences?.[k] || []).length),
    empty:'What gets easier, and what gets harder?',
    render: d => ['good','bad','neutral'].filter(k => (d.consequences?.[k] || []).length).map(k => `<p class="bk-label">${{good:'Gains', bad:'Costs', neutral:'Neutral'}[k]}</p>${cq(k)(d)}`).join('')});
  def('gains', {name:'Gains', family:'effects', question:'What gets better?', src:'Consequences · good',
    when:'Paired with Costs when the canvas has room for both. Shown side by side, they make one-sided records obvious.', avoid:'Restating the option’s pros. Write what changes for the team or the users.',
    shape:'consequences.good: string[]', needs: d => (d.consequences?.good || []).length > 0, empty:'What becomes easier, faster or cheaper?', render: cq('good')});
  def('costs', {name:'Costs', family:'effects', question:'What gets harder?', src:'Consequences · bad and neutral',
    when:'Always paired with Gains. An empty Costs compartment is the most common gap in decision records.', avoid:'Softening costs into “trade-offs”. Say what gets worse.',
    shape:'consequences.bad, consequences.neutral: string[]', needs: d => (d.consequences?.bad || []).length > 0, empty:'No downside recorded. Every real decision has one.',
    render: d => cq('bad')(d) + ((d.consequences?.neutral || []).length ? `<p class="bk-label">Neutral</p>${cq('neutral')(d)}` : '')});

  def('flip', {name:'Flip analysis', family:'effects', question:'What would flip it?', src:'Robustness of the choice',
    when:'Any canvas with a Weighted matrix. It finds the smallest change to a weight or rating that hands the win to another option, which tells reviewers where to push.',
    avoid:'Matrices with invented precision: the analysis is only as honest as the ratings.',
    shape:'derived from criteria + ratings + chosen', needs: d => !!robustness(d), empty:'Add criteria, ratings and a chosen option to see how robust the choice is.',
    render: d => flipBlock(d)});

  def('proscons', {name:'Option cards', family:'context', shelf:true, question:'Why each option won or lost', src:'Pros and cons of the options',
    when:'The detail behind the evidence: each option’s pros and cons, with a tally bar. Works well as a full-width shelf along the base.',
    avoid:'Pros that are only the absence of a con.',
    shape:'options: [{id, name, desc}], prosCons: {optionId: [{kind: "good"|"bad"|"neutral", text}]}',
    needs: d => (d.options || []).length > 0,
    empty:'Each considered option gets a card here with its pros and cons.',
    render: d => `<div class="bk-opts">${d.options.map(o => {
      const items = d.prosCons?.[o.id] || [], n = {good:0, neutral:0, bad:0}; items.forEach(i => n[i.kind]++);
      return `<article class="bk-opt${o.id === d.chosen ? ' is-chosen' : ''}"><div class="bk-opt-top"><h3>${esc(o.name)}</h3>${o.id === d.chosen ? '<span class="bk-stamp">Chosen</span>' : ''}</div>${o.desc ? `<p class="desc">${md(o.desc)}</p>` : ''}
        ${items.length ? `<div class="bk-tally" role="img" aria-label="${n.good} good, ${n.neutral} neutral, ${n.bad} bad">${['good','neutral','bad'].map(k => n[k] ? `<span class="${k[0]}" style="flex:${n[k]}"></span>` : '').join('')}</div><ul class="bk-pc">${items.map(i => `<li class="${i.kind}"><span>${md(i.text)}</span></li>`).join('')}</ul>` : prompt('No pros or cons recorded.')}</article>`; }).join('')}</div>`});

  def('people', {core:true, name:'People', family:'context', question:'Who decided, who heard?', src:'Decided · consulted · informed',
    when:'Every record. For process and org changes, promote it to a large compartment: who carries the change matters as much as the change.',
    avoid:'Listing whole teams as “decided by”. Name the people accountable.',
    shape:'people: {decided: [], responsible?: [], consulted: [], informed: []}',
    needs: d => !!(d.people && Object.values(d.people).some(v => arr(v).length)),
    empty:'Name who decided, who was consulted and who needs to know.',
    render: d => `<dl class="bk-people">${[['decided','Decided by'],['responsible','Carries it out'],['consulted','Consulted'],['informed','Informed']].filter(([k]) => arr(d.people[k]).length).map(([k, l]) => `<div><dt class="bk-label">${l}</dt><dd>${arr(d.people[k]).map(p => `<span class="bk-chip">${esc(p)}</span>`).join('')}</dd></div>`).join('')}</dl>`});

  def('more', {name:'More information', family:'context', question:'Where to dig deeper', src:'Links and notes',
    when:'Spikes, tickets, related decisions, and when to revisit.', avoid:'Content the reader needs to understand the decision. That belongs in the problem.',
    shape:'more: string[]', needs: d => arr(d.more).length > 0, empty:'Link spikes, tickets and related decisions, and say when to revisit.',
    render: d => `<div class="bk-prose">${arr(d.more).map(p => `<p>${md(p)}</p>`).join('')}</div>`});

  def('advocate', {name:'Devil’s advocate', family:'effects', question:'What would a critic say?', src:'Challenges from a chosen persona',
    when:'Before review. Pick personas that match the risk: the CFO for spend, the on-call engineer for operability, the future maintainer for complexity.',
    avoid:'Treating the notes as verdicts. They are prompts for the team to answer.',
    shape:'advocate: {persona, verdict, strength, challenges: [{type, title, why}]} (from BentoKit.advocate)',
    needs: d => !!(d.advocate && (d.advocate.challenges || []).length),
    empty:'Run the devil’s advocate to fill this compartment with challenges.',
    render: d => renderNotes(d.advocate)});

  /* ───────── templates ─────────
     slots are in reading order (that is also the phone order). area names double as grid-area names. */
  const T = {};
  const tpl = (id, spec) => { T[id] = {id, ...spec}; };
  tpl('tech-choice', {name:'Technology choice', for:'Picking a library, protocol, architecture or approach. Maps one-to-one onto MADR.',
    cols:'1fr 1.3fr 1.3fr 1fr', areas:['problem evidence evidence gains','problem evidence evidence costs','people verdict verdict confirm','shelf shelf shelf shelf'],
    md:{cols:'1fr 1fr', areas:['problem problem','evidence evidence','verdict verdict','gains costs','confirm people','shelf shelf']},
    slots:[['problem','problem'],['evidence','matrix'],['verdict','decision'],['gains','gains'],['costs','costs'],['confirm','confirm'],['people','people'],['shelf','proscons']]});
  tpl('vendor-select', {name:'Vendor selection', for:'Choosing a supplier or SaaS tool, where facts, prices and lock-in matter more than taste.',
    cols:'1fr 1fr 1fr 1fr', areas:['problem facts facts facts','numbers numbers verdict verdict','risks risks verdict verdict','risks risks costs people'],
    md:{cols:'1fr 1fr', areas:['problem problem','facts facts','numbers numbers','verdict verdict','risks risks','costs people']},
    slots:[['problem','problem'],['facts','compare'],['numbers','bars'],['verdict','decision'],['risks','risks'],['costs','costs'],['people','people']]});
  tpl('build-vs-buy', {name:'Build vs buy', for:'Make, buy, or adopt open source. The trend line shows when the cheapest option changes, and the assumptions say when to revisit.',
    cols:'1fr 1.2fr 1.2fr 1fr', areas:['problem trend trend trend','facts facts verdict verdict','beliefs beliefs plan plan'],
    md:{cols:'1fr 1fr', areas:['problem problem','trend trend','facts facts','verdict verdict','beliefs beliefs','plan plan']},
    slots:[['problem','problem'],['trend','line'],['facts','compare'],['verdict','decision'],['beliefs','assumptions'],['plan','timeline']]});
  tpl('product-bet', {name:'Product bet', for:'Which initiative gets the team next quarter. Many candidates, two axes, explicit kill criteria.',
    cols:'1fr 1.2fr 1.2fr 1fr', areas:['problem map map verdict','beliefs map map verdict','beliefs measure plan plan'],
    md:{cols:'1fr 1fr', areas:['problem problem','map map','verdict verdict','beliefs beliefs','measure measure','plan plan']},
    slots:[['problem','problem'],['map','quadrant'],['verdict','decision'],['beliefs','assumptions'],['measure','confirm'],['plan','timeline']]});
  tpl('migration', {name:'Migration plan', for:'Moving from A to B safely: the decision is mostly the sequence, the gates and the rollback.',
    cols:'1fr 1fr 1fr 1fr', areas:['problem plan plan plan','risks risks verdict verdict','risks risks measure costs'],
    md:{cols:'1fr 1fr', areas:['problem problem','plan plan','verdict verdict','risks risks','measure costs']},
    slots:[['problem','problem'],['plan','timeline'],['verdict','decision'],['risks','risks'],['measure','confirm'],['costs','costs']]});
  tpl('process-change', {name:'Process or org change', for:'Changing how people work. Before/after facts, who carries the change, and what would make you roll it back.',
    cols:'1fr 1.2fr 1.2fr 1fr', areas:['problem facts facts people','verdict verdict beliefs beliefs','gains costs measure measure'],
    md:{cols:'1fr 1fr', areas:['problem problem','facts facts','people people','verdict verdict','beliefs beliefs','gains costs','measure measure']},
    slots:[['problem','problem'],['facts','compare'],['people','people'],['verdict','decision'],['beliefs','assumptions'],['gains','gains'],['costs','costs'],['measure','confirm']]});

  /* ───────── selection guide ───────── */
  const GUIDE = [
    {evidence:'judgements', if:'You are judging options against named criteria and can defend a ++ to −− rating', use:'matrix', instead:'Inventing numbers to fill a scoring sheet'},
    {evidence:'facts', if:'The differences are facts in words: licence, residency, who owns it, how it works today versus tomorrow', use:'compare', instead:'Forcing text facts into scores'},
    {evidence:'numbers', if:'One to four measurements decide it: price, latency, setup time', use:'bars', instead:'Pie charts and gauges'},
    {evidence:'time', if:'A quantity changes over time per option: cumulative cost, adoption, load', use:'line', instead:'A single “year one” number that hides the crossover'},
    {evidence:'candidates', if:'Many candidates traded off on two dimensions', use:'quadrant', instead:'A long ranked list with no reasoning'},
    {evidence:'risks', if:'Things can go wrong in ways you can name and mitigate', use:'risks', instead:'A paragraph of worries'},
    {evidence:'sequence', if:'The decision is mostly an order of steps with go/no-go points', use:'timeline', instead:'A Gantt chart'},
    {evidence:'beliefs', if:'It rests on beliefs that could turn out wrong', use:'assumptions', instead:'Silent assumptions nobody revisits'}
  ];
  const KINDS = {'tech-choice':'Pick a technology or approach', 'vendor-select':'Pick a vendor or tool', 'build-vs-buy':'Build, buy or adopt', 'product-bet':'Choose which bet to fund', 'migration':'Move from A to B', 'process-change':'Change how people work'};
  function recommend({kind, evidence = []} = {}){
    const t = T[kind] || T['tech-choice'];
    const used = new Set(t.slots.map(s => s[1]));
    const wanted = GUIDE.filter(g => evidence.includes(g.evidence)).map(g => g.use).filter(c => !used.has(c));
    const swaps = {}, reasons = [];
    const free = s => !Object.prototype.hasOwnProperty.call(swaps, s[0]);
    wanted.forEach(c => {
      const fam = C[c].family;
      // replace a same-family slot whose component has no matching evidence
      const target = t.slots.find(s => free(s) && !C[s[1]].core && C[s[1]].family === fam && !evidence.includes(GUIDE.find(g => g.use === s[1])?.evidence));
      if(target){ swaps[target[0]] = c; reasons.push(`Swap ${C[target[1]].name} for ${C[c].name}: ${GUIDE.find(g => g.use === c).if.toLowerCase()}.`); }
      else reasons.push(`Consider adding ${C[c].name}: no free ${fam} slot in this template, so it would replace something you have evidence for.`);
    });
    return {template: t.id, swaps, reasons};
  }

  /* ───────── compose: let the data choose the compartments ─────────
     Starts from the template for the decision's kind, fills empty slots with a same-family component that has
     data, and appends full-width rows for evidence the template had no slot for. `lead` puts one component on
     top (a picker, say); `skip` keeps components out (because the page shows them elsewhere). */
  const EVIDENCE_OF = {matrix:'judgements', compare:'facts', bars:'numbers', line:'time', quadrant:'candidates', risks:'risks', timeline:'sequence', assumptions:'beliefs'};
  const FAMILY_ORDER = ['evidence', 'plan', 'effects', 'context'];
  function compose(d, {kind, lead, skip = [], maxExtra = 4, extras, hideEmpty = false} = {}){
    const t = T[kind] || T['tech-choice'];
    const has = id => !!C[id] && !skip.includes(id) && C[id].needs(d);
    const evidence = Object.keys(EVIDENCE_OF).filter(has).map(id => EVIDENCE_OF[id]);
    const placed = new Set(lead ? [lead] : []), swaps = {}, reasons = [], drop = [];
    t.slots.forEach(([, cid]) => { if(has(cid)) placed.add(cid); });
    t.slots.forEach(([area, cid]) => {
      if(has(cid)) return;
      const alt = Object.values(C).find(c => c.family === C[cid].family && !c.shelf && !placed.has(c.id) && has(c.id));
      if(alt){ swaps[area] = alt.id; placed.add(alt.id); reasons.push(`${alt.name} sits where ${C[cid].name} would: ${skip.includes(cid) ? 'that one is shown elsewhere on the page' : 'there is nothing for it yet'}.`); }
      else if(skip.includes(cid)) drop.push(area);
    });
    const shown = id => placed.has(id);
    // gains + costs say the same as the consequences ledger: keep the pair whenever either is available
    const redundant = id => (id === 'flip' && shown('decision')) || (id === 'consequences' && (shown('gains') || shown('costs') || has('gains') || has('costs'))) || ((id === 'gains' || id === 'costs') && shown('consequences'));
    const extra = Object.values(C).filter(c => !c.core && !c.shelf && has(c.id) && !placed.has(c.id) && !redundant(c.id) && (!extras || extras.includes(c.id)))
      .sort((a, b) => FAMILY_ORDER.indexOf(a.family) - FAMILY_ORDER.indexOf(b.family)).slice(0, maxExtra);
    extra.forEach(c => { const g = GUIDE.find(x => x.use === c.id); reasons.push(`Added ${c.name}${g ? ': ' + g.if.charAt(0).toLowerCase() + g.if.slice(1) : ''}.`); });
    const n = t.cols.split(' ').length, m = t.md.cols.split(' ').length;
    const row = (a, k) => Array(k).fill(a).join(' ');
    const keep = r => !r.split(' ').every(a => drop.includes(a));
    const ex = extra.map((c, i) => ['x' + (i + 1), c.id]);
    const template = {id: t.id + '+composed', name: t.name, for: t.for, cols: t.cols,
      areas: [...(lead ? [row('lead', n)] : []), ...t.areas.filter(keep), ...ex.map(([a]) => row(a, n))],
      md: {cols: t.md.cols, areas: [...(lead ? [row('lead', m)] : []), ...t.md.areas.filter(keep), ...ex.map(([a]) => row(a, m))]},
      slots: [...(lead ? [['lead', lead]] : []), ...t.slots.filter(([a]) => !drop.includes(a)).map(([a, c]) => [a, swaps[a] || c]), ...ex]};
    const gone = template.slots.filter(([, c]) => !C[c].needs(d)).map(([a]) => a);
    const empty = template.slots.filter(([a]) => gone.includes(a)).map(([, c]) => C[c].name);
    if(hideEmpty && gone.length){
      // an empty compartment hands its cells to a neighbour in the same row; a row with nothing left goes
      const close = rows => rows.map(r => { const cells = r.split(' '), live = cells.filter(a => !gone.includes(a));
        return live.length ? cells.map((a, i) => gone.includes(a) ? (cells.slice(0, i).reverse().find(x => !gone.includes(x)) || live[0]) : a).join(' ') : null; }).filter(Boolean);
      template.areas = close(template.areas); template.md.areas = close(template.md.areas);
      template.slots = template.slots.filter(([a]) => !gone.includes(a));
    }
    return {kind: t.id, template, evidence, swaps, extra: extra.map(c => c.id), empty, hidden: hideEmpty ? empty : [], reasons};
  }

  /* ───────── devil's advocate ───────── */
  const PERSONAS = [
    {id:'skeptic', name:'The devil’s advocate', lens:'Argue the strongest case against the chosen option, whatever it is.'},
    {id:'cfo', name:'The skeptical CFO', lens:'Money: total cost over three years, cheaper alternatives, spend that grows with usage, what happens at renewal.'},
    {id:'oncall', name:'The on-call engineer at 3 a.m.', lens:'Operability: failure modes, alerting, rollback, what breaks under load, who gets paged.'},
    {id:'maintainer', name:'Whoever inherits this in two years', lens:'Complexity, documentation, lock-in, hiring for the skills, how hard it is to undo.'},
    {id:'security', name:'The security reviewer', lens:'Data flows, access, third parties, compliance, blast radius of a breach.'},
    {id:'customer', name:'The customer', lens:'Whether anything improves for users, what they will notice, what could annoy them.'},
    {id:'rival', name:'Your sharpest competitor', lens:'Speed and opportunity cost: what you are not doing while you do this.'}
  ];
  const TYPES = {missing_option:'Missing option', hidden_cost:'Unlisted cost', weak_evidence:'Weak evidence', missing_criterion:'Missing criterion', risk:'Risk', question:'Open question'};
  function advocatePrompt(d, personaId = 'skeptic'){
    const p = PERSONAS.find(x => x.id === personaId) || PERSONAS[0];
    const lines = [];
    lines.push(`Decision: ${d.title || ''}`);
    if(d.context) lines.push('Context: ' + arr(d.context).join(' '));
    if(d.question) lines.push('Question: ' + d.question);
    lines.push('Options: ' + (d.options || []).map(o => o.name + (o.id === d.chosen ? ' (CHOSEN)' : '') + (o.desc ? ` — ${o.desc}` : '')).join('; '));
    if(d.because) lines.push('Stated reason: ' + d.because);
    if((d.criteria || []).length) lines.push('Criteria and ratings (−2…+2, weight 0–3):\n' + d.criteria.map(c => `- ${c.name} (weight ${c.weight ?? 1}): ` + (d.options || []).map(o => `${o.name} ${sym(d.ratings?.[c.id]?.[o.id]) || 'unrated'}`).join(', ')).join('\n'));
    (d.attributes || []).forEach(a => lines.push(`${a.name}: ` + (d.options || []).map(o => `${o.name} = ${a.values?.[o.id] ?? '—'}`).join('; ')));
    (d.metrics || []).forEach(m => lines.push(`${m.name} (${m.unit || ''}, ${m.better || ''} is better): ` + Object.entries(m.values).map(([k, v]) => `${optName(d, k)} ${v}`).join(', ')));
    if(d.series) lines.push(`${d.series.name} over ${d.series.x.join(', ')}: ` + Object.entries(d.series.values).map(([k, v]) => `${optName(d, k)} [${v.join(', ')}]`).join('; '));
    if(d.quadrant) lines.push(`Candidates on ${d.quadrant.x.name} (x) and ${d.quadrant.y.name} (y): ` + d.quadrant.items.map(i => `${i.name} (${i.x}, ${i.y})`).join('; '));
    if((d.risks || []).length) lines.push('Known risks: ' + d.risks.map(r => `${r.text} [L${r.likelihood} I${r.impact}]`).join('; '));
    if((d.assumptions || []).length) lines.push('Assumptions: ' + d.assumptions.map(a => `${a.text} (kill if: ${a.killIf || 'not stated'})`).join('; '));
    if((d.timeline || []).length) lines.push('Plan: ' + d.timeline.map(t => `${t.when}: ${t.what}${t.gate ? ` [gate: ${t.gate}]` : ''}`).join('; '));
    ['good','bad','neutral'].forEach(k => { if((d.consequences?.[k] || []).length) lines.push(`Consequences (${k}): ` + d.consequences[k].join('; ')); });
    if(arr(d.confirmation).length) lines.push('Success measures: ' + arr(d.confirmation).map(c => typeof c === 'string' ? c : `${c.metric} ${c.target} by ${c.by}`).join('; '));
    return `You are reviewing a team's decision record in the role of ${p.name}. Your lens: ${p.lens}
Argue from that lens only. Be specific to this decision, fair, and concrete: name numbers, options and failure modes from the record. No generic advice.
Reply with only JSON in this shape:
{"verdict":"one or two sentences, in your persona's voice, on how well the record supports the choice","strength":"strong|mixed|weak","challenges":[{"type":"missing_option|hidden_cost|weak_evidence|missing_criterion|risk|question","title":"short, under 14 words","why":"under 30 words"}]}
Give 3 to 5 challenges, most important first.

The record:
${lines.join('\n')}`;
  }
  function renderNotes(r, persona){
    if(!r) return '';
    const p = PERSONAS.find(x => x.id === (persona || r.persona));
    return `<div class="bk-flip-top">${p ? `<span class="bk-label">${esc(p.name)}</span>` : ''}<span class="bk-verdict ${esc(r.strength || 'mixed')}">${esc(r.strength || 'mixed')} case</span></div>${r.verdict ? `<p>${esc(r.verdict)}</p>` : ''}
      <div class="bk-notes">${(r.challenges || []).map(c => `<article class="bk-note"><span class="k">${esc(TYPES[c.type] || c.type || 'Challenge')}</span><b>${esc(c.title)}</b>${c.why ? `<p>${esc(c.why)}</p>` : ''}</article>`).join('')}</div>`;
  }

  /* ───────── rendering ───────── */
  function compartment(area, n, comp, d, slotQ){
    const ok = comp.needs(d);
    const cls = ['bk-cmp', comp.hero ? 'is-hero' : '', comp.shelf ? 'is-shelf' : '', ok ? '' : 'is-empty'].filter(Boolean).join(' ');
    let body;
    try { body = ok ? comp.render(d, {}) : prompt(comp.empty); } catch(e){ body = prompt('This compartment could not be drawn from the data given.'); }
    return `<section class="${cls}" style="grid-area:${area}" data-slot="${area}" data-component="${comp.id}"><header class="bk-head">${n ? `<span class="bk-num" aria-hidden="true">${n}</span>` : ''}<div><h2 class="bk-q">${esc(slotQ || comp.question)}</h2><span class="bk-src">${esc(comp.src)}</span></div></header>${body}</section>`;
  }
  function toHTML(templateOrId, d, o = {}){
    const t = typeof templateOrId === 'string' ? T[templateOrId] : templateOrId;
    if(!t) throw new Error('Unknown template: ' + templateOrId);
    const q = a => a.map(r => `"${r}"`).join(' ');
    const style = `--bk-cols:${t.cols};--bk-areas:${q(t.areas)};--bk-cols-md:${t.md.cols};--bk-areas-md:${q(t.md.areas)}`;
    const slots = t.slots.map(([area, cid], i) => {
      const id = (o.swap && o.swap[area]) || cid, comp = C[id];
      if(!comp) throw new Error('Unknown component: ' + id);
      return compartment(area, o.numbers === false ? 0 : i + 1, comp, d, o.questions?.[area]);
    }).join('');
    return `<div class="bk-wrap"><div class="bk-box" style='${style}'>${slots}</div></div>`;
  }
  function fit(el, d){
    el.querySelectorAll('[data-bk-line]').forEach(box => {
      let last = 0;
      const draw = () => { const w = box.clientWidth; if(w > 0 && Math.abs(w - last) > 2){ last = w; box.innerHTML = lineSVG(d, w); } };
      draw();
      if(typeof ResizeObserver === 'function') new ResizeObserver(draw).observe(box);
    });
    return el;
  }
  function render(el, templateOrId, d, o){ el.innerHTML = toHTML(templateOrId, d, o); return fit(el, d); }
  function renderComponent(el, id, d){
    const comp = C[id]; if(!comp) throw new Error('Unknown component: ' + id);
    el.innerHTML = `<div class="bk-wrap"><div class="bk-box" style="--bk-cols:1fr;--bk-areas:'one';--bk-cols-md:1fr;--bk-areas-md:'one'">${compartment('one', 0, comp, d)}</div></div>`;
    return fit(el, d);
  }

  const BentoKit = {
    version: '0.1.0',
    components: C, templates: T, guide: GUIDE, kinds: KINDS,
    render, renderComponent, toHTML, recommend, compose,
    analyze: {scores, robustness, crossover},
    advocate: {personas: PERSONAS, types: TYPES, prompt: advocatePrompt, render: renderNotes},
    util: {esc, md}
  };
  if(typeof module === 'object' && module.exports) module.exports = BentoKit;
  root.BentoKit = BentoKit;
})(typeof globalThis !== 'undefined' ? globalThis : this);
