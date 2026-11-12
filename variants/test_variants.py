#!/usr/bin/env python3
"""Tests for the variants engine. Stdlib only; works on a scratch copy of the cells."""

import json
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import engine as E  # noqa: E402

CELL = "invoice-followup"
OLD = r"Thank you,\n{business}"
NEW = r"With thanks,\n{business}"


def world():
    """A scratch commons (cells + shared folder) and one person's versions folder."""
    tmp = Path(tempfile.mkdtemp())
    E.copy_tree(E.CELLS, tmp / "cells")
    return tmp, E.Variants(tmp / "mine", cells_root=tmp / "cells", shared_root=tmp / "shared")


def make_version(v: E.Variants, name="warm sign-off"):
    v.start(CELL, "sign the final notice more warmly")
    v.edit(CELL, "followup.py", find=OLD, replace=NEW)
    return v.save(CELL, name, author="Test Person", ai_assist="Test AI")


def test_make_save_switch_and_history():
    tmp, v = world()
    try:
        assert "Private working copy ready" in v.start(CELL, "sign the final notice more warmly")
        assert OLD in v.read(CELL, "followup.py")
        assert "exactly once" in _problem(lambda: v.edit(CELL, "followup.py", find="{business}", replace="x"))
        assert "outside" in _problem(lambda: v.edit(CELL, "../../escape.py", content="x"))
        assert "reserved" in _problem(lambda: v.edit(CELL, "cell.json", content="{}"))
        v.edit(CELL, "followup.py", find=OLD, replace=NEW)
        ok, report = v.test(CELL)
        assert ok and "PASS" in report
        out = v.save(CELL, "warm sign-off", author="Test Person", ai_assist="Test AI")
        assert "Saved and switched on" in out and "tests pass" in out
        assert NEW in (v.effective_dir(CELL) / "followup.py").read_text()
        assert OLD in (tmp / "cells" / CELL / "followup.py").read_text()  # the original is untouched
        saved = v.saved(CELL)[0]
        assert E.validate(saved) == [] and saved["wish"] == "sign the final notice more warmly"
        assert "running warm-sign-off" in v.listing()
        assert "the original" in v.switch(CELL, "original") and v.effective_dir(CELL) == tmp / "cells" / CELL
        assert "your version" in v.switch(CELL, "previous") and NEW in (v.effective_dir(CELL) / "followup.py").read_text()
        if shutil.which("git"):
            log = subprocess.run(["git", "-C", str(tmp / "mine"), "log", "--format=%s"], capture_output=True, text=True).stdout
            assert "Save my version of invoice-followup: warm sign-off" in log and "Switch invoice-followup to the original" in log
    finally:
        shutil.rmtree(tmp)


def test_broken_change_is_not_saved():
    tmp, v = world()
    try:
        v.start(CELL, "break it")
        v.edit(CELL, "followup.py", find='(45, "final",', replace='(46, "last",')
        assert "tests fail" in _problem(lambda: v.save(CELL, "broken"))
        assert v.saved() == [] and v.active_dirs() == {}
        v2 = E.Variants(tmp / "other", cells_root=tmp / "cells")
        v2.start(CELL, "nothing")
        assert "identical" in _problem(lambda: v2.save(CELL, "nothing"))
    finally:
        shutil.rmtree(tmp)


def test_original_moves_on_and_we_do_not_lose_ground():
    tmp, v = world()
    try:
        make_version(v)
        base = tmp / "cells" / CELL / "followup.py"
        # 1. the original changes somewhere else in the same file: re-fitted
        base.write_text(base.read_text().replace("Quick reminder: invoice", "Friendly reminder: invoice"))
        msgs = v.refresh()
        mine = (v.effective_dir(CELL) / "followup.py").read_text()
        if shutil.which("git"):
            assert msgs == [] and NEW in mine and "Friendly reminder" in mine
        # 2. the original changes the very same lines: keep running the last good copy, and say so
        before = (v.effective_dir(CELL) / "followup.py").read_text()
        base.write_text(base.read_text().replace(OLD, r"Regards,\n{business}"))
        msgs = v.refresh()
        assert len(msgs) == 1 and "keeps running" in msgs[0]
        assert (v.effective_dir(CELL) / "followup.py").read_text() == before
        assert "second look" in v.listing()
        # 3. the original adopts exactly this change (promotion): quietly back to the original
        base.write_text(base.read_text().replace(r"Regards,\n{business}", NEW))
        msgs = v.refresh()
        assert "now part of the original" in msgs[0] and v.active_dirs() == {}
    finally:
        shutil.rmtree(tmp)


