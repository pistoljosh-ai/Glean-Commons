#!/usr/bin/env python3
"""Tests for the Folio document desk. Stdlib only. No network. No Folio process."""

from __future__ import annotations

import hashlib
import json
import sys
import tempfile
from contextlib import redirect_stderr, redirect_stdout
from io import StringIO
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(ROOT / "mcp"))

import desk  # noqa: E402
import tools  # noqa: E402
import server as mcp_server  # noqa: E402

PIN = "0590fac31d915810c881ca6144fc7e8bb32e82c0"
EXAMPLE = HERE / "examples" / "SYNTHETIC-not-a-real-invoice.pdf"
BANNED = ("subprocess", "urllib", "requests", "socket", "webbrowser", "os.system", "Popen")


def test_pin_and_license():
    pin = desk.load_pin()
    assert pin["url"] == "https://github.com/Forward-Future/folio"
    assert pin["pinned_revision"] == PIN
    assert pin["license_spdx"] == "MIT"
    assert pin["copyright"] == "Copyright (c) 2026 mberman84"
    assert pin["vendored_code"] is False
    assert pin["stars_are_proof_of_use"] is False
    license_bytes = desk.LICENSE_PATH.read_bytes()
    assert license_bytes.startswith(b"MIT License\n\nCopyright (c) 2026 mberman84\n")
    assert hashlib.sha256(license_bytes).hexdigest() == pin["license_sha256"]
    text = desk.provenance_text()
    assert "https://github.com/Forward-Future/folio" in text
    assert PIN in text
    assert "MIT" in text
    assert "Copyright (c) 2026 mberman84" in text
    assert "not in this repository" in text
    assert "did not clone, download, launch, or import Folio" in text


def test_synthetic_slip_and_refusals():
    slip = desk.slip_text(EXAMPLE)
    digest = hashlib.sha256(EXAMPLE.read_bytes()).hexdigest()
    assert f"SHA-256: {digest}" in slip
    assert "Header: %PDF-" in slip
    assert "Synthetic marker (SYNTHETIC example. Not a real invoice.): present" in slip
    assert "did not launch Folio" in slip
    assert "did not extract text" in slip
    with redirect_stdout(StringIO()):
        assert desk.main(["slip", str(EXAMPLE)]) == 0

    tmp = Path(tempfile.mkdtemp())
    try:
        other = tmp / "notes.txt"
        other.write_bytes(b"not a pdf")
        try:
            desk.identify_pdf(other)
            raise AssertionError("non-pdf should be refused")
        except desk.DeskError as exc:
            assert "%PDF-" in str(exc)
        missing = tmp / "missing.pdf"
        try:
            desk.identify_pdf(missing)
            raise AssertionError("missing file should be refused")
        except desk.DeskError as exc:
            assert "Not a file" in str(exc)
        link = tmp / "link.pdf"
        link.symlink_to(EXAMPLE)
        try:
            desk.identify_pdf(link)
            raise AssertionError("symlink should be refused")
        except desk.DeskError as exc:
            assert "symlink" in str(exc)
        desk.MAX_BYTES = 20
        try:
            big = tmp / "big.pdf"
            big.write_bytes(b"%PDF-" + b"x" * 40)
            try:
                desk.identify_pdf(big)
                raise AssertionError("oversize pdf should be refused")
            except desk.DeskError as exc:
                assert "larger than" in str(exc)
        finally:
            desk.MAX_BYTES = 300 * 1024 * 1024
    finally:
        for child in tmp.iterdir():
            if child.is_symlink() or child.is_file():
                child.unlink()
        tmp.rmdir()


