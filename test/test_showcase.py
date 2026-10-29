"""Static checks for how Hoist uses Bento MADR (stdlib only, no server).

Run: python3 test/test_showcase.py — 0 means every check passed.
Locks: Bento MADR lives in its own repo; Hoist loads a pinned copy from
site/vendor/bento-madr, adds its own compartments in site/hoist-bento.js,
and the old showcase URL forwards to the Bento MADR catalog.
"""
import sys
from pathlib import Path

FAILURES = []
ROOT = Path(__file__).resolve().parent.parent
VENDOR = ROOT / "site" / "vendor" / "bento-madr"


def check(name, cond, detail=""):
    print(("PASS " if cond else "FAIL ") + name)
    if not cond:
        FAILURES.append(name + (" — " + detail if detail else ""))


def test_bento_split():
    for f in ("bento-kit.js", "bento-kit.css", "LICENSE", "VERSION"):
        check("pinned kit has " + f, (VENDOR / f).exists())
    version = (VENDOR / "VERSION").read_text() if (VENDOR / "VERSION").exists() else ""
    kit = (VENDOR / "bento-kit.js").read_text() if (VENDOR / "bento-kit.js").exists() else ""
    check("VERSION names the tag", "Bento MADR v" in version)
    check("kit version matches VERSION", "version: '" + version.split()[2].lstrip("v") + "'" in kit if version else False)
    check("kit has define()", "function define(" in kit)
    check("kit ships madr-record", "tpl('madr-record'" in kit)
    check("no kit copy left in the repo root", not (ROOT / "bentomadr").exists())
    check("no stray kit copy in site/", not (ROOT / "site" / "bento-kit.js").exists())
    ext = (ROOT / "site" / "hoist-bento.js").read_text()
    check("Hoist extends the kit with define", "BentoKit.define(" in ext)
    check("update script pins a tag", "raw.githubusercontent.com/leadui/bento-madr" in (ROOT / "scripts" / "update-bento.sh").read_text())
    for page in ("index.html", "landing.html"):
        src = (ROOT / "site" / page).read_text()
        check(page + " loads the pinned kit", "vendor/bento-madr/bento-kit.js" in src)
        check(page + " loads Hoist's extensions", "hoist-bento.js" in src)
        check(page + " does not redefine madr-record", 'templates["madr-record"] =' not in src)
    check("empty compartments say nothing was recorded, not what to write", "Nothing recorded here for this decision." in ext and ".bk-cmp.is-empty > .bk-prompt" in ext)
    check("people subtitle lists only filled columns", '[data-component="people"]' in ext)
    check("Because badge is followed by a real space", "BecauseInstall" in ext and "createTextNode(\" \")" in ext)
    import json as _json
    ses = _json.loads((ROOT / "site" / "sample.json").read_text())["sample_session"]
    for did, dr in ses["drafts"].items():
        for o in dr["options"]:
            if not o.get("ruled_out"):
                check("critic baked for " + did + "/" + o["id"], bool((dr.get("advocate") or {}).get(o["id"])))
    check("old showcase URL forwards", "leadui.github.io/bento-madr" in (ROOT / "site" / "bentomadr.html").read_text())


if __name__ == "__main__":
    test_bento_split()
    print(f"\n{len(FAILURES)} failure(s)")
    for f in FAILURES:
        print("FAILED:", f)
    sys.exit(1 if FAILURES else 0)
