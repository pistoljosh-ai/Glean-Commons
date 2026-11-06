#!/usr/bin/env python3
"""Tests for scripts/check_credit.py. Stdlib only."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

from check_credit import judge  # noqa: E402


def test_code_without_credit_fails():
    ok, msg = judge([("M", "cells/small-business-core/tools.py")])
    assert not ok and "adds no ledger entry" in msg


def test_code_with_credit_passes():
    ok, _ = judge([("A", "cells/quote/tools.py"), ("A", "ledger/pending/quote.json")])
    assert ok


def test_editing_an_existing_pending_file_is_not_new_credit():
    ok, _ = judge([("M", "mcp/server.py"), ("M", "ledger/pending/old.json")])
    assert not ok


def test_docs_and_generated_only_pass():
    ok, _ = judge([("M", "README.md"), ("M", "cells/invoice-followup/cell.md"),
                   ("M", "catalog.json"), ("M", "dashboard/index.html"), ("A", "anchors/stamps/x.txt")])
    assert ok


def test_workflows_need_credit():
    ok, _ = judge([("M", ".github/workflows/verify-ledger.yml")])
    assert not ok


def test_maintainer_exemption():
    ok, msg = judge([("M", "scripts/search.py")], exempt=True)
    assert ok and "exempt" in msg


if __name__ == "__main__":
    for name, fn in list(globals().items()):
        if name.startswith("test_"):
            fn()
    print("OK: credit check tests passed")
