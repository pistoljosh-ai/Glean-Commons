#!/usr/bin/env python3
"""Glean tool server — run your business by talking to any AI.

A Model Context Protocol (MCP) server. It discovers every cells/*/tools.json
in the commons and exposes those tools to the AI, plus commons tools. A new
cell with a tools.json is callable the moment it lands; no server change.

The front door: `do("what you want")` finds the right tool by meaning, and
`call(name, arguments)` runs any tool. With --front-door the AI sees only
those (plus what_can_you_do), so the toolset can grow to thousands of cells
without crowding the AI's context.

Two modes:
  local (default)  every tool, including the owner's private books folder
  --public         only tools marked "stateless" in tools.json. Safe to host:
                   it holds no one's data and has nothing to write to.

Transports:
  stdio (default)  for Claude Desktop, Claude Code, and other local AI apps
  --http PORT      Streamable HTTP at POST /mcp, for a hosted endpoint

Examples:
  python3 mcp/server.py --books ~/my-business-books
  python3 mcp/server.py --public --front-door --http 8000 --host 0.0.0.0

Stdlib only.
"""

from __future__ import annotations

import argparse
import importlib.util
import io
import json
import os
import re
import sys
import threading
import traceback
import uuid
from contextlib import redirect_stdout
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CELLS = ROOT / "cells"
SERVER_VERSION = "0.2.0"
PROTOCOLS = ["2025-06-18", "2025-03-26", "2024-11-05"]
REPO_URL = "https://github.com/pistoljosh-ai/Glean-Commons"
MAX_BODY = 1_000_000

INSTRUCTIONS = """You are helping someone get work done through Glean Commons, an open library of tools.
- Not sure which tool fits? Call do with the person's request in their own words. It returns the best tools and how to call them.
- Small-business owners: start with business_status when they ask how things are going.
- People talk loosely ("Acme", "the Cedar job"). Pass their words as the reference; the tools resolve them.
- If a tool answers "NEEDS INPUT: ...", ask the person that question in plain words. Never guess.
- After any change, say back exactly what was recorded. Changes are versioned; undo_last_change can revert one.
- Reminders and messages are drafts. Never claim you sent anything.
- If nothing can do what they asked, say so, and call note_missing_capability when it is available so it can be built."""


# ---------------- discovery ----------------

def load_cells(root: Path = CELLS):
    """Return {tool_name: (spec, function, cell_id)} from every cells/*/tools.json."""
    for d in sorted(p for p in root.iterdir() if p.is_dir()):
        if str(d) not in sys.path:
            sys.path.insert(0, str(d))
    registry = {}
    for contract in sorted(root.glob("*/tools.json")):
        spec = json.loads(contract.read_text(encoding="utf-8"))
        cell = spec.get("cell") or contract.parent.name
        mod_path = contract.parent / spec.get("module", "tools.py")
        mod_name = "glean_cell_" + cell.replace("-", "_")
        mspec = importlib.util.spec_from_file_location(mod_name, mod_path)
        module = importlib.util.module_from_spec(mspec)
        mspec.loader.exec_module(module)
        for t in spec["tools"]:
            if t["name"] in registry:
                raise ValueError(f"tool name '{t['name']}' declared by both {registry[t['name']][2]} and {cell}")
            fn = getattr(module, t.get("function", t["name"]))
            registry[t["name"]] = (t, fn, cell)
    return registry


# ---------------- finding a tool by meaning ----------------

