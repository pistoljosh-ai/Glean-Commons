#!/usr/bin/env python3
"""Check every shared variant and every adoption record.

A shared variant must be well formed, unaltered since it was saved, filed
under the tool it changes, and — when it fits the current original — pass
that tool's own tests with the change applied.

An adoption record is one small file per GitHub account. On a pull request
(PR_AUTHOR set), a person may only add, change or remove their own.

Usage:
  python3 scripts/check_variants.py                 # everything in the repo
  PR_AUTHOR=login python3 scripts/check_variants.py origin/main   # plus the one-voice rule

Stdlib only.
"""

from __future__ import annotations

import json
import os
import re
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "variants"))
import engine as E  # noqa: E402


def check_shared(root: Path = ROOT) -> tuple[list[str], list[str]]:
    errors, notes = [], []
    cells = sorted(d for d in (root / "cells").iterdir() if d.is_dir() and not d.name.startswith(("_", ".")))
    for f in sorted((root / "variants" / "shared").glob("*/*.json")):
        where = f.relative_to(root).as_posix()
        try:
            v = json.loads(f.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            errors.append(f"{where}: not valid JSON ({exc})")
            continue
        errs = E.validate(v)
        if errs:
            errors += [f"{where}: {e}" for e in errs]
            continue
        group = v["base"].get("cell") or E.UPSTREAM
        if f.stem != v["id"] or f.parent.name != group:
            errors.append(f"{where}: must be filed as variants/shared/{group}/{v['id']}.json")
            continue
        if v["kind"] != "cell":
            notes.append(f"{v['id']}: patch for an outside program; not run here")
            continue
        base = root / "cells" / group
        if not base.is_dir():
            errors.append(f"{where}: there is no cell called {group}")
            continue
        with tempfile.TemporaryDirectory() as tmp:
            status, why = E.apply_changes(base, v["changes"], Path(tmp) / group)
            if status == "conflict":
                notes.append(f"{v['id']}: no longer fits the original ({'; '.join(why)}); it needs re-fitting")
            elif status == "same":
                if v.get("status") != "canonical":
                    notes.append(f"{v['id']}: already part of the original; mark it canonical")
            else:
                if v.get("status") == "canonical":
                    errors.append(f"{where}: marked canonical but the original does not contain it")
                ok, report = E.run_tests(Path(tmp) / group, [str(c) for c in cells if c.name != group])
                if ok is False:
                    errors.append(f"{where}: the tool's tests fail with this variant applied\n{report}")
                else:
                    notes.append(f"{v['id']}: fits {group}" + ("; tests pass" if ok else "; the tool has no tests"))
    return errors, notes


def check_adoptions(root: Path = ROOT) -> list[str]:
    errors = []
    known = {v["id"] for v in E.shared_variants(root)}
    for f in sorted((root / "variants" / "adoptions").glob("*/*")):
        where = f.relative_to(root).as_posix()
        if f.name == "README.md":
            continue
        if f.suffix != ".json" or not re.fullmatch(r"[A-Za-z0-9](?:[A-Za-z0-9-]{0,38})", f.stem):
            errors.append(f"{where}: must be named <github-login>.json")
        elif f.parent.name not in known:
            errors.append(f"{where}: there is no shared variant called {f.parent.name}")
        else:
            try:
                json.loads(f.read_text(encoding="utf-8"))
            except json.JSONDecodeError:
                errors.append(f"{where}: not valid JSON")
    return errors


def one_voice(changed: list[tuple[str, str]], author: str) -> list[str]:
    """changed: (status, path) pairs. Only your own adoption record may change in your pull request."""
    errors = []
    for _status, path in changed:
        p = Path(path)
        if path.startswith("variants/adoptions/") and p.suffix == ".json" and p.stem.lower() != author.lower():
            errors.append(f"{path}: an adoption record speaks for one GitHub account. "
                          f"This pull request is from {author}, so it can only add or change {author}.json.")
    return errors


def main(argv: list[str]) -> int:
    errors, notes = check_shared()
    errors += check_adoptions()
    author = os.environ.get("PR_AUTHOR", "").strip()
    if author and len(argv) > 1:
        out = subprocess.run(["git", "diff", "--name-status", "--no-renames", f"{argv[1]}...HEAD"],
                             capture_output=True, text=True, check=True).stdout
        errors += one_voice([(l.split("\t")[0][0], l.split("\t")[-1]) for l in out.splitlines() if "\t" in l], author)
    for n in notes:
        print("  " + n)
    if errors:
        print("FAIL:\n" + "\n".join("  - " + e for e in errors), file=sys.stderr)
        return 1
    print(f"OK: {len(E.shared_variants())} shared variant(s) checked")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