def test_share_adopt_and_standing():
    tmp, alice = world()
    try:
        make_version(alice)
        out = alice.share(cell=CELL, author="Alice Example", login="@alice")
        vid = alice.saved(CELL)[0]["id"]
        shared_file = tmp / "mine" / "outbox" / f"{vid}.json"
        assert f"variants/shared/{CELL}/{vid}.json" in out and shared_file.is_file()
        ledger = json.loads((tmp / "mine" / "outbox" / f"{vid}.ledger.json").read_text())
        assert ledger["parents"] == [CELL] and ledger["creator"] == "Alice Example" and ledger["uses"] == 0
        # publish into the scratch commons
        dest = tmp / "variants" / "shared" / CELL / f"{vid}.json"
        dest.parent.mkdir(parents=True)
        shutil.copy(shared_file, dest)
        bob = E.Variants(tmp / "bob", cells_root=tmp / "cells", shared_root=tmp / "variants" / "shared")
        preview = bob.adopt("warm-sign-off")
        assert "someone else's code" in preview and "With thanks" in preview and bob.active_dirs() == {}
        assert "Adopted and switched on" in bob.adopt("warm-sign-off", confirm=True)
        assert NEW in (bob.effective_dir(CELL) / "followup.py").read_text()
        # tampering is caught
        bad = json.loads(dest.read_text()); bad["changes"][0]["new"] += "import os\n"
        (tmp / "bad.json").write_text(json.dumps(bad))
        assert "altered" in _problem(lambda: bob.adopt(str(tmp / "bad.json"), confirm=True))
        # standing: the author's own adoption never counts
        ad = tmp / "variants" / "adoptions" / vid
        ad.mkdir(parents=True)
        for login in ["alice", "bob", "Carol"]:
            (ad / f"{login}.json").write_text(json.dumps({"variant": vid}))
        row = E.standing(tmp)[0]
        assert row["adopters"] == 2 and row["next"].startswith("keep testing (2 of 30")
        for i in range(30):
            (ad / f"user{i}.json").write_text("{}")
        assert E.standing(tmp)[0]["next"].startswith("ready for a promotion decision")
    finally:
        shutil.rmtree(tmp)


def test_upstream_patch_roundtrip():
    if not shutil.which("git"):
        return
    tmp, v = world()
    try:
        def repo(name):
            r = tmp / name
            r.mkdir()
            g = lambda *a: subprocess.run(["git", "-C", str(r), "-c", "user.name=t", "-c", "user.email=t@t", *a], capture_output=True, text=True)  # noqa: E731
            g("init", "-q")
            (r / "app.js").write_text("function sign() { return 'replace'; }\n")
            g("add", "-A"); g("commit", "-q", "-m", "pin", "--date=2026-01-01T00:00:00Z")
            return r, g
        import os
        os.environ.update(GIT_AUTHOR_DATE="2026-01-01T00:00:00Z", GIT_COMMITTER_DATE="2026-01-01T00:00:00Z")
        mine, _ = repo("mine-app")
        (mine / "app.js").write_text("function sign() { return 'replace'; }\nfunction removeSignature() { return null; }\n")
        (mine / "notes.txt").write_text("new file\n")
        out = v.capture_upstream(str(mine), "remove signature", "let me remove a signature, not just replace it", author="Test Person", upstream="some-app")
        assert "as a patch on commit" in out
        saved = v.saved(E.UPSTREAM)[0]
        assert E.validate(saved) == [] and "removeSignature" in saved["patch"] and "notes.txt" in saved["patch"]
        v.share(saved["id"])
        theirs, _ = repo("their-app")  # same content and dates, so the same commit id
        f = str(tmp / "mine" / "outbox" / f"{saved['id']}.json")
        assert "Read the patch" in v.adopt(f)
        assert "Applied to" in v.adopt(f, confirm=True, folder=str(theirs))
        assert "removeSignature" in (theirs / "app.js").read_text() and (theirs / "notes.txt").is_file()
        assert "does not fit" in _problem(lambda: v.adopt(f, confirm=True, folder=str(theirs)))
    finally:
        shutil.rmtree(tmp)


def _problem(fn) -> str:
    try:
        fn()
    except E.Problem as p:
        return str(p)
    raise AssertionError("expected a Problem")


if __name__ == "__main__":
    for name, fn in list(globals().items()):
        if name.startswith("test_"):
            fn()
    print("OK: variants engine tests passed")
