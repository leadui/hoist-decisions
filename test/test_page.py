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
    ("kit composes the moment", "BentoKit.compose"),
    ("demo opens on the Muse terminal", "sampleHomeHtml"),
    ("commit bar shows progress dots", "progressDots()"),
    ("commit bar tags a pick against your answers", "against your answers"),
    ("finish says it's okay to go back to the terminal", "it's okay to return to your terminal now"),
    ("sample records persist across loads", "restoreSample"),
    ("sample records saved on every commit", "saveSample();"),
    ("ids owned by decisions are never reused", "never reuse an id a decision owns"),
    ("interruption replaces only its own record", "only this decision's own earlier record"),
    ("deliberate reset of sample records", 'data-action="reset-sample"'),
    ("chosen option read whole, commas and all", "a record with no option list (a Hoist default) still names its choice by label"),
    ("canvas says when a kind reshapes the same decision", "Same decision, reshaped as a"),
    ("nav is Start and Records", 'id="nav-records"'),
    ("terminal routes to Hoist", 'data-action="intro" data-v="hoist"'),
    ("terminal shows the blind option list", "Option one, option two, option three."),
    ("demo asks what you are building", "What are you building?"),
    ("agent resumes after commit", "resumeTtyHtml"),
    ("options lead the canvas", 'lead: "proscons"'),
    ("pros and cons data", "prosCons"),
    ("kind switch", 'data-action="kind"'),
    ("profile answers become the matrix", "driversOf"),
    ("lean becomes assumptions", "assumptionsOf"),
    ("structured risks", "risksOf"),
    ("critic personas", 'data-action="critic"'),
    ("critic over the API", "/api/advocate"),
    ("zero-options state", "No options on the table yet"),
    ("first-entry mount", 'state.phase === "moment"'),
    ("catalog fail state", "CATFAIL"),
    ("madr record canvas", "madr-record"),
    ("record canvas data", "recordData"),
    # decision-moment flow
    ("moment box", "Decision moment"),
    ("tabs switch questions", 'data-action="q"'),
    ("moment names its question", "You captured"),
    ("captured state stays on the moment", "isCaptured"),
    ("next moves on", "data-action=\"next\""),
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
    ("pinned to the light theme", 'data-theme="light"'),
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
    ("sticky commit bar", "commitbar"),
    ("connected stepper", ".qtab + .qtab::before"),
    ("cards pick options", "optionCardsWire"),
    ("kit option shelf cards", "proscons"),
]
ABSENT = [
    # P0: the interruption must never wipe other records by id prefix
    ("no prefix wipe of records", 'indexOf(dec.id + "-") !== 0'),
    # retired: Session tab and theme toggle in the nav
    ("no Session nav tab", 'id="nav-session"'),
    ("no theme toggle", "theme-toggle"),
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
    ("no fork step", "Walk through it"),
    ("no fork action", 'data-action="path"'),
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