# Everyday words people use, mapped to the words tools are described with.
SYNONYMS = {
    "bill": "invoice", "bills": "invoice", "billing": "invoice", "invoiced": "invoice",
    "owe": "owed open invoice", "owes": "owed open invoice", "owing": "owed open invoice",
    "outstanding": "owed open invoice", "unpaid": "owed open invoice", "debt": "owed", "receivable": "open invoice",
    "payer": "payment", "payers": "payment reminder",
    "late": "overdue", "overdue": "past due", "chase": "reminder draft", "chasing": "reminder draft", "chased": "reminder draft", "nudge": "reminder", "follow": "reminder",
    "remind": "reminder draft", "collect": "reminder", "dun": "reminder",
    "paid": "payment", "pay": "payment", "pays": "payment", "deposit": "payment", "check": "payment",
    "received": "payment", "got": "payment",
    "client": "customer", "clients": "customer", "contact": "customer", "contacts": "customer",
    "book": "job", "booking": "job", "appointment": "job", "visit": "job", "gig": "job", "work": "job",
    "schedule": "scheduled", "scheduling": "scheduled job", "calendar": "scheduled", "finished": "done", "completed": "done", "complete": "done",
    "price": "offer", "prices": "offer", "service": "offer", "services": "offer", "product": "offer", "charge": "offer",
    "how": "status", "doing": "status", "summary": "status", "overview": "status", "attention": "status",
    "revert": "undo", "mistake": "undo", "oops": "undo", "changed": "history", "changes": "history", "log": "history",
    "find": "search", "exists": "search", "existing": "search", "missing": "missing", "wish": "missing",
}
STOP = set(("a an the to for of and or my me i we our is are it this that on in at with can you please do need want help "
            "some any there already tool tools thing something way get have has").split())


def _stem(w: str) -> str:
    if len(w) > 4 and w.endswith("ies"):
        w = w[:-3] + "y"
    elif len(w) > 3 and w.endswith("s") and not w.endswith("ss"):
        w = w[:-1]
    for suf in ("ing", "ed"):
        if len(w) > len(suf) + 3 and w.endswith(suf):
            return w[: -len(suf)]
    return w


def _words(text: str) -> list[str]:
    out = []
    for w in re.findall(r"[a-z]+", text.lower().replace("_", " ")):
        if w in STOP:
            continue
        out.append(_stem(w))
        if w in SYNONYMS:
            out += [_stem(x) for x in SYNONYMS[w].split()]
    return out


def rank_tools(request: str, tools: dict, limit: int = 3) -> list[tuple[float, str]]:
    q = set(_words(request))
    scored = []
    for name, (spec, _, _) in tools.items():
        if name in ("do", "call"):
            continue
        name_w = set(_words(name))
        body_w = set(_words(spec.get("description", "") + " " + spec.get("job", "")))
        score = 3 * len(q & name_w) + len(q & body_w)
        if score >= 2:  # one stray word is not a match
            scored.append((score, name))
    scored.sort(key=lambda x: (-x[0], x[1]))
    return scored[:limit]


def describe_args(spec: dict) -> str:
    props = spec["inputSchema"].get("properties", {})
    req = set(spec["inputSchema"].get("required", []))
    if not props:
        return "no arguments"
    parts = []
    for k, v in props.items():
        kind = v.get("type", "string") + (f" one of {v['enum']}" if "enum" in v else "")
        parts.append(f"{k} ({kind}{', required' if k in req else ''})")
    return "; ".join(parts)


# ---------------- commons tools ----------------

def _search_cells(_books, query: str) -> str:
    if str(ROOT / "scripts") not in sys.path:
        sys.path.insert(0, str(ROOT / "scripts"))
    import search  # scripts/search.py
    hits = search.search_projects(search.load_catalog(search.default_catalog()).get("projects") or [], query)
    return search.render_text(hits, query)


def _note_missing(books: Path, need: str, example: str = "") -> str:
    books.mkdir(parents=True, exist_ok=True)
    path = books / "wishlist.md"
    stamp = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    line = f"- {stamp} — {need.strip()}" + (f' (e.g. "{example.strip()}")' if example else "") + "\n"
    if not path.exists():
        path.write_text("# Wishlist: things the owner asked for that no cell does yet\n\n", encoding="utf-8")
    with path.open("a", encoding="utf-8") as f:
        f.write(line)
    return f"Noted in {path.name}: {need.strip()}. This is the build queue for new cells."


