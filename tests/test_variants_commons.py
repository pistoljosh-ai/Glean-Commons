#!/usr/bin/env python3
"""The whole loop on a scratch commons: share -> adopt -> count -> promote -> everyone gets it."""

import json
import shutil
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
sys.path.insert(0, str(ROOT / "variants"))

import check_variants as C  # noqa: E402
import engine as E  # noqa: E402
import promote_variant as P  # noqa: E402

CELL = "invoice-followup"


def scratch():
    tmp = Path(tempfile.mkdtemp())
    E.copy_tree(ROOT / "cells", tmp / "cells")
    (tmp / "ledger" / "pending").mkdir(parents=True)
    (tmp / "variants" / "shared").mkdir(parents=True)
    return tmp


def test_repo_variants_are_sound():
    errors, _ = C.check_shared()
    assert errors == [] and C.check_adoptions() == [], errors


def test_full_loop():
    tmp = scratch()
    try:
        # Ana makes a version and shares it
        ana = E.Variants(tmp / "ana", cells_root=tmp / "cells", shared_root=tmp / "variants" / "shared")
        ana.start(CELL, "call the last notice a reminder, not a final notice")
        ana.edit(CELL, "followup.py", find='"Final notice: invoice {invoice}"', replace='"Last reminder: invoice {invoice}"')
        ana.save(CELL, "last reminder", author="Ana Example")
        ana.share(cell=CELL, login="ana")
        vid = ana.saved(CELL)[0]["id"]
        dest = tmp / "variants" / "shared" / CELL / f"{vid}.json"
        dest.parent.mkdir(parents=True)
        shutil.copy(tmp / "ana" / "outbox" / f"{vid}.json", dest)
        errors, notes = C.check_shared(tmp)
        assert errors == [] and "tests pass" in notes[0], (errors, notes)

        # Ben adopts it
        ben = E.Variants(tmp / "ben", cells_root=tmp / "cells", shared_root=tmp / "variants" / "shared")
        ben.adopt(vid, confirm=True)
        assert "Last reminder" in (ben.effective_dir(CELL) / "followup.py").read_text()

        # one voice per account
        assert C.one_voice([("A", f"variants/adoptions/{vid}/ben.json")], "Ben") == []
        assert len(C.one_voice([("A", f"variants/adoptions/{vid}/ben.json"), ("A", f"variants/adoptions/{vid}/sock1.json")], "ben")) == 1

        # not enough adopters: no promotion
        ad = tmp / "variants" / "adoptions" / vid
        ad.mkdir(parents=True)
        (ad / "ana.json").write_text("{}")  # the author's own does not count
        (ad / "ben.json").write_text("{}")
        try:
            P.prepare(vid, "Maintainer", root=tmp)
            raise AssertionError("should refuse below the threshold")
        except E.Problem as p:
            assert "1 of 30" in str(p)
        assert C.check_adoptions(tmp) == []

        # thirty independent adopters: a person can approve the promotion
        for i in range(29):
            (ad / f"user{i}.json").write_text("{}")
        assert E.standing(tmp)[0]["next"].startswith("ready for a promotion decision")
        out = P.prepare(vid, "Maintainer", root=tmp)
        assert "Prepared" in out
        assert "Last reminder" in (tmp / "cells" / CELL / "followup.py").read_text()
        decision = json.loads((tmp / "ledger" / "pending" / f"decision-promote-{vid}.json").read_text())
        assert decision["parents"] == [CELL, f"variant-{vid}"] and "adopters=30" in decision["notes"] and "OVERRIDE" not in decision["notes"]
        errors, _ = C.check_shared(tmp)
        assert errors == [] and E.standing(tmp)[0]["next"].startswith("promoted")

        # everyone who ran it is now simply on the original
        for person in (ana, ben):
            msgs = person.refresh()
            assert "now part of the original" in msgs[0] and person.active_dirs() == {}
    finally:
        shutil.rmtree(tmp)


def test_tampered_or_misfiled_is_rejected():
    tmp = scratch()
    try:
        src = next((ROOT / "variants" / "shared").glob("*/*.json"))
        v = json.loads(src.read_text())
        bad = tmp / "variants" / "shared" / CELL / src.name
        bad.parent.mkdir(parents=True)
        v["changes"][0]["new"] += "\nimport os\n"
        bad.write_text(json.dumps(v))
        errors, _ = C.check_shared(tmp)
        assert any("altered" in e for e in errors)
        wrong = tmp / "variants" / "shared" / "small-business-core" / src.name
        wrong.parent.mkdir(parents=True)
        shutil.copy(src, wrong)
        bad.unlink()
        errors, _ = C.check_shared(tmp)
        assert any("must be filed as" in e for e in errors)
    finally:
        shutil.rmtree(tmp)


if __name__ == "__main__":
    for name, fn in list(globals().items()):
        if name.startswith("test_"):
            fn()
    print("OK: share, adopt, count, promote loop passes")
