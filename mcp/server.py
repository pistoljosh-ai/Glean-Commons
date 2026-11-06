#!/usr/bin/env python3
"""Glean tool server — run your business by talking to any AI.

A Model Context Protocol (MCP) server over stdio. It discovers every
cells/*/tools.json in the commons and exposes those tools to the AI, plus a
few commons tools (search_cells, what_can_you_do, note_missing_capability).
A new cell with a tools.json is callable the moment it lands; no server change.

Run (most AI apps start this for you from their config):
  GLEAN_BOOKS=~/my-business-books python3 mcp/server.py
  python3 mcp/server.py --books ~/my-business-books

Stdlib only. Line-delimited JSON-RPC 2.0 on stdin/stdout.
"""

from __future__ import annotations

import argparse
import importlib.util
import io
import json
import os
import sys
import traceback
from contextlib import redirect_stdout
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CELLS = ROOT / "cells"
SERVER_VERSION = "0.1.0"
PROTOCOLS = ["2025-06-18", "2025-03-26", "2024-11-05"]

INSTRUCTIONS = """You are helping a small-business owner run their business through the Glean Commons tools.
- Start with business_status when they ask how things are going or what needs attention.
- They talk loosely ("Acme", "the Cedar job"). Pass their words as the reference; the tools resolve them.
- If a tool answers "NEEDS INPUT: ...", ask the owner that question in plain words. Never guess.
- After any change, say back exactly what was recorded. Every change is versioned and undo_last_change can revert it.
- Reminders and messages are drafts. Never claim you sent anything.
- If they ask for something no tool can do, call note_missing_capability so it can be built, then help as best you can."""


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


# ---------------- commons tools ----------------

def _search_cells(_books, query: str) -> str:
    sys.path.insert(0, str(ROOT / "scripts"))
    import search  # scripts/search.py
    hits = search.search_projects(search.load_catalog(search.default_catalog()), query)
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


def commons_tools(registry):
    def what_can_you_do(_books) -> str:
        jobs: dict[str, list[str]] = {}
        for name, (t, _, cell) in sorted(registry.items()):
            jobs.setdefault(t.get("job", "other"), []).append(name)
        lines = ["Jobs I can do for this business, and the tools for each:"]
        lines += [f"- {job}: {', '.join(names)}" for job, names in sorted(jobs.items())]
        lines.append("Anything else: tell me, and I'll note it so a new cell can be built.")
        return "\n".join(lines)

    return {
        "what_can_you_do": ({
            "name": "what_can_you_do", "job": "commons",
            "description": "List the business jobs these tools can do (owner, scheduler, billing clerk, ...) and which tools do each.",
            "inputSchema": {"type": "object", "properties": {}}}, what_can_you_do, "glean-mcp"),
        "search_cells": ({
            "name": "search_cells", "job": "commons",
            "description": "Search the Glean Commons catalog for an existing cell before anyone builds a new one.",
            "inputSchema": {"type": "object", "required": ["query"],
                            "properties": {"query": {"type": "string"}}}}, _search_cells, "glean-mcp"),
        "note_missing_capability": ({
            "name": "note_missing_capability", "job": "commons",
            "description": "Record something the owner asked for that no tool can do yet. It goes on the wishlist that drives what gets built next.",
            "inputSchema": {"type": "object", "required": ["need"], "properties": {
                "need": {"type": "string", "description": "The job or task, in the owner's words"},
                "example": {"type": "string", "description": "What they actually said"}}}}, _note_missing, "glean-mcp"),
    }


# ---------------- server ----------------

class Server:
    def __init__(self, books: Path):
        self.books = books
        self.tools = load_cells()
        self.tools.update(commons_tools(self.tools))

    def ensure_books(self):
        if not (self.books / "customers.csv").exists():
            import books as B  # small-business-core
            with redirect_stdout(io.StringIO()):
                B.cmd_init(self.books)

    def tool_list(self):
        return [{"name": n, "description": t["description"], "inputSchema": t["inputSchema"]}
                for n, (t, _, _) in sorted(self.tools.items())]

    def call(self, name: str, args: dict):
        if name not in self.tools:
            return {"content": [{"type": "text", "text": f"Unknown tool '{name}'."}], "isError": True}
        spec, fn, _ = self.tools[name]
        allowed = set(spec["inputSchema"].get("properties", {}))
        kwargs = {k: v for k, v in (args or {}).items() if k in allowed and v not in (None, "")}
        missing = [k for k in spec["inputSchema"].get("required", []) if k not in kwargs]
        if missing:
            return {"content": [{"type": "text", "text": f"NEEDS INPUT: missing {', '.join(missing)}."}],
                    "isError": False}
        try:
            self.ensure_books()
            with redirect_stdout(io.StringIO()):  # stdout belongs to the protocol
                text = fn(self.books, **kwargs)
            return {"content": [{"type": "text", "text": str(text)}], "isError": False}
        except Exception as exc:  # report, don't crash the session
            traceback.print_exc(file=sys.stderr)
            return {"content": [{"type": "text", "text": f"Tool error: {exc}"}], "isError": True}

    def handle(self, msg: dict):
        method, mid = msg.get("method"), msg.get("id")
        if mid is None:  # notification
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

    def serve(self, inp=sys.stdin, out=sys.stdout):
        for line in inp:
            line = line.strip()
            if not line:
                continue
            try:
                msg = json.loads(line)
            except json.JSONDecodeError:
                reply = {"jsonrpc": "2.0", "id": None, "error": {"code": -32700, "message": "Parse error"}}
            else:
                reply = self.handle(msg)
            if reply is not None:
                out.write(json.dumps(reply) + "\n")
                out.flush()


def main() -> int:
    p = argparse.ArgumentParser(description="Glean Commons MCP tool server (stdio)")
    p.add_argument("--books", default=os.environ.get("GLEAN_BOOKS", str(Path.home() / "glean-books")))
    p.add_argument("--list", action="store_true", help="print the tools and exit")
    a = p.parse_args()
    server = Server(Path(a.books).expanduser())
    if a.list:
        for t in server.tool_list():
            print(f"{t['name']}: {t['description']}")
        return 0
    server.serve()
    return 0


if __name__ == "__main__":
    sys.exit(main())