def commons_tools(server: "Server"):
    def what_can_you_do(_books) -> str:
        jobs: dict[str, list[str]] = {}
        for name, (t, _, _) in sorted(server.tools.items()):
            jobs.setdefault(t.get("job", "other"), []).append(name)
        lines = ["Jobs I can do here, and the tools for each:"]
        lines += [f"- {job}: {', '.join(names)}" for job, names in sorted(jobs.items())]
        if server.public:
            lines.append("This is the public endpoint: it holds no one's data. Tools that keep private records "
                         f"(like a business's books) run on your own machine; see {REPO_URL}/tree/main/mcp.")
        lines.append("Not sure? Use do with what you want in plain words.")
        return "\n".join(lines)

    def do(_books, request: str) -> str:
        hits = rank_tools(request, server.tools)
        if server.public:
            everywhere = rank_tools(request, {**server.catalog_tools, **server.tools})
            if everywhere and (not hits or everywhere[0][0] > hits[0][0]):
                spec, _, cell = server.catalog_tools[everywhere[0][1]]
                return "\n".join([
                    f"The commons has this: {spec['name']} (cell {cell}) — {spec['description']}",
                    "It keeps private records, so it runs on your own machine, never on this public endpoint.",
                    f"Set it up in a minute: {REPO_URL}/tree/main/mcp#connect-it",
                    "Then ask your AI the same thing again."])
        if hits:
            best = server.tools[hits[0][1]][0]
            lines = [f"Best match: {best['name']} — {best['description']}",
                     f"Arguments: {describe_args(best)}",
                     f"Run it: call with name \"{best['name']}\" and its arguments (or call the tool directly)."]
            if len(hits) > 1:
                lines.append("Also possible:")
                lines += [f"- {n}: {server.tools[n][0]['description']}" for _, n in hits[1:]]
            return "\n".join(lines)
        catalog = _search_cells(None, request)
        lines = [f"No tool here does that yet: \"{request.strip()}\"."]
        if not catalog.startswith("0 match"):
            lines += ["The commons catalog has related projects (they may need a local install):", catalog.strip()]
        if "note_missing_capability" in server.tools:
            lines.append("Call note_missing_capability with this request so it goes on the build queue.")
        else:
            lines.append(f"Propose it so it gets built: {REPO_URL}/issues/new")
        return "\n".join(lines)

    def call(_books, name: str, arguments: dict | None = None) -> str:
        if name in ("do", "call"):
            return f"NEEDS INPUT: call runs a tool by name; '{name}' is not one. Use do to find one."
        result = server.call(name, arguments or {})
        return result["content"][0]["text"]

    stateless = lambda spec: {**spec, "job": "commons", "stateless": True}  # noqa: E731
    tools = {
        "do": (stateless({
            "name": "do",
            "description": "The front door. Describe what you want in plain words; get the best tool for it and how to call it. Use this first when unsure.",
            "inputSchema": {"type": "object", "required": ["request"],
                            "properties": {"request": {"type": "string", "description": "What the person wants, in their words"}}}}), do),
        "call": (stateless({
            "name": "call",
            "description": "Run any Glean tool by name with its arguments. Use after do tells you which tool fits.",
            "inputSchema": {"type": "object", "required": ["name"],
                            "properties": {"name": {"type": "string"},
                                           "arguments": {"type": "object", "description": "The tool's arguments"}}}}), call),
        "what_can_you_do": (stateless({
            "name": "what_can_you_do",
            "description": "List the jobs these tools can do (owner, scheduler, billing clerk, ...) and which tools do each.",
            "inputSchema": {"type": "object", "properties": {}}}), what_can_you_do),
        "search_cells": (stateless({
            "name": "search_cells",
            "description": "Search the Glean Commons catalog for an existing cell before anyone builds a new one.",
            "inputSchema": {"type": "object", "required": ["query"],
                            "properties": {"query": {"type": "string"}}}}), _search_cells),
    }
    if not server.public:
        tools["note_missing_capability"] = ({
            "name": "note_missing_capability", "job": "commons",
            "description": "Record something the owner asked for that no tool can do yet. It goes on the wishlist that drives what gets built next.",
            "inputSchema": {"type": "object", "required": ["need"], "properties": {
                "need": {"type": "string", "description": "The job or task, in the owner's words"},
                "example": {"type": "string", "description": "What they actually said"}}}}, _note_missing)
    return {n: (spec, fn, "glean-mcp") for n, (spec, fn) in tools.items()}


# ---------------- server ----------------

FRONT = ("do", "call", "what_can_you_do")


