"""Static checks for the Bento MADR showcase page (stdlib only, no server).

Run: python3 test/test_showcase.py — 0 means every check passed.
Locks: the page loads the real kit, registers the record template,
renders live canvases, and the landing page links to it.
"""
import sys
from pathlib import Path

FAILURES = []
ROOT = Path(__file__).resolve().parent.parent
PAGE = ROOT / "site" / "bentomadr.html"
SRC = PAGE.read_text()
LANDING = (ROOT / "site" / "landing.html").read_text()


def check(name, cond, detail=""):
    print(("PASS " if cond else "FAIL ") + name)
    if not cond:
        FAILURES.append(name + (" — " + detail if detail else ""))


PRESENT = [
    ("kit css", "bento-kit.css"),
    ("kit js", "bento-kit.js"),
    ("record template", "madr-record"),
    ("completeness strip", "completeness"),
    ("builder", "builder"),
    ("component index", "BentoKit.components"),
    ("live render", "BentoKit.render"),
    ("theme toggle", "theme-toggle"),
]
ABSENT = [
    ("no invented scores in copy", "99.9%"),
    ("no external images", "unsplash"),
]


def test_showcase_shape():
    for name, needle in PRESENT:
        check("showcase has " + name, needle in SRC, repr(needle))
    for name, needle in ABSENT:
        check("showcase: " + name, needle not in SRC, repr(needle))
    check("landing links to showcase", "bentomadr.html" in LANDING)


if __name__ == "__main__":
    test_showcase_shape()
    print(f"\n{len(FAILURES)} failure(s)")
    for f in FAILURES:
        print("FAILED:", f)
    sys.exit(1 if FAILURES else 0)