#!/usr/bin/env python3
"""Page-shape tests: site/index.html is the decision-moments engine.

Asserts over the exact bytes that the moments foundation is present
(tabs, tiers, journeys, micro-bars, growth chart, veil + sheet modal
with three close paths, escape row, review gate) wired to the Hoist
API, and that retired blocks (lean display, Q&A, voice, old shells)
are fully gone.

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
    # bento canvas experience (kit does the heavy lifting)
    ("bento kit css", "bento-kit.css"),
    ("bento kit js", "bento-kit.js"),
    ("moment canvas", "bk-moment"),
    ("moment template", '"moment"'),
    ("madr record canvas", "madr-record"),
    ("record canvas data", "recordData"),
    # decision-moment flow
    ("moment box", "Decision moment"),
    ("two paths", "Walk through it"),
    ("tabs switch questions", 'data-action="q"'),
    ("quick picks commit", 'data-action="quickpick"'),
    ("moment names its question", "Earlier you chose"),
    ("mobile rules", "@media (max-width: 560px)"),
    ("answered pills turn green", "qtab.done"),
    ("typing indicator", 'class="typing"'),
    # escape row + review gate
    ("custom option escape", 'data-v="custom"'),
    ("back-to-chat escape", 'data-v="chat"'),
    ("skip escape", 'data-v="skip"'),
    ("delegate escape", "Let the agent decide"),
    ("confirm + review + seal", 'data-action="file"'),
    ("commit CTA", "Commit &amp; send back to chat"),
    ("review and commit tab", "Review &amp; commit"),
    ("theme toggle", "theme-toggle"),
    # Hoist wiring underneath
    ("loads live state", "/api/state"),
    ("replays sample offline", "sample.json"),
    ("files session records", "/api/session/decisions/"),
    ("abandons to chat", "/api/session/abandon"),
    ("files single decisions", "/api/decisions/"),
    ("Muse Spark progress", "Muse Spark"),
    ("record fields chips", "rec-fields"),
    ("raw toggle", "View raw"),
    ("sample badge", "Sample data"),
    ("conflict block", "Do not add"),
    ("commit verb", "Commit choice"),
    ("cards pick options", "optionCardsWire"),
    ("rich option cards", "optioncards"),
]
ABSENT = [
    # retired: agent-lean display
    ("no lean box", "lean-box"),
    ("no lean strip builder", "leanStrip"),
    ("no lean wording", "agent's lean"),
    # retired: per-decision Q&A
    ("no Q&A blocks", "m-qa"),
    ("no Q&A pills", ".m-pick"),
    ("no assume handlers", "data-setans"),
    # retired: old port inventions
    ("no old tab wiring", "data-etab"),
    ("no old tier wiring", "data-etier"),
    ("no old pick wiring", "data-epick"),
    ("no old modal names", "m-veil"),
    ("no old sheet names", "m-sheet"),
    ("no old modal mount", "emodal"),
    # retired: voice
    ("no speech synthesis", "speechSynthesis"),
    ("no voice scripts", "voiceOpen"),
    ("no listen buttons", "listen-btn"),
    ("no hyper speech", "hyperspeak"),
    # retired: old house shell
    ("no house font", "Geist"),
    ("no old step shell", 'class="step'),
    # retired: tiers
    ("no depth wiring", 'data-action="depth"'),
    ("no glance tier", '"Glance"'),
    ("no compare tier", '"Compare"'),
    ("no deep tier", '"Deep dive"'),
    ("no sheet tiers", "sheet-tiers"),
    # retired: old language
    ("no interruption box", "The interruption"),
    ("no file CTA", "File records"),
    ("no seal CTA", "Seal the moments"),
    ("no seal wording", "seal"),
    ("no confirm verb", "Confirm choice"),
    ("no choose verb", "Choose "),
    ("no hyper dive", 'data-action="hyper"'),
    ("no deep pull", "/deep"),
    ("no hyper modal", "hyperHtml"),
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