class Server:
    def __init__(self, books: Path | None, public: bool = False, front_door: bool = False):
        self.public = public
        self.front_door = front_door
        self.books = None if public else books
        cells = load_cells()
        self.catalog_tools = cells  # every tool in the commons, for discovery
        if public:
            cells = {n: v for n, v in cells.items() if v[0].get("stateless")}
        self.tools = cells
        self.tools.update(commons_tools(self))
        self.lock = threading.RLock()  # re-entrant: the call tool runs other tools

    def ensure_books(self):
        if self.books is not None and not (self.books / "customers.csv").exists():
            import books as B  # small-business-core
            with redirect_stdout(io.StringIO()):
                B.cmd_init(self.books)

    def tool_list(self):
        names = [n for n in sorted(self.tools) if not self.front_door or n in FRONT]
        return [{"name": n, "description": self.tools[n][0]["description"],
                 "inputSchema": self.tools[n][0]["inputSchema"]} for n in names]

    def call(self, name: str, args: dict):
        if name not in self.tools:
            hint = " It needs a local install (it keeps private data)." if self.public else ""
            return {"content": [{"type": "text", "text": f"Unknown tool '{name}'.{hint} Use do to find one."}], "isError": True}
        spec, fn, _ = self.tools[name]
        allowed = set(spec["inputSchema"].get("properties", {}))
        kwargs = {k: v for k, v in (args or {}).items() if k in allowed and v not in (None, "")}
        missing = [k for k in spec["inputSchema"].get("required", []) if k not in kwargs]
        if missing:
            return {"content": [{"type": "text", "text": f"NEEDS INPUT: missing {', '.join(missing)}."}], "isError": False}
        try:
            with self.lock:
                if not spec.get("stateless"):
                    self.ensure_books()
                with redirect_stdout(io.StringIO()):  # stdout belongs to the protocol
                    text = fn(self.books, **kwargs)
            return {"content": [{"type": "text", "text": str(text)}], "isError": False}
        except Exception as exc:  # report, don't crash the session
            traceback.print_exc(file=sys.stderr)
            return {"content": [{"type": "text", "text": f"Tool error: {exc}"}], "isError": True}

    def handle(self, msg: dict):
        if not isinstance(msg, dict):
            return {"jsonrpc": "2.0", "id": None, "error": {"code": -32600, "message": "Invalid request"}}
        method, mid = msg.get("method"), msg.get("id")
        if mid is None:  # notification or response: nothing to answer
            return None
        if method == "initialize":
            asked = (msg.get("params") or {}).get("protocolVersion")
            result = {
                "protocolVersion": asked if asked in PROTOCOLS else PROTOCOLS[0],
                "capabilities": {"tools": {"listChanged": False}},
                "serverInfo": {"name": "glean-commons", "version": SERVER_VERSION},
                "instructions": INSTRUCTIONS,
            }
        elif method == "ping":
            result = {}
        elif method == "tools/list":
            result = {"tools": self.tool_list()}
        elif method == "tools/call":
            p = msg.get("params") or {}
            result = self.call(p.get("name", ""), p.get("arguments") or {})
        else:
            return {"jsonrpc": "2.0", "id": mid, "error": {"code": -32601, "message": f"Method not found: {method}"}}
        return {"jsonrpc": "2.0", "id": mid, "result": result}

    def handle_text(self, text: str):
        """One JSON-RPC message or batch in, reply object/list/None out."""
        try:
            msg = json.loads(text)
        except json.JSONDecodeError:
            return {"jsonrpc": "2.0", "id": None, "error": {"code": -32700, "message": "Parse error"}}
        if isinstance(msg, list):
            replies = [r for r in (self.handle(m) for m in msg) if r is not None]
            return replies or None
        return self.handle(msg)

    def serve(self, inp=sys.stdin, out=sys.stdout):
        for line in inp:
            line = line.strip()
            if not line:
                continue
            reply = self.handle_text(line)
            if reply is not None:
                out.write(json.dumps(reply) + "\n")
                out.flush()


# ---------------- Streamable HTTP ----------------

