#!/usr/bin/env python3
"""Tests for small-business-core (the books). Stdlib only."""

import csv
import io
import shutil
import sys
import tempfile
from datetime import date
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE.parent / "invoice-followup"))

import books  # noqa: E402
from followup import build_drafts  # noqa: E402

TODAY = date(2026, 11, 6)
SAMPLE = HERE / "sample_books"


def test_sample_is_consistent():
    assert books.check(books.load(SAMPLE)) == []


def test_paid_is_derived_from_payments():
    by_id = {i["invoice_id"]: i for i in books.invoice_balances(books.load(SAMPLE), TODAY)}
    assert by_id["1001"]["balance"] == 0 and by_id["1001"]["days_overdue"] == 0
    assert by_id["1002"]["paid"] == 200 and by_id["1002"]["balance"] == 280
    assert by_id["1003"]["days_overdue"] == 52


def test_status():
    s = books.status_text(books.load(SAMPLE), TODAY)
    assert "$2,480.00 across 2 invoice(s)" in s
    assert "Done, not invoiced: J6" in s


def test_ar_feeds_invoice_followup():
    rows = list(csv.DictReader(io.StringIO(books.ar_csv(books.load(SAMPLE), TODAY))))
    drafts = build_drafts(rows, TODAY, "Test Co")
    assert [d["tier"] for d in drafts] == ["final", "firm"]
    assert drafts[1]["amount"] == 280  # remaining balance, not original amount


def test_check_catches_problems():
    tmp = Path(tempfile.mkdtemp())
    try:
        shutil.copytree(SAMPLE, tmp / "b")
        with (tmp / "b" / "payments.csv").open("a", encoding="utf-8") as f:
            f.write("P3,9999,10,2026-11-01,cash\nP3,1001,abc,nope,cash\n")
        errs = books.check(books.load(tmp / "b"))
        joined = "\n".join(errs)
        assert "'9999' not found in invoices.csv" in joined
        assert "duplicate payment_id 'P3'" in joined
        assert "not a valid money" in joined and "not a valid date" in joined
    finally:
        shutil.rmtree(tmp)


def test_init_creates_headers():
    tmp = Path(tempfile.mkdtemp())
    try:
        books.cmd_init(tmp / "new")
        assert (tmp / "new" / "jobs.csv").read_text().startswith("job_id,customer_id")
        assert books.check(books.load(tmp / "new")) == []
    finally:
        shutil.rmtree(tmp)


if __name__ == "__main__":
    for name, fn in list(globals().items()):
        if name.startswith("test_"):
            fn()
    print("OK: small-business-core tests passed")
