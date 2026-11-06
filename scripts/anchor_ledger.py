#!/usr/bin/env python3
"""Stamp the ledger tip with OpenTimestamps, or upgrade pending proofs.

Stdlib only. The `ots` client is installed in CI, not imported here.

  python3 scripts/anchor_ledger.py stamp
  python3 scripts/anchor_ledger.py upgrade

A stamp file records the ledger tip hash plus the git commit and tree.
`ots stamp` anchors those bytes. `ots upgrade` later adds the Bitcoin proof.
"""

from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
from pathlib import Path


def repo_root() -> Path:
    return Path(__file__).resolve().parents[1]


def git(root: Path, *args: str) -> str:
    result = subprocess.run(
        ["git", "-C", str(root), *args],
        check=True,
        capture_output=True,
        text=True,
    )
    return result.stdout.strip()


def ledger_tip(root: Path) -> str:
    path = root / "ledger" / "contributions.json"
    with path.open(encoding="utf-8") as handle:
        data = json.load(handle)
    tip = data.get("tip_hash") or ""
    if not tip:
        raise SystemExit(f"no tip_hash in {path}")
    return str(tip)


def stamp_bytes(tip: str, commit: str, tree: str) -> str:
    return f"ledger_tip: {tip}\ngit_commit: {commit}\ngit_tree: {tree}\n"


def ots_bin() -> str:
    found = shutil.which("ots")
    if not found:
        raise SystemExit(
            "ots is not installed. CI installs it with: pip install opentimestamps-client"
        )
    return found


def stamp(root: Path, commit: str | None = None) -> Path | None:
    commit = commit or git(root, "rev-parse", "HEAD")
    tree = git(root, "rev-parse", f"{commit}^{{tree}}")
    # The ledger tip is whatever contributions.json says at this checkout.
    # Tag/release workflows check out that commit before calling stamp.
    tip = ledger_tip(root)
    folder = root / "anchors" / "stamps"
    folder.mkdir(parents=True, exist_ok=True)
    target = folder / f"{commit}.txt"
    proof = Path(str(target) + ".ots")
    body = stamp_bytes(tip, commit, tree)
    if target.is_file() and target.read_text(encoding="utf-8") != body:
        raise SystemExit(f"refusing to overwrite {target} with different bytes")
    if proof.is_file():
        print(f"OK: already stamped {proof.relative_to(root)}")
        return proof
    target.write_text(body, encoding="utf-8")
    subprocess.run(
        [ots_bin(), "stamp", "--timeout", "30", "-m", "1", str(target)],
        check=True,
    )
    if not proof.is_file():
        raise SystemExit(f"ots stamp did not write {proof}")
    print(f"OK: stamped {proof.relative_to(root)}")
    return proof


def upgrade(root: Path) -> int:
    proofs = sorted(
        path
        for path in (root / "anchors").rglob("*.ots")
        if path.is_file() and not path.name.endswith(".bak")
    )
    if not proofs:
        print("OK: no .ots proofs to upgrade")
        return 0
    subprocess.run(
        [ots_bin(), "upgrade", "--timeout", "60", *[str(path) for path in proofs]],
        check=False,
    )
    removed = 0
    for bak in (root / "anchors").rglob("*.bak"):
        bak.unlink()
        removed += 1
    print(f"OK: upgrade attempted for {len(proofs)} proof(s); removed {removed} bak file(s)")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="OpenTimestamps anchor for the ledger tip")
    parser.add_argument("command", choices=("stamp", "upgrade"))
    parser.add_argument("--commit", default="", help="Commit SHA to record (default: HEAD)")
    args = parser.parse_args()
    root = repo_root()
    if args.command == "stamp":
        stamp(root, args.commit or None)
    else:
        upgrade(root)
    return 0


if __name__ == "__main__":
    sys.exit(main())
