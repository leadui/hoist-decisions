#!/usr/bin/env python3
"""Page-shape tests: the session view is decision-moments native.

Asserts over the exact bytes of site/index.html that the moments
foundation is present (tabs, tiers, journeys, micro-bars, growth,
hyper-dive modal, escape row) and that retired blocks (agent-lean
display, per-decision Q&A) are fully gone — markup, styles, handlers.

Run:  python3 test/test_page.py
Standard library only.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

FAILURES = []
PAGE = Path(__file__).resolve().parent.parent / "site" / "index.html"
SRC = PAGE.read_text()


def check(name, cond, detail=""):
    print(("PASS " if cond else "FAIL ") + name)
    if not cond:
        FAILURES.append(name + (" — " + detail if detail else ""))


PRESENT = [
    # tiered moments engine wiring
    ("tabs switch decisions", 'data-etab='),
    ("tiers switch depth", 'data-etier='),
    ("rows expand options", 'data-epick='),
    ("hyper-dive opens", 'data-hyper='),
    ("glance tier labeled", "'Glance'"),
    ("compare tier labeled", "'Compare'"),
    ("deep tier labeled", "'Deep dive'"),
    # moments components
    ("journey steps styled", 'jstep'),
    ("journey steps numbered", 'counter(js)'),
    ("micro-bars styled", 'micro-track'),
    ("growth chart styled", 'growthHtml'),
    # modal opens and closes three ways
    ("modal veil styled", 'm-veil'),
    ("modal sheet rendered", 'm-sheet'),
    ("modal close helper", 'closeEmodal'),
    ("modal closes on backdrop", "contains('m-veil')"),
    ("modal closes on escape", "'Escape'"),
    # escape row unblocks the agent
    ("delegate escape", 'data-s="delegate"'),
    ("park escape", 'data-s="park"'),
    ("abandon escape", 'data-s="abandon"'),
]

ABSENT = [
    # retired: agent-lean display
    ("no lean box styles", 'lean-box'),
    ("no lean strip builder", 'leanStrip'),
    ("no lean wording", "agent's lean"),
    ("no lean confirm handler", 'dataset.lok'),
    ("no lean challenge handler", 'dataset.lch'),
    # retired: per-decision Q&A
    ("no Q&A block styles", 'm-qa'),
    ("no Q&A pick styles", 'm-pick'),
    ("no assume-block builder", 'assume('),
    ("no per-decision answer handler", 'data-oa='),
    ("no assume confirm handler", 'data-ok='),
    ("no assume change handler", 'data-chg='),
    ("no assume answer handler", 'data-setans='),
]


def test_page_shape():
    for name, needle in PRESENT:
        check("page has " + name, needle in SRC, repr(needle))
    for name, needle in ABSENT:
        check("page: " + name, needle not in SRC, repr(needle))


if __name__ == "__main__":
    test_page_shape()
    print(f"\n{len(FAILURES)} failure(s)")
    for f in FAILURES:
        print("FAILED:", f)
    sys.exit(1 if FAILURES else 0)
