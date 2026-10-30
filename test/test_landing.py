#!/usr/bin/env python3
"""Landing-page tests: site/landing.html is the Hoist pitch.

Asserts over the exact bytes that the story is present (hero, pause → decide →
record, ask vs autopilot, Bento MADR, install), that links and anchors resolve,
and that no banned cheap-default styling crept in.

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
    """The story: your idea, the questions come, hard to undo, okay to stop, answers before you ask, one live canvas, records outlive the agent."""
    for name, needle in [("headline", "You've got a"), ("the belief", "It's okay to stop"), ("option one, two, three", "Option one. Option two."), ("terminal moment", 'id="term"'), ("one live canvas", 'id="live"'),
                         ("kit composes the canvas", "K.compose("), ("Hoist extensions", "hoist-bento.js"),
                         ("pinned kit", "vendor/bento-madr/bento-kit.js"), ("ask vs autopilot", "hoist.py mode autopilot"),
                         ("four beliefs", "It's not okay to say yes blindly."), ("answers before you ask", 'id="asks"'), ("idea switcher on the canvas", 'id="ideas"'), ("records outlive the agent", "outlive"), ("Bento MADR link", "github.com/leadui/bento-madr"),
                         ("Muse Spark credit", "Muse Spark"), ("reduced motion", "prefers-reduced-motion"), ("mobile menu", 'id="burger"')]:
        check("v2 has " + name, needle in V2, repr(needle))
    check("v2 has exactly one live canvas", V2.count('id="live"') == 1)
    site = Path(__file__).resolve().parent.parent / "site"
    for img in set(re.findall(r'src="(images/[^"]+)"', V2)):
        check("v2 image exists: " + img, (site / img).exists())
    check("v2 uses the brand renders", "images/door.webp" in V2 and "images/yes.webp" in V2)
    check("v2 icons are true cut-outs in front, not blended", "mix-blend-mode:multiply" not in V2 and ".obj{filter:drop-shadow" in V2)
    check("v2 hero uses the desk photo as a backdrop", 'class="hero-bg"' in V2 and "images/desk.webp" in V2)
    check("v2 hero has a video slot", 'data-video=' in V2 and "createElement(\"video\")" in V2)
    check("v2 yes-person is a full-bleed band", 'class="band"' in V2 and "images/yes.webp" in V2)
    check("v2 has no framed photos left", 'class="bezel photo' not in V2)
    check("v2 rotating phrases share one slot (no reflow)", ".rot > span{grid-area:1 / 1" in V2)
    check("v2 section numbers sit top-left, clear of icons", ".sec-num{position:absolute;top:22px;left:-10px" in V2)
    check("v2 icons sit in the layout, not offset", "icon3d" not in V2 and V2.count('class="ic obj') == 6)
    check("v2 terminal lives in the Pause step", 'class="term-box"' in V2 and "hero-term" not in V2)
    check("v2 link preview image", 'og:image' in V2 and (site / "images" / "og.jpg").exists())
    rots = re.findall(r'<span class="rot[^"]*"[^>]*>(.*?)</span></(?:p|h2)>', V2)
    check("v2 rotating lines: the ideas in the hero, the question at install", len(rots) == 2 and "Cake pre-orders." in rots[0], str(len(rots)))
    check("v2 rotation names no decision kind Hoist doesn't guard", all("database" not in r for r in rots))
    check("v2 kind tabs disclose the same decision", "Same decision, as a" in V2 and "the options stay the same" in V2)
    check("v2 demo links open the Start terminal", 'href="index.html#/"' in V2 and "index.html#/session" not in V2)
    check("v2 has no 3D scene", "three.module" not in V2 and "importmap" not in V2 and "GLTFLoader" not in V2)
    for f in ("Inter", "Roboto"):
        check("v2 avoids " + f, '"' + f + '"' not in V2)
    ids = set(re.findall(r'id="([^"]+)"', V2))
    for href in set(re.findall(r'href="#([^"]+)"', V2)):
        check("v2 anchor #" + href + " exists", href in ids)


if __name__ == "__main__":
    test_no_banned_styles()
    test_landing_anchors()
    test_landing_v2()
    print(f"\n{len(FAILURES)} failure(s)")
    for f in FAILURES:
        print("FAILED:", f)
    sys.exit(1 if FAILURES else 0)
