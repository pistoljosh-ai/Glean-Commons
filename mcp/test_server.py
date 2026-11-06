#!/usr/bin/env python3
"""End-to-end test: drive the MCP server over real stdio like an AI app would."""

import json
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
SERVER = HERE / "server.py"


def session(books: Path, calls: list[tuple[str, dict]]) -> list[dict]:
    msgs = [
        {"jsonrpc": "2.0", "id": 0, "method": "initialize",
         "params": {"protocolVersion": "2025-06-18", "capabilities": {}, "clientInfo": {"name": "test"}}},
        {"jsonrpc": "2.0", "method": "notifications/initialized"},
        {"jsonrpc": "2.0", "id": 1, "method": "tools/list"},
    ]
    for i, (name, args) in enumerate(calls, start=2):
        msgs.append({"jsonrpc": "2.0", "id": i, "method": "tools/call",
                     "params": {"name": name, "arguments": args}})
    msgs.append({"jsonrpc": "2.0", "id": 999, "method": "no/such"})
    proc = subprocess.run([sys.executable, str(SERVER), "--books", str(books)],
                          input="\n".join(json.dumps(m) for m in msgs) + "\n",
                          capture_output=True, text=True, timeout=60)
    assert proc.returncode == 0, proc.stderr
    return [json.loads(l) for l in proc.stdout.splitlines()]


def text(reply: dict) -> str:
    return reply["result"]["content"][0]["text"]


def test_conversation():
    tmp = Path(tempfile.mkdtemp())
    books = tmp / "my-books"  # does not exist yet: server opens fresh books
    try:
        out = session(books, [
            ("add_offer", {"name": "Lawn treatment", "price": 85, "unit": "visit"}),
            ("add_customer", {"name": "Fern Hollow", "email": "fh@x.example"}),
            ("add_job", {"customer": "fern", "offer": "lawn", "status": "scheduled",
                         "scheduled_date": "2026-11-10"}),
            ("update_job", {"job": "fern", "status": "done", "done_date": "2026-11-10"}),
            ("create_invoice", {"job": "J1", "issued_date": "2026-09-01", "terms_days": 15}),
            ("business_status", {"today": "2026-11-06"}),
            ("draft_payment_reminders", {"business_name": "Demo Co", "today": "2026-11-06"}),
            ("record_payment", {"customer": "Fern Hollow", "method": "check"}),
            ("add_job", {}),
            ("note_missing_capability", {"need": "send a quote as a PDF", "example": "quote Fern for mulch"}),
            ("what_can_you_do", {}),
            ("search_cells", {"query": "invoice reminders"}),
            ("history", {}),
        ])
        init, tools = out[0]["result"], out[1]["result"]["tools"]
        assert init["serverInfo"]["name"] == "glean-commons" and "NEEDS INPUT" in init["instructions"]
        names = {t["name"] for t in tools}
        assert {"business_status", "create_invoice", "draft_payment_reminders", "search_cells"} <= names
        r = {m["id"]: m for m in out}
        assert "Add offer O1" in text(r[2])
        assert "Invoice #1001 to Fern Hollow: $85.00, due 2026-09-16" in text(r[6])
        assert "Past due:         $85.00" in text(r[7])
        assert "[final]" in text(r[8]) and "Drafts only" in text(r[8])
        assert "paid in full" in text(r[9])
        assert text(r[10]).startswith("NEEDS INPUT: missing customer")
        assert "wishlist" in text(r[11]) and "quote as a PDF" in (books / "wishlist.md").read_text()
        assert "billing clerk: create_invoice" in text(r[12])
        assert "invoice-followup" in text(r[13]) and not r[13]["result"]["isError"]
        if shutil.which("git"):
            assert "Payment P1" in text(r[14]) and "Open the books" in text(r[14])
        assert r[999]["error"]["code"] == -32601
    finally:
        shutil.rmtree(tmp)


if __name__ == "__main__":
    test_conversation()
    print("OK: MCP server end-to-end test passed")
