/* Hoist's extensions to Bento MADR (site/vendor/bento-madr, pinned by scripts/update-bento.sh).
   Hoist never edits the kit: it adds its own compartments with BentoKit.define and words the stamps
   for a decision that is still being made. Load after vendor/bento-madr/bento-kit.js. */
(function () {
  "use strict";
  if (typeof BentoKit === "undefined" || !BentoKit.define) return;
  var md = BentoKit.util.md, esc = BentoKit.util.esc;

  /* What the agent would have done on its own. Shown next to the person's pick, never instead of it. */
  BentoKit.define("agent-lean", {
    family: "verdict", name: "Agent lean", question: "What would the agent pick, and why?", src: "The agent's proposal",
    when: "An AI agent proposed an option before a person decided. Shows the pick, the reason and what it takes for granted.",
    avoid: "Presenting the lean as the decision. The person decides; the lean is one input.",
    shape: "lean: {name, why, assumptions?: string[], flips?: string[]}",
    needs: function (d) { return !!(d.lean && d.lean.name); },
    empty: "Record what the agent would have picked and why.",
    render: function (d) {
      var l = d.lean;
      return '<p class="bk-chosen" style="font-size:20px">' + esc(l.name) + "</p>" +
        (l.why ? '<p class="bk-because"><b>Because</b>' + md(l.why) + "</p>" : "") +
        ((l.flips || []).length ? '<p class="bk-label">Another option wins if</p><ul class="bk-list">' +
          l.flips.map(function (f) { return "<li>" + md(f) + "</li>"; }).join("") + "</ul>" : "");
    }
  });

  /* The kit stamps the chosen option "Chosen". In Hoist the pick stays open until you commit, so it reads "Selected". */
  var render = BentoKit.render;
  BentoKit.render = function (el) {
    var out = render.apply(BentoKit, arguments);
    if (el && el.querySelectorAll) {
      el.querySelectorAll(".bk-stamp").forEach(function (s) { if (s.textContent === "Chosen") s.textContent = "Selected"; });
      el.querySelectorAll(".bk-key").forEach(function (k) { if (k.lastChild && k.lastChild.nodeValue === "Chosen") k.lastChild.nodeValue = "Selected"; });
    }
    return out;
  };
})();
