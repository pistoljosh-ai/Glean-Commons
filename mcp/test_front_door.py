#!/usr/bin/env python3
"""Tests: the front door (do/call), public mode, and Streamable HTTP. Stdlib only."""

import json
import shutil
import sys
import tempfile
import threading
import urllib.error
import urllib.request
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import server as S  # noqa: E402


def call(srv, name, args=None):
    return srv.call(name, args or {})["content"][0]["text"]


def test_do_routes_everyday_words():
    srv = S.Server(Path(tempfile.mkdtemp()) / "b")
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
        top = S.rank_tools(request, srv.tools)[0][1]
        assert top == tool, (request, top)
    out = call(srv, "do", {"request": "chase the late payers"})
    assert out.startswith("Best match: draft_payment_reminders") and "business_name" in out


def test_do_admits_gaps():
    srv = S.Server(Path(tempfile.mkdtemp()) / "b")
    out = call(srv, "do", {"request": "send a quote to the Garcias"})
    assert out.startswith("No tool here does that yet") and "note_missing_capability" in out


def test_call_runs_tools_and_refuses_recursion():
    tmp = Path(tempfile.mkdtemp())
    try:
        srv = S.Server(tmp / "b")
        assert "Add customer C1: Bob" in call(srv, "call", {"name": "add_customer", "arguments": {"name": "Bob"}})
        assert call(srv, "call", {"name": "do"}).startswith("NEEDS INPUT")
        assert "Unknown tool" in call(srv, "call", {"name": "nope"})
    finally:
        shutil.rmtree(tmp)


def test_front_door_lists_three_tools_but_all_callable():
    tmp = Path(tempfile.mkdtemp())
    try:
        srv = S.Server(tmp / "b", front_door=True)
        assert [t["name"] for t in srv.tool_list()] == ["call", "do", "what_can_you_do"]
        assert "Add offer O1" in call(srv, "add_offer", {"name": "Wash", "price": 50})
    finally:
        shutil.rmtree(tmp)


def test_public_mode_holds_no_data():
    srv = S.Server(Path("/should/never/be/created"), public=True)
    assert srv.books is None
    names = set(srv.tools)
    assert {"do", "call", "search_cells", "what_can_you_do"} <= names
    assert not names & {"add_customer", "record_payment", "business_status", "note_missing_capability"}
    out = call(srv, "add_customer", {"name": "X"})
    assert "Unknown tool" in out and "local install" in out
    assert "public endpoint" in call(srv, "what_can_you_do")
    assert "Propose it" in call(srv, "do", {"request": "send a quote to the Garcias"})
    found = call(srv, "do", {"request": "is there a tool for chasing late invoices?"})
    assert "draft_payment_reminders" in found and "your own machine" in found
    assert not Path("/should/never/be/created").exists()


def test_http_transport():
    srv = S.Server(None, public=True, front_door=True)
    httpd = S.serve_http(srv, "127.0.0.1", 0, {"https://claude.ai"})
    t = threading.Thread(target=httpd.serve_forever, daemon=True)
    t.start()
    base = f"http://127.0.0.1:{httpd.server_port}"

    def post(body, origin=None):
        req = urllib.request.Request(base + "/mcp", data=json.dumps(body).encode(), method="POST",
                                     headers={"Content-Type": "application/json", "Accept": "application/json, text/event-stream",
                                              **({"Origin": origin} if origin else {})})
        try:
            with urllib.request.urlopen(req, timeout=10) as r:
                return r.status, dict(r.headers), r.read().decode()
        except urllib.error.HTTPError as e:
            return e.code, dict(e.headers), e.read().decode()

    try:
        code, hdr, body = post({"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {"protocolVersion": "2025-06-18"}})
        assert code == 200 and hdr.get("Mcp-Session-Id") and json.loads(body)["result"]["serverInfo"]["name"] == "glean-commons"
        code, _, body = post({"jsonrpc": "2.0", "method": "notifications/initialized"})
        assert code == 202 and body == ""
        code, _, body = post({"jsonrpc": "2.0", "id": 2, "method": "tools/list"})
        assert [t["name"] for t in json.loads(body)["result"]["tools"]] == ["call", "do", "what_can_you_do"]
        code, _, body = post([{"jsonrpc": "2.0", "id": 3, "method": "tools/call",
                               "params": {"name": "do", "arguments": {"request": "find an existing cell for invoices"}}},
                              {"jsonrpc": "2.0", "id": 4, "method": "ping"}])
        replies = json.loads(body)
        assert [r["id"] for r in replies] == [3, 4] and "search_cells" in replies[0]["result"]["content"][0]["text"]
        assert post({"jsonrpc": "2.0", "id": 5, "method": "ping"}, origin="https://claude.ai")[0] == 200
        assert post({"jsonrpc": "2.0", "id": 6, "method": "ping"}, origin="https://evil.example")[0] == 403
        with urllib.request.urlopen(base + "/health", timeout=10) as r:
            assert json.loads(r.read())["mode"] == "public"
        try:
            urllib.request.urlopen(base + "/mcp", timeout=10)
            assert False, "GET /mcp should be 405"
        except urllib.error.HTTPError as e:
            assert e.code == 405
    finally:
        httpd.shutdown()


if __name__ == "__main__":
    for name, fn in list(globals().items()):
        if name.startswith("test_"):
            fn()
    print("OK: front door, public mode and HTTP tests passed")
