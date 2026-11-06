#!/usr/bin/env python3
"""Tests for the invoice follow-up cell. Stdlib only."""

import csv
import sys
from datetime import date
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

from followup import build_drafts, render, tier_for  # noqa: E402


def load():
    with (HERE / "sample_invoices.csv").open(newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def test_tiers():
    assert tier_for(0) is None
    assert tier_for(1)[0] == "friendly"
    assert tier_for(15)[0] == "firm"
    assert tier_for(45)[0] == "final"


def test_sample():
    drafts = build_drafts(load(), date(2026, 11, 6), "Test Co")
    # 1004 not due yet, 1005 paid -> 3 drafts, oldest first
    assert [d["tier"] for d in drafts] == ["final", "firm", "friendly"], drafts
    assert drafts[0]["to"] == "office@cedar.example"
    assert "1,250.00" in drafts[2]["body"]
    assert "Test Co" in drafts[0]["body"]
    assert "3 reminder draft(s)" in render(drafts)


def test_empty():
    assert "Nothing to send" in render([])


if __name__ == "__main__":
    test_tiers()
    test_sample()
    test_empty()
    print("OK: invoice-followup tests passed")
