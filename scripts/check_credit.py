#!/usr/bin/env python3
"""Every contribution carries its credit.

> Every idea has an ancestry. — The Glean System, Draft 1.0, sec 4.3
> AI attributes credit fairly. — sec 3.4

A pull request that changes what the commons *does* (code, cells, tools,
workflows, upstream pointers) must add a ledger entry in ledger/pending/.
Docs-only edits and generated files don't need one.

Usage (CI runs this on every pull request):
  python3 scripts/check_credit.py <base-ref>        e.g. origin/main
  NO_CREDIT=1 python3 scripts/check_credit.py ...   maintainer-approved exemption

Stdlib only.
"""

from __future__ import annotations

import os
import subprocess
import sys

# Paths whose changes are contributions that need credit.
CONTRIBUTION_PREFIXES = (
    "cells/", "mcp/", "router/", "analyst/", "scripts/", "ledger/", "upstream/",
    "experiments/", "video/", "whitepaper/", "dashboard/template.html", ".github/workflows/",
)
# Generated or bookkeeping files: never count as a contribution on their own.
GENERATED = (
    "catalog.json", "catalog.txt", "llms.txt", "commons.json", "ledger/contributions.json",
    "dashboard/index.html", "dashboard/data.json", "dashboard/data/", "anchors/",
    "ledger/pending/", "registry/pending/",
)


def needs_credit(path: str) -> bool:
    if path.startswith(GENERATED) or path.endswith(".md"):
        return False
    return path.startswith(CONTRIBUTION_PREFIXES)


def is_credit(path: str, status: str) -> bool:
    return status == "A" and path.startswith("ledger/pending/") and path.endswith(".json")


def judge(changes: list[tuple[str, str]], exempt: bool = False) -> tuple[bool, str]:
    """changes: (status, path) pairs from git diff --name-status. Returns (ok, message)."""
    work = sorted({p for s, p in changes if needs_credit(p)})
    credits = sorted({p for s, p in changes if is_credit(p, s)})
    if not work:
        return True, "OK: no contribution paths changed (docs or generated files only); no credit needed."
    if credits:
        return True, f"OK: {len(work)} contribution file(s) credited by {', '.join(credits)}."
    if exempt:
        return True, f"OK: {len(work)} contribution file(s) changed; exempt by maintainer (no-credit label)."
    lines = [
        f"FAIL: this pull request changes {len(work)} contribution file(s) but adds no ledger entry.",
        "Every contribution carries its credit (whitepaper sec 4.3). Add ledger/pending/<id>.json",
        "naming the human creator, the AI that helped, and the parents it builds on. See ledger/pending/README.md.",
        "A maintainer can exempt a trivial fix with the 'no-credit' label.",
        "Changed:",
    ] + [f"  - {p}" for p in work[:20]]
    return False, "\n".join(lines)


def git_changes(base: str) -> list[tuple[str, str]]:
    out = subprocess.run(["git", "diff", "--name-status", "--no-renames", f"{base}...HEAD"],
                         capture_output=True, text=True, check=True).stdout
    pairs = []
    for line in out.splitlines():
        parts = line.split("\t")
        if len(parts) >= 2:
            pairs.append((parts[0][0], parts[-1]))
    return pairs


def main(argv: list[str]) -> int:
    base = argv[1] if len(argv) > 1 else "origin/main"
    ok, msg = judge(git_changes(base), exempt=os.environ.get("NO_CREDIT") == "1")
    print(msg, file=sys.stdout if ok else sys.stderr)
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv))
