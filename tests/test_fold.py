#!/usr/bin/env python3
"""Fold pending ledger entries without rewriting the existing chain."""

from __future__ import annotations

import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "ledger"))

import add_entry  # noqa: E402
import fold_pending  # noqa: E402


def _spec(eid: str, created: str, parents: list[str], title: str | None = None) -> dict:
    return {
        "id": eid,
        "title": title or eid,
        "type": "other",
        "creator": "Fold Test",
        "ai_assist": "test",
        "parents": parents,
        "created": created,
        "version": "0.0.0-test",
        "commit": "",
        "uses": 0,
        "notes": "Simulated pending entry. Not a real commons project.",
    }


def _write(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")


class FoldTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        ledger_src = ROOT / "ledger" / "contributions.json"
        ledger_dst = self.root / "ledger" / "contributions.json"
        ledger_dst.parent.mkdir(parents=True)
        shutil.copy(ledger_src, ledger_dst)
        self.before = json.loads(ledger_src.read_text(encoding="utf-8"))
        self.before_entries = json.loads(json.dumps(self.before["entries"]))

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def _add_pending(self, spec: dict) -> None:
        _write(self.root / "ledger" / "pending" / f"{spec['id']}.json", spec)

    def test_two_pending_entries_fold_in_created_order(self) -> None:
        # Filename order is the reverse of created order, so a sort-by-name
        # bug would chain them backwards.
        later = _spec("aaa-later", "2026-11-07T00:05:00Z", ["zzz-earlier"])
        earlier = _spec("zzz-earlier", "2026-11-07T00:00:00Z", ["glean-commons-repo"])
        self._add_pending(later)
        self._add_pending(earlier)
        starting_tip = self.before["tip_hash"]

        appended = fold_pending.fold(self.root)

        self.assertEqual([entry["id"] for entry in appended], ["zzz-earlier", "aaa-later"])
        self.assertEqual(appended[0]["prev_hash"], starting_tip)
        self.assertEqual(appended[1]["prev_hash"], appended[0]["entry_hash"])
        self.assertEqual(appended[1]["parents"], ["zzz-earlier"])
        self.assertEqual(appended[1]["parent_hashes"], [appended[0]["entry_hash"]])
        folded = json.loads((self.root / "ledger" / "contributions.json").read_text(encoding="utf-8"))
        self.assertEqual(folded["entries"][: len(self.before_entries)], self.before_entries)
        self.assertEqual(folded["tip_hash"], appended[1]["entry_hash"])
        for old, new in zip(self.before_entries, folded["entries"]):
            self.assertEqual(add_entry.compute_hash(old), old["entry_hash"])
            self.assertEqual(old, new)
        self.assertFalse((self.root / "ledger" / "pending" / "zzz-earlier.json").exists())
        self.assertFalse((self.root / "ledger" / "pending" / "aaa-later.json").exists())
        print(
            "DRY-RUN tip_before="
            + starting_tip
            + " first="
            + appended[0]["id"]
            + " "
            + appended[0]["entry_hash"]
            + " second="
            + appended[1]["id"]
            + " "
            + appended[1]["entry_hash"]
            + " tip_after="
            + appended[1]["entry_hash"]
        )

    def test_folded_copy_still_verifies(self) -> None:
        self._add_pending(_spec("fold-verify-child", "2026-11-07T01:00:00Z", ["glean-commons-repo"]))
        fold_pending.fold(self.root)
        proc = subprocess.run(
            [sys.executable, str(ROOT / "ledger" / "verify.py"), str(self.root / "ledger" / "contributions.json")],
            capture_output=True,
            text=True,
        )
        # verify.py also checks commons.json next to the ledger's parent.
        # Point it at an isolated ledger by passing the path; commons checks
        # use the script's repo root, so run verify's ledger function instead
        # when the temp root is not the repo.
        self.assertEqual(proc.returncode, 0, proc.stderr)
        errors = []
        # Re-check with the library so a missing commons in the temp root is irrelevant.
        sys.path.insert(0, str(ROOT / "ledger"))
        import verify  # noqa: E402

        errors = verify.verify_ledger(self.root / "ledger" / "contributions.json")
        self.assertEqual(errors, [])

    def test_handwritten_hash_is_rejected(self) -> None:
        spec = _spec("hashed-by-hand", "2026-11-07T02:00:00Z", ["glean-commons-repo"])
        spec["entry_hash"] = "abc"
        spec["prev_hash"] = "def"
        self._add_pending(spec)
        errors = fold_pending.validate(self.root)
        self.assertTrue(any("entry_hash" in error for error in errors))
        self.assertTrue(any("prev_hash" in error for error in errors))

    def test_registry_fragment_receives_computed_hash(self) -> None:
        eid = "fragment-cell"
        self._add_pending(_spec(eid, "2026-11-07T03:00:00Z", ["glean-commons-repo"], title="Fragment cell"))
        manifest_rel = "cells/fragment-cell/cell.json"
        _write(
            self.root / manifest_rel,
            {"id": eid, "name": "Fragment cell", "entry_hash": None, "parents": ["glean-commons-repo"]},
        )
        _write(
            self.root / "registry" / "pending" / f"{eid}.json",
            {
                "id": eid,
                "name": "Fragment cell",
                "type": "cell",
                "path": "cells/fragment-cell/",
                "manifest": manifest_rel,
                "status": "active",
                "maintainers": ["Fold Test"],
                "parents": ["glean-commons-repo"],
                "entry_hash": None,
                "tags": ["test"],
                "how_to_change": {"edit": [manifest_rel], "labels": ["type:cell"]},
                "canonical_version": "0.0.0-test",
                "variants": [],
                "experiments": [],
            },
        )
        _write(self.root / "commons.json", {"schema_version": 1, "projects": []})
        appended = fold_pending.fold(self.root)
        commons = json.loads((self.root / "commons.json").read_text(encoding="utf-8"))
        manifest = json.loads((self.root / manifest_rel).read_text(encoding="utf-8"))
        self.assertEqual(commons["projects"][0]["entry_hash"], appended[0]["entry_hash"])
        self.assertEqual(manifest["entry_hash"], appended[0]["entry_hash"])
        self.assertFalse((self.root / "registry" / "pending" / f"{eid}.json").exists())

    def test_real_repo_pending_dir_is_empty(self) -> None:
        errors = fold_pending.validate(ROOT)
        self.assertEqual(errors, [])


if __name__ == "__main__":
    unittest.main()