def test_checkout_match_and_mismatch():
    pin = desk.load_pin()["pinned_revision"]
    tmp = Path(tempfile.mkdtemp())
    try:
        loose = tmp / "loose"
        ref = loose / ".git" / "refs" / "heads"
        ref.mkdir(parents=True)
        (loose / ".git" / "HEAD").write_text("ref: refs/heads/main\n", encoding="utf-8")
        (ref / "main").write_text(pin + "\n", encoding="utf-8")
        matched = desk.checkout_text(loose)
        assert "Match: yes" in matched
        assert "was not launched" in matched

        packed = tmp / "packed"
        (packed / ".git").mkdir(parents=True)
        (packed / ".git" / "HEAD").write_text("ref: refs/heads/main\n", encoding="utf-8")
        (packed / ".git" / "packed-refs").write_text(
            "# pack-refs with: peeled fully-peeled sorted\n"
            + "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa refs/heads/other\n"
            + pin
            + " refs/heads/main\n",
            encoding="utf-8",
        )
        assert "Match: yes" in desk.checkout_text(packed)

        (ref / "main").write_text("0123456789abcdef0123456789abcdef01234567\n", encoding="utf-8")
        assert "Match: no" in desk.checkout_text(loose)

        detached = tmp / "detached"
        (detached / ".git").mkdir(parents=True)
        (detached / ".git" / "HEAD").write_text(pin + "\n", encoding="utf-8")
        assert desk.read_head(detached) == pin

        linked = tmp / "linked"
        linked.mkdir()
        (linked / ".git").write_text(f"gitdir: {detached / '.git'}\n", encoding="utf-8")
        assert desk.read_head(linked) == pin

        empty = tmp / "empty-dir"
        empty.mkdir()
        try:
            desk.read_head(empty)
            raise AssertionError("non-checkout should fail")
        except desk.DeskError as exc:
            assert "does not clone" in str(exc)

        with redirect_stdout(StringIO()):
            assert desk.main([]) == 0
        with redirect_stderr(StringIO()):
            assert desk.main(["compare-checkout"]) == 2
    finally:
        import shutil
        shutil.rmtree(tmp)


def test_tool_stays_local_and_does_not_steal_routes():
    spec = json.loads((HERE / "tools.json").read_text(encoding="utf-8"))
    assert spec["cell"] == "folio-document-desk"
    assert len(spec["tools"]) == 1
    assert spec["tools"][0]["name"] == "folio_pdf_desk"
    assert not spec["tools"][0].get("stateless")
    source = (HERE / "desk.py").read_text(encoding="utf-8") + (HERE / "tools.py").read_text(encoding="utf-8")
    for banned in BANNED:
        assert banned not in source

    out = tools.folio_pdf_desk(None)
    assert PIN in out
    assert tools.folio_pdf_desk(None, action="slip").startswith("NEEDS INPUT")
    assert "SHA-256" in tools.folio_pdf_desk(None, action="slip", path=str(EXAMPLE))

    absent = Path("/tmp/folio-desk-should-not-create-books")
    if absent.exists():
        raise AssertionError(f"refusing to run public-mode test over existing path {absent}")
    public = mcp_server.Server(absent, public=True)
    assert "folio_pdf_desk" not in public.tools
    assert not absent.exists()

    local_root = Path(tempfile.mkdtemp())
    try:
        local = mcp_server.Server(local_root / "books")
        assert "folio_pdf_desk" in local.tools
        cases = {
            "who owes me money?": "open_invoices",
            "chase the late payers": "draft_payment_reminders",
            "Acme paid by check": "record_payment",
            "add a new client named Bob": "add_customer",
            "how's business?": "business_status",
            "bill the Cedar job": "create_invoice",
            "I made a mistake, undo that": "undo_last_change",
        }
        for request, tool in cases.items():
            top = mcp_server.rank_tools(request, local.tools)[0][1]
            assert top == tool, (request, top)
        assert mcp_server.rank_tools("send a quote to the Garcias", local.tools) == []
        ranked = mcp_server.rank_tools("identify this pdf with folio", local.tools)
        assert ranked and ranked[0][1] == "folio_pdf_desk"
    finally:
        import shutil
        shutil.rmtree(local_root)


if __name__ == "__main__":
    test_pin_and_license()
    test_synthetic_slip_and_refusals()
    test_checkout_match_and_mismatch()
    test_tool_stays_local_and_does_not_steal_routes()
    print("OK: folio-document-desk tests passed")
