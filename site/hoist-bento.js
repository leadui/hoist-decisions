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

  /* One critic, written for this decision: not a menu of job titles that may not exist in this project. */
  BentoKit.advocate.personas.push({ id: "most-affected", name: "The person this affects most",
    lens: "First work out who, in this project, this choice would hurt most: a customer, the owner, a helper, whoever is real here, never a generic job title. Argue as them, from what they would actually live through." });

  /* The kit's empty-state text is guidance for whoever writes a record ("List the phases and…").
     Visitors read Hoist's canvases, so an empty compartment just says nothing was recorded; the hatching shows the gap. */
  var EMPTY = "Nothing recorded here for this decision.";

  /* The kit stamps the chosen option "Chosen". In Hoist the pick stays open until you commit, so it reads "Selected". */
  var render = BentoKit.render;
  BentoKit.render = function (el) {
    var out = render.apply(BentoKit, arguments);
    if (el && el.querySelectorAll) {
      el.querySelectorAll(".bk-cmp.is-empty > .bk-prompt").forEach(function (p) { p.textContent = EMPTY; });
      /* the BECAUSE badge is followed by a real space, so copied or read-aloud text isn't "BecauseInstall" */
      el.querySelectorAll(".bk-because > b").forEach(function (b) {
        var n = b.nextSibling;
        if (n && n.nodeType === 3 && /^\s/.test(n.nodeValue)) return;
        b.parentNode.insertBefore(document.createTextNode(" "), n);
        b.style.marginRight = "4px";
      });
      /* "Decided · consulted · informed" names only the columns this record actually has */
      el.querySelectorAll('[data-component="people"]').forEach(function (c) {
        var src = c.querySelector(".bk-src"), cols = [];
        c.querySelectorAll("dt").forEach(function (dt) { cols.push({ "Decided by": "decided", "Carries it out": "carries it out", "Consulted": "consulted", "Informed": "informed" }[dt.textContent] || dt.textContent.toLowerCase()); });
        if (src && cols.length) src.textContent = cols.join(" · ");
      });
      el.querySelectorAll(".bk-stamp").forEach(function (s) { if (s.textContent === "Chosen") s.textContent = "Selected"; });
      el.querySelectorAll(".bk-key").forEach(function (k) { if (k.lastChild && k.lastChild.nodeValue === "Chosen") k.lastChild.nodeValue = "Selected"; });
    }
    return out;
  };
})();
