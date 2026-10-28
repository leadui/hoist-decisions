#!/usr/bin/env python3
"""Landing-page tests: site/landing.html is the full Hoist pitch.

Asserts over the exact bytes that every section is present (hero,
problem, moment flow, records, install, footer), that demo/repo links
point at real targets, and that no banned cheap-default styling
crept in.

Run:  python3 test/test_landing.py
Standard library only.
"""
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

FAILURES = []
PAGE = Path(__file__).resolve().parent.parent / "site" / "landing.html"
SRC = PAGE.read_text()


def check(name, cond, detail=""):
    print(("PASS " if cond else "FAIL ") + name)
    if not cond:
        FAILURES.append(name + (" — " + detail if detail else ""))


PRESENT = [
    ("title", "<title>Hoist — every decision moment, together</title>"),
    ("hackathon eyebrow", "Meta Global AI Developer Hackathon"),
    ("hero headline", "Stop rolling the dice"),
    ("hero canvas", 'id="scene"'),
    ("hero headline words", "['Decide', 'With', 'AI']"),
    ("hero sr headline", "Decide With AI</h1>"),
    ("section numerals", 'sec-num" aria-hidden="true">05<'),
    ("ui examples", "DECISION MOMENT 1 OF 3"),
    ("cube arrows", 'id="prev"'),
    ("moment numeral", ">01<"),
    ("three.js pinned", "three@0.169.0"),
    ("display font", "family=Poppins"),
    ("demo CTA", 'href="index.html#/session"'),
    ("records link", 'href="index.html#/records"'),
    ("repo link", "https://github.com/leadui/hoist-decisions"),
    ("problem section", 'id="problem"'),
    ("moment section", 'id="moment"'),
    ("records section", 'id="records"'),
    ("install section", 'id="install"'),
    ("install command", "hoist.py install"),
    ("serve command", "hoist.py serve"),
    ("madr sample", "## Decision Drivers"),
    ("island nav", 'class="island"'),
    ("burger morph", 'class="burger"'),
    ("staggered menu", 'class="menu"'),
    ("scroll reveals", "IntersectionObserver"),
    ("reduced motion", "prefers-reduced-motion"),
]

ABSENT = [
    ("no banned font Roboto", "Roboto"),
    ("no banned font Arial", "Arial"),
    ("no banned font Helvetica", "Helvetica"),
    ("no banned font Open Sans", "Open Sans"),
    ("no layout animation", "transition:transform .5s var(--ease),top"),
]


def test_landing_shape():
    for name, needle in PRESENT:
        check("landing has " + name, needle in SRC, repr(needle))
    for name, needle in ABSENT:
        check("landing: " + name, needle not in SRC, repr(needle))


def test_no_banned_styles():
    families = " ".join(re.findall(r"font-family:([^;]+)", SRC))
    for bad in ("Inter", "Roboto", "Arial", "Helvetica", "Open Sans"):
        check("no banned font " + bad, bad not in families, families[:160])
    transitions = " ".join(re.findall(r"transition:([^;]+)", SRC))
    check("no linear or ease-in-out motion",
          "linear" not in transitions and "ease-in-out" not in transitions, transitions[:200])


def test_landing_anchors():
    ids = set(re.findall(r'id="([^"]+)"', SRC))
    for href in re.findall(r'href="(#[^"]+)"', SRC):
        check("anchor " + href + " resolves", href[1:] in ids, href)


if __name__ == "__main__":
    test_landing_shape()
    test_no_banned_styles()
    test_landing_anchors()
    print(f"\n{len(FAILURES)} failure(s)")
    for f in FAILURES:
        print("FAILED:", f)
    sys.exit(1 if FAILURES else 0)
