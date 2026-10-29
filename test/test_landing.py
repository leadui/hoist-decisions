#!/usr/bin/env python3
"""Landing-page tests: site/landing.html is the Hoist pitch (v2); site/landing-v1.html is the earlier one, kept for reference.

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
PAGE = Path(__file__).resolve().parent.parent / "site" / "landing-v1.html"
SRC = PAGE.read_text()


def check(name, cond, detail=""):
    print(("PASS " if cond else "FAIL ") + name)
    if not cond:
        FAILURES.append(name + (" — " + detail if detail else ""))


PRESENT = [
    ("title", "<title>Hoist — every decision moment, together</title>"),
    ("hackathon eyebrow", "Meta Global AI Developer Hackathon"),
    ("hero headline", "It's okay to stop and"),
    ("premises", "IT'S NOT OKAY TO SAY YES TO EVERYTHING"),
    ("autopilot install line", "hoist.py mode autopilot"),
    ("hero canvas", 'id="scene"'),
    ("hero headline words", "['Decide', 'With', 'AI']"),
    ("hero sr headline", "Decide With AI</h1>"),
    ("section numerals", 'sec-num" aria-hidden="true">05<'),
    ("ui examples", "js-mtitle"),
    ("demo styling", ".demo .opt[aria-pressed"),
    ("madr viewer", 'data-madr="2"'),
    ("muse terminal", "hoist.py wait"),
    ("madr switch", "madrShow"),
    ("madr icon", "icons/clipboard.webp"),
    ("https clone", "https://github.com/leadui/hoist-decisions.git"),
    ("hero dpr cap", "devicePixelRatio || 1, 1.5"),
    ("hero static fallback", "hero-static"),
    ("live canvas render", "renderLive"),
    ("live canvas mount", 'id="bk-live"'),
    ("landing composes its canvas", "BentoKit.compose"),
    ("landing uses the pinned kit", "vendor/bento-madr/bento-kit.js"),
    ("landing links Bento MADR", "leadui.github.io/bento-madr"),
    ("bento section", 'id="bentomadr"'),
    ("bento nav", 'href="#bentomadr"'),
    ("Bento MADR catalog cta", "Open the Bento MADR catalog"),
    ("completeness strips", "Thin record · 2 of 8"),
    ("component chips", "Devil's advocate"),
    ("problem icon", "icons/idea.webp"),
    ("moment icon", "icons/chart.webp"),
    ("install icon", "icons/shield.webp"),
    ("live mocks", "data-mopt"),
    ("cube arrows", 'id="prev"'),
    ("moment numeral", ">01<"),
    ("three.js pinned", "three@0.169.0"),
    ("display font", "Bricolage+Grotesque"),
    ("bento kit css", "bento-kit.css"),
    ("landing record canvas", "madr-record"),
    ("bk board mount", "bk-board"),
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
    ("hand-rolled mock", "mock-edu"),
    ("old pane builder", "rpOptHtml"),
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


V2 = (Path(__file__).resolve().parent.parent / "site" / "landing.html").read_text()


def test_landing_v2():
    """Version 2: one live canvas, pause → decide → record, ask vs autopilot, Bento MADR, install."""
    for name, needle in [("headline", "It's okay to stop and"), ("terminal moment", 'id="term"'), ("one live canvas", 'id="live"'),
                         ("kit composes the canvas", "K.compose("), ("Hoist extensions", "hoist-bento.js"),
                         ("pinned kit", "vendor/bento-madr/bento-kit.js"), ("ask vs autopilot", "hoist.py mode autopilot"),
                         ("four beliefs", "It's not okay to say yes to everything."), ("Bento MADR link", "github.com/leadui/bento-madr"),
                         ("Muse Spark credit", "Muse Spark"), ("reduced motion", "prefers-reduced-motion"), ("mobile menu", 'id="burger"')]:
        check("v2 has " + name, needle in V2, repr(needle))
    check("v2 has exactly one live canvas", V2.count('id="live"') == 1)
    check("v2 demo links open the Start terminal", 'href="index.html#/"' in V2 and "index.html#/session" not in V2)
    check("v2 has no 3D scene", "three.module" not in V2 and "importmap" not in V2 and "GLTFLoader" not in V2)
    for f in ("Inter", "Roboto"):
        check("v2 avoids " + f, '"' + f + '"' not in V2)
    ids = set(re.findall(r'id="([^"]+)"', V2))
    for href in set(re.findall(r'href="#([^"]+)"', V2)):
        check("v2 anchor #" + href + " exists", href in ids)


if __name__ == "__main__":
    test_landing_shape()
    test_no_banned_styles()
    test_landing_anchors()
    test_landing_v2()
    print(f"\n{len(FAILURES)} failure(s)")
    for f in FAILURES:
        print("FAILED:", f)
    sys.exit(1 if FAILURES else 0)
