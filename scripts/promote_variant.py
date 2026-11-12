#!/usr/bin/env python3
"""Prepare a promotion: make a shared variant the original.

This script only prepares the change in your working tree. It never commits,
pushes or merges. A person opens the pull request and a person merges it
(ANALYST.md: humans approve every promotion).

What it does:
  1. Checks the variant has enough independent adopters (30), unless
     --maintainer-override is given, which is recorded in the ledger note.
  2. Applies the variant to the cell and runs the cell's tests.
  3. Marks the variant file canonical.
  4. Writes ledger/pending/decision-promote-<id>.json crediting both the
     original and the variant, so value flows up the tree (whitepaper 4.3).

Usage:
  python3 scripts/promote_variant.py <variant-id> --approved-by "Your Name"
"""

from __future__ import annotations

import argparse
import json
import shutil
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "variants"))
import engine as E  # noqa: E402


def prepare(variant_ref: str, approved_by: str, override: bool = False, root: Path = ROOT) -> str:
    files = [f for f in sorted((root / "variants" / "shared").glob("*/*.json")) if variant_ref.lower() in f.stem.lower()]
    if len(files) != 1:
        raise E.Problem(f"'{variant_ref}' matches {len(files)} shared variants; name exactly one.")
    v = json.loads(files[0].read_text(encoding="utf-8"))
    if v["kind"] != "cell":
        raise E.Problem("Only variants of commons cells can be promoted here; patches for outside programs go to that project.")
    if v.get("status") == "canonical":
        raise E.Problem("That variant is already the original.")
    n = len(E.adopters(v, root))
    if n < E.PROMOTE_AT and not override:
        raise E.Problem(f"Not yet: {n} of {E.PROMOTE_AT} independent adopters. Keep testing. "
                        "(A maintainer can pass --maintainer-override; the ledger will say so.)")
    cell = v["base"]["cell"]
    base = root / "cells" / cell
    others = [str(d) for d in (root / "cells").iterdir() if d.is_dir() and d.name != cell and not d.name.startswith(("_", "."))]
    with tempfile.TemporaryDirectory() as tmp:
        status, notes = E.apply_changes(base, v["changes"], Path(tmp) / cell)
        if status != "ok":
            raise E.Problem(f"Cannot promote: {'already in the original' if status == 'same' else '; '.join(notes)}")
        ok, report = E.run_tests(Path(tmp) / cell, others)
        if ok is False:
            raise E.Problem("Cannot promote: the cell's tests fail with it applied.\n" + report)
        for c in v["changes"]:
            target, built = base / c["path"], Path(tmp) / cell / c["path"]
            if built.is_file():
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(built, target)
            elif target.exists():
                target.unlink()
    v["status"], v["promoted"] = "canonical", E.now()[:10]
    files[0].write_text(json.dumps(v, indent=2) + "\n", encoding="utf-8")
    entry = {
        "id": f"decision-promote-{v['id']}", "title": f"Decision: promote '{v['name']}' to the original {cell}",
        "type": "other", "creator": approved_by, "ai_assist": "", "parents": [cell, f"variant-{v['id']}"],
        "created": E.now(), "version": "decision", "commit": "", "uses": 0,
        "notes": f"promote; variant {v['id']} by {v['author']}; independent adopters={n} (threshold {E.PROMOTE_AT})"
                 + ("; MAINTAINER OVERRIDE below threshold" if n < E.PROMOTE_AT else "")
                 + f"; evidence: variants/adoptions/{v['id']}/; approved by {approved_by}. Wish: {v['wish']}",
    }
    out = root / "ledger" / "pending" / f"{entry['id']}.json"
    out.write_text(json.dumps(entry, indent=2) + "\n", encoding="utf-8")
    return (f"Prepared. cells/{cell}/ now contains '{v['name']}', its tests pass, and {out.relative_to(root)} records the decision.\n"
            "Review the diff, open a pull request, and merge it yourself. After the merge, everyone running this variant "
            "switches back to the original automatically, because the original now is their version.")


def main() -> int:
    p = argparse.ArgumentParser(description="Prepare a variant promotion (never merges)")
    p.add_argument("variant")
    p.add_argument("--approved-by", required=True, help="the person accountable for this decision")
    p.add_argument("--maintainer-override", action="store_true", help="promote below the adopter threshold; recorded in the ledger")
    a = p.parse_args()
    try:
        print(prepare(a.variant, a.approved_by, a.maintainer_override))
    except E.Problem as exc:
        print(f"{exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
