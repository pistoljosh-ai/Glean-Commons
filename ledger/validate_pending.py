#!/usr/bin/env python3
"""Check ledger/pending and registry/pending without writing the chain.

  python3 ledger/validate_pending.py
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from fold_pending import validate  # noqa: E402


def main() -> int:
    errors = validate()
    if errors:
        print(f"FAIL: {len(errors)} pending error(s)", file=sys.stderr)
        for error in errors:
            print(f"  - {error}", file=sys.stderr)
        return 1
    print("OK: pending entries are foldable")
    return 0


if __name__ == "__main__":
    sys.exit(main())