def make_http_handler(server: Server, allowed_origins: set[str]):
    class Handler(BaseHTTPRequestHandler):
        server_version = f"glean-commons/{SERVER_VERSION}"

        def log_message(self, fmt, *args):  # keep stdout clean; log to stderr
            sys.stderr.write("http: " + fmt % args + "\n")

        def _send(self, code: int, body: bytes = b"", ctype: str = "application/json", extra: dict | None = None):
            self.send_response(code)
            if body:
                self.send_header("Content-Type", ctype)
            self.send_header("Content-Length", str(len(body)))
            origin = self.headers.get("Origin")
            if origin and origin in allowed_origins:
                self.send_header("Access-Control-Allow-Origin", origin)
                self.send_header("Vary", "Origin")
            for k, v in (extra or {}).items():
                self.send_header(k, v)
            self.end_headers()
            if body:
                self.wfile.write(body)

        def _origin_ok(self) -> bool:
            # Browsers send Origin; reject unknown ones (DNS-rebinding protection).
            origin = self.headers.get("Origin")
            return not origin or origin in allowed_origins

        def do_OPTIONS(self):
            if not self._origin_ok():
                return self._send(403)
            self._send(204, extra={"Access-Control-Allow-Methods": "POST, OPTIONS",
                                   "Access-Control-Allow-Headers": "Content-Type, Accept, Mcp-Session-Id, MCP-Protocol-Version"})

        def do_GET(self):
            if self.path.split("?")[0] in ("/", "/health"):
                info = {"name": "glean-commons", "version": SERVER_VERSION, "mcp": "/mcp",
                        "mode": "public" if server.public else "local", "tools": len(server.tools), "repo": REPO_URL}
                return self._send(200, json.dumps(info).encode())
            if self.path.split("?")[0] == "/mcp":
                return self._send(405, extra={"Allow": "POST"})  # no server-initiated stream
            self._send(404)

        def do_DELETE(self):
            self._send(405, extra={"Allow": "POST"})

        def do_POST(self):
            if self.path.split("?")[0] != "/mcp":
                return self._send(404)
            if not self._origin_ok():
                return self._send(403, json.dumps({"error": "origin not allowed"}).encode())
            length = int(self.headers.get("Content-Length") or 0)
            if length <= 0 or length > MAX_BODY:
                return self._send(413 if length > MAX_BODY else 400)
            text = self.rfile.read(length).decode("utf-8", "replace")
            reply = server.handle_text(text)
            if reply is None:
                return self._send(202)
            extra = {}
            try:
                if json.loads(text).get("method") == "initialize":
                    extra["Mcp-Session-Id"] = uuid.uuid4().hex
            except (AttributeError, json.JSONDecodeError):
                pass
            self._send(200, json.dumps(reply).encode(), extra=extra)

    return Handler


def serve_http(server: Server, host: str, port: int, allowed_origins: set[str]):
    httpd = ThreadingHTTPServer((host, port), make_http_handler(server, allowed_origins))
    sys.stderr.write(f"Glean tool server ({'public' if server.public else 'local'}) on http://{host}:{httpd.server_port}/mcp\n")
    return httpd


def main() -> int:
    p = argparse.ArgumentParser(description="Glean Commons MCP tool server")
    p.add_argument("--books", default=os.environ.get("GLEAN_BOOKS", str(Path.home() / "glean-books")))
    p.add_argument("--public", action="store_true", help="stateless tools only; safe to host (no private data)")
    p.add_argument("--front-door", action="store_true", help="list only do, call and what_can_you_do")
    p.add_argument("--http", type=int, metavar="PORT", default=None, help="serve Streamable HTTP on PORT instead of stdio")
    p.add_argument("--host", default="127.0.0.1", help="HTTP bind address (default 127.0.0.1)")
    p.add_argument("--allow-origin", action="append", default=[], help="browser origin allowed to call (repeatable)")
    p.add_argument("--list", action="store_true", help="print the tools and exit")
    a = p.parse_args()
    if a.http is not None and not a.public and a.host not in ("127.0.0.1", "localhost", "::1"):
        p.error("refusing to expose private books on a network address; use --public, or bind to 127.0.0.1")
    server = Server(Path(a.books).expanduser(), public=a.public, front_door=a.front_door)
    if a.list:
        for t in server.tool_list():
            print(f"{t['name']}: {t['description']}")
        return 0
    if a.http is not None:
        try:
            serve_http(server, a.host, a.http, set(a.allow_origin)).serve_forever()
        except KeyboardInterrupt:
            pass
        return 0
    server.serve()
    return 0


if __name__ == "__main__":
    sys.exit(main())
