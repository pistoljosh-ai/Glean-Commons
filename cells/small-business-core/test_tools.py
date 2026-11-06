#!/usr/bin/env python3
"""Tests for the callable tools (writes, fuzzy lookup, versioning). Stdlib only."""

import json
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import books as B  # noqa: E402
import tools as T  # noqa: E402

HAS_GIT = shutil.which("git") is not None


def fresh():
    tmp = Path(tempfile.mkdtemp()) / "books"
    shutil.copytree(HERE / "sample_books", tmp)
    if HAS_GIT:
        B.git(tmp, "init", "-q")
        B.git(tmp, "add", ".")
        B.git(tmp, "commit", "-q", "-m", "Open the books")
    return tmp


def test_contract_matches_module():
    spec = json.loads((HERE / "tools.json").read_text())
    for t in spec["tools"]:
        assert callable(getattr(T, t["name"])), t["name"]
        assert t["description"] and t["inputSchema"]["type"] == "object"


def test_spoken_workflow():
    f = fresh()
    try:
        assert "Add customer C5: Fern Hollow" in T.add_customer(f, name="Fern Hollow", email="fh@x.example")
        assert "already a customer" in T.add_customer(f, name="fern hollow")
        assert "Add job J7 for Fern Hollow" in T.add_job(f, customer="fern", offer="lawn", status="scheduled",
                                                         scheduled_date="2026-11-10")
        assert "status=done" in T.update_job(f, job="J7", status="done")
        out = T.create_invoice(f, job="J7", issued_date="2026-11-10")
        assert "Invoice #1004 to Fern Hollow: $85.00, due 2026-12-10" in out, out
        assert "already invoiced" in T.create_invoice(f, job="J7")
        assert "paid in full" in T.record_payment(f, customer="Fern", method="cash")
        assert "more than" in T.record_payment(f, invoice="1003", amount=99999)
        assert "$1,200.00 still owed" in T.record_payment(f, invoice="#1003", amount=1000)
        assert B.check(B.load(f)) == []
    finally:
        shutil.rmtree(f.parent)


def test_ambiguity_asks():
    f = fresh()
    try:
        out = T.add_job(f, customer="e")  # matches several customers
        assert out.startswith("NEEDS INPUT") and "more than one customer" in out
        assert "No customer matches" in T.add_job(f, customer="Zebra Co")
        T.add_job(f, customer="Cedar", description="Custom pruning")
        assert "no priced offer" in T.create_invoice(f, job="pruning")
        assert "already invoiced" in T.create_invoice(f, job="J1")
    finally:
        shutil.rmtree(f.parent)


def test_bad_write_is_refused():
    f = fresh()
    try:
        before = (f / "jobs.csv").read_text()
        out = T.update_job(f, job="J1", status="finished")  # not a valid status
        assert out.startswith("NEEDS INPUT") and "Not saved" in out
        assert (f / "jobs.csv").read_text() == before
    finally:
        shutil.rmtree(f.parent)


def test_history_and_undo():
    if not HAS_GIT:
        return
    f = fresh()
    try:
        T.add_customer(f, name="Gale Farms")
        assert "Add customer C5: Gale Farms" in T.history(f)
        assert "Undid" in T.undo_last_change(f)
        assert "Gale Farms" not in (f / "customers.csv").read_text()
        log = T.history(f)
        assert "Revert" in log and "Gale Farms" in log  # nothing lost
    finally:
        shutil.rmtree(f.parent)


if __name__ == "__main__":
    for name, fn in list(globals().items()):
        if name.startswith("test_"):
            fn()
    print("OK: small-business-core tool tests passed")
