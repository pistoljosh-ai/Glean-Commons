#!/usr/bin/env python3
"""Static checks for the Folio edit-mode patch. Stdlib only."""

from __future__ import annotations

import subprocess
from pathlib import Path

HERE = Path(__file__).resolve().parent
PATCH = HERE / "edit-mode-erase.patch"
PIN = "0590fac31d915810c881ca6144fc7e8bb32e82c0"


def main() -> None:
    text = PATCH.read_text(encoding="utf-8")
    for name in (
        "a/README.md",
        "a/src/ContentEditor.tsx",
        "a/src/styles.css",
        "a/scripts/test-edit-erase.mjs",
    ):
        assert f"diff --git {name} " in text, name
    assert "package-lock.json" not in text
    assert "setSelectionRange" in text
    assert "disableUpdates" in text
    assert "folio-remove-line" in text
    assert "Remove line" in text
    assert "fillRect" not in text
    assert "BakedHello" in text and "FormHello" in text and "KeepMe" in text
    removed_select = "\n-    if (selected?.target.kind === \"text\") { input.current?.focus({ preventScroll: true }); input.current?.select(); }"
    assert removed_select in text
    # The patch must still be the one that applies to the pinned revision.
    apply = HERE / "apply_and_test.py"
    script = apply.read_text(encoding="utf-8")
    assert PIN in script and "https://github.com/Forward-Future/folio" in script
    cell = (HERE / "cell.md").read_text(encoding="utf-8")
    assert PIN in cell and "MIT" in cell and "mberman84" in cell
    clean = Path("/tmp/folio-check")
    if (clean / ".git").exists():
        head = subprocess.run(["git", "rev-parse", "HEAD"], cwd=clean, capture_output=True, text=True, check=True).stdout.strip()
        dirty = subprocess.run(["git", "status", "--porcelain"], cwd=clean, capture_output=True, text=True, check=True).stdout.strip()
        if head == PIN and not dirty:
            subprocess.run(["git", "apply", "--check", str(PATCH)], cwd=clean, check=True)
            print("ok  git apply --check against a clean pin checkout")
    print("ok  folio edit-erase patch checks passed")


if __name__ == "__main__":
    main()
