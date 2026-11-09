#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Apply the Folio edit-mode patch onto the pinned revision and run its test.

Folio itself is not stored in Glean Commons. This checks out
https://github.com/Forward-Future/folio at 0590fac31d915810c881ca6144fc7e8bb32e82c0,
applies cells/folio-edit-erase/edit-mode-erase.patch, then runs
scripts/test-edit-erase.mjs. That test launches the real reader against a
synthetic PDF. It does not build an installer and it does not push anywhere.

Usage:
  python3 cells/folio-edit-erase/apply_and_test.py
  python3 cells/folio-edit-erase/apply_and_test.py --folio-dir /path/to/clean/folio
"""

from __future__ import annotations

import argparse
import subprocess
import sys
import tempfile
from pathlib import Path

PIN = "0590fac31d915810c881ca6144fc7e8bb32e82c0"
UPSTREAM = "https://github.com/Forward-Future/folio"
HERE = Path(__file__).resolve().parent
PATCH = HERE / "edit-mode-erase.patch"


def run(cmd: list[str], cwd: Path, env: dict | None = None) -> None:
    print("+", " ".join(cmd), flush=True)
    subprocess.run(cmd, cwd=cwd, check=True, env=env)


def checkout(dest: Path) -> None:
    if (dest / ".git").exists():
        dirty = subprocess.run(["git", "status", "--porcelain"], cwd=dest, capture_output=True, text=True, check=True)
        if dirty.stdout.strip():
            raise SystemExit(f"{dest} has uncommitted changes. Pass a clean checkout of {PIN}.")
        head = subprocess.run(["git", "rev-parse", "HEAD"], cwd=dest, capture_output=True, text=True, check=True).stdout.strip()
        if head != PIN:
            run(["git", "fetch", "--depth", "1", "origin", PIN], dest)
            run(["git", "checkout", "--detach", PIN], dest)
        return
    dest.parent.mkdir(parents=True, exist_ok=True)
    run(["git", "clone", "--filter=blob:none", "--no-checkout", UPSTREAM, str(dest)], dest.parent)
    run(["git", "fetch", "--depth", "1", "origin", PIN], dest)
    run(["git", "checkout", "--detach", PIN], dest)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--folio-dir", type=Path, help="Clean Folio checkout. Created under the temp dir when omitted.")
    args = parser.parse_args()
    if not PATCH.is_file():
        raise SystemExit(f"Missing patch: {PATCH}")
    own_dir = args.folio_dir is None
    dest = args.folio_dir or Path(tempfile.mkdtemp(prefix="folio-edit-erase-"))
    checkout(dest)
    head = subprocess.run(["git", "rev-parse", "HEAD"], cwd=dest, capture_output=True, text=True, check=True).stdout.strip()
    if head != PIN:
        raise SystemExit(f"{dest} is {head}, not {PIN}")
    run(["git", "apply", "--check", str(PATCH)], dest)
    run(["git", "apply", str(PATCH)], dest)
    run(["npm", "install", "--no-audit", "--no-fund"], dest)
    run(["npm", "run", "assets"], dest)
    run(["node", "scripts/test-edit-erase.mjs"], dest)
    print()
    print(f"Patched Folio is at {dest}")
    print("The UI test passed. This is a source checkout, not an installed app.")
    print("To try it: cd there, run `npm run dev`, and open a PDF of your own that you can throw away.")
    print("Edit mode: click a line of baked-in text. Backspace deletes the previous character.")
    print("Enter applies the line. Clear the line and press Enter, or choose Remove line, to delete those words.")
    print("Esc cancels. Form fields, text boxes, and highlights are separate from that line editor.")
    if own_dir:
        print("The checkout is yours to inspect. Nothing was pushed and no installer was built.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
