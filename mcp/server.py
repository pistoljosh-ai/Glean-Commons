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
sys.path.insert(0, str(ROOT / "variants"))
import engine as V  # noqa: E402  (variants/engine.py: your own version of any tool)
SERVER_VERSION = "0.3.0"
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
- If nothing can do what they asked, say so, and call note_missing_capability when it is available so it can be built.
- If they want a tool to work differently ("stop it doing X", "I'd rather it said Y"), make them their own version: version_start, read and edit the working copy, version_test, version_save. Their version runs for them only, with history and undo. Offer version_share only if they want others to have it.
- Before version_adopt with confirm, show the person what the change does. It is someone else's code."""


# ---------------- discovery ----------------

_OVERLAY_ROOTS: set[Path] = set()  # every versions folder this process has loaded cell code from


def _forget_cell_modules(roots: list[Path]) -> None:
    """Drop cached cell code and its import paths so the next load reads the files again."""
    roots = [str(r.resolve()) for r in roots if r]
    under = lambda p: any(str(p).startswith(r + os.sep) or str(p) == r for r in roots)  # noqa: E731
    for name, mod in list(sys.modules.items()):
        f = getattr(mod, "__file__", None)
        if name.startswith("glean_cell_") or (f and under(Path(f).resolve())):
            del sys.modules[name]
    sys.path[:] = [p for p in sys.path if not (p and under(Path(p).resolve()))]
    importlib.invalidate_caches()


def _load_one(folder: Path, registry: dict, mine: bool) -> None:
    spec = json.loads((folder / "tools.json").read_text(encoding="utf-8"))
    cell = spec.get("cell") or folder.name
    mod_name = "glean_cell_" + cell.replace("-", "_")
    mspec = importlib.util.spec_from_file_location(mod_name, folder / spec.get("module", "tools.py"))
    module = importlib.util.module_from_spec(mspec)
    mspec.loader.exec_module(module)
    found = {}
    for t in spec["tools"]:
        if t["name"] in registry or t["name"] in found:
            raise ValueError(f"tool name '{t['name']}' is declared twice")
        found[t["name"]] = (dict(t, mine=True) if mine else t, getattr(module, t.get("function", t["name"])), cell)
    registry.update(found)


def load_cells(root: Path = CELLS, overlay: dict[str, Path] | None = None, warnings: list[str] | None = None):
    """Return {tool_name: (spec, function, cell_id)} from every cells/*/tools.json.

    overlay maps a cell to the folder holding the person's own version of it.
    If their version fails to load, the original is used and a warning is kept.
    """
    overlay = overlay or {}
    folders = [d for d in sorted(root.iterdir()) if d.is_dir() and not d.name.startswith(("_", "."))]
    for d in folders:
        path = str(overlay.get(d.name, d))
        if path not in sys.path:
            sys.path.insert(0, path)
    registry = {}
    for d in folders:
        mine = overlay.get(d.name)
        if mine and (mine / "tools.json").is_file():
            try:
                _load_one(mine, registry, True)
                continue
            except Exception as exc:  # their version is broken: fall back, do not lose ground
                (warnings if warnings is not None else []).append(
                    f"Your version of {d.name} failed to load ({exc}); running the original instead.")
                sys.path[:] = [p for p in sys.path if p != str(mine)]
                sys.path.insert(0, str(d))
                sys.modules.pop("glean_cell_" + d.name.replace("-", "_"), None)
        if (d / "tools.json").is_file():
            _load_one(d, registry, False)
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
    "customize": "start own version", "customise": "start own version", "tweak": "start own version", "modify": "start own version",
    "differently": "own version", "different": "own version", "instead": "own version", "rather": "own version",
    "adopt": "adopt version", "share": "share version", "publish": "share version",
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
            if "version_start" in server.tools and server.tools[hits[0][1]][2] != "glean-mcp":
                lines.append("Want it to work differently? version_start makes this person their own version of it.")
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


# ---------------- your own version of any tool ----------------

def version_tools(server: "Server"):
    """Speak a change to a tool; keep it, share it, adopt someone else's. Local mode only."""
    vs = server.variants

    def guard(fn, reload=False):
        def run(_books, **kw):
            try:
                out = fn(**kw)
            except V.Problem as p:
                return f"NEEDS INPUT: {p}"
            if reload:
                server.reload()
            return out
        return run

    def cell_of(ref: str) -> str:
        ref = (ref or "").strip()
        if ref in server.catalog_tools:
            return server.catalog_tools[ref][2]
        if ref in vs.cells():
            return ref
        hits = rank_tools(ref, server.catalog_tools, 1)
        if hits:
            return server.catalog_tools[hits[0][1]][2]
        raise V.Problem(f"Which tool do you mean by '{ref}'? Tool families: {', '.join(vs.cells())}.")

    def start(tool: str, wish: str) -> str:
        return vs.start(cell_of(tool), wish)

    def test(tool: str) -> str:
        ok, report = vs.test(cell_of(tool))
        head = {True: "Tests pass with your change.", False: "Tests FAIL with your change.", None: "Nothing to run."}[ok]
        return head + "\n" + report

    def save(tool: str, name: str, author: str = "", ai_assist: str = "", folder: str = "", wish: str = "", commit: str = "") -> str:
        if folder:
            return vs.capture_upstream(folder, name, wish, author, ai_assist, commit, upstream=tool)
        return vs.save(cell_of(tool), name, author, ai_assist)

    def mine() -> str:
        return vs.listing()

    def shared(tool: str = "") -> str:
        rows = [r for r in V.standing() if not tool or tool.lower() in (r["tool"] + " " + r["name"]).lower()]
        if not rows:
            return "No shared versions yet" + (f" for '{tool}'." if tool else ".") + " Be the first: make your own, then share it."
        return "\n".join(f"{r['id']} ({r['tool']}) by {r['author']}: {r['wish']} — {r['next']}" for r in rows)

    T = lambda name, desc, props, required=(), **extra: dict(  # noqa: E731
        {"name": name, "job": "your versions", "description": desc,
         "inputSchema": {"type": "object", "required": list(required), "properties": props}}, **extra)
    S = {"type": "string"}
    tool_arg = {"type": "string", "description": "The tool or tool family, e.g. draft_payment_reminders or invoice-followup"}
    tools = {
        "version_start": (T("version_start", "Start making this person their own version of a tool: say which tool and how they want it to work differently. Opens a private working copy; the original and other people are unaffected.",
                            {"tool": tool_arg, "wish": {"type": "string", "description": "What should be different, in their words"}}, ("tool", "wish")),
                          guard(start)),
        "version_read": (T("version_read", "Read a file from the working copy of a tool being changed.",
                           {"tool": tool_arg, "file": S}, ("tool", "file")),
                         guard(lambda tool, file: vs.read(cell_of(tool), file))),
        "version_edit": (T("version_edit", "Edit a file in the working copy: replace one exact piece of text (find must appear exactly once), or pass content to write the whole file.",
                           {"tool": tool_arg, "file": S, "find": S, "replace": S, "content": S}, ("tool", "file")),
                         guard(lambda tool, file, find="", replace="", content=None: vs.edit(cell_of(tool), file, find, replace, content))),
        "version_test": (T("version_test", "Run the tool's own tests against the working copy.", {"tool": tool_arg}, ("tool",)), guard(test)),
        "version_save": (T("version_save", "Save the change as this person's own version and switch it on. Refuses if the tool's tests fail. Kept in their private history; nothing is shared. For a program outside the commons, pass folder (their local git copy) to save the change as a patch.",
                           {"tool": tool_arg, "name": {"type": "string", "description": "Short name for this version"},
                            "author": {"type": "string", "description": "The person's name"}, "ai_assist": {"type": "string", "description": "Name of the AI that helped"},
                            "folder": {"type": "string", "description": "Only for outside programs: path to their local git copy"},
                            "wish": {"type": "string", "description": "Only with folder: what the change is for"},
                            "commit": {"type": "string", "description": "Only with folder: the commit the change starts from (default: current)"}}, ("tool", "name")),
                         guard(save, reload=True)),
        "my_versions": (T("my_versions", "List this person's own versions of tools, which one is switched on, and any change in progress.", {}), guard(mine)),
        "version_switch": (T("version_switch", "Switch a tool between this person's versions: a version name, 'original', or 'previous' to go back. Nothing is deleted.",
                             {"tool": tool_arg, "to": {"type": "string", "description": "A version name or id, 'original', or 'previous'"}}, ("tool", "to")),
                           guard(lambda tool, to: vs.switch(cell_of(tool), to), reload=True)),
        "version_share": (T("version_share", "Package one of this person's versions as a single file they can send to someone or offer to the commons. Contains only the change, never their data.",
                            {"version": {"type": "string", "description": "Version name or id (default: the one switched on for tool)"},
                             "tool": tool_arg, "author": S, "github_login": S}),
                          guard(lambda version="", tool="", author="", github_login="": vs.share(version, cell_of(tool) if tool else None, author, github_login))),
        "version_adopt": (T("version_adopt", "Try a version someone shared (an id from shared_versions, or a file). Without confirm it only shows what the change does. With confirm it checks the change fits and passes tests, then switches it on.",
                            {"source": {"type": "string", "description": "Shared version id or name, or a path to a version file"},
                             "confirm": {"type": "boolean"}, "folder": {"type": "string", "description": "Only for outside programs: path to their local git copy"}}, ("source",)),
                          guard(lambda source, confirm=False, folder="": vs.adopt(source, bool(confirm), folder), reload=True)),
    }
    tools["shared_versions"] = (T("shared_versions", "List versions of tools that people have shared with the commons, who made each, how many independent people adopted it, and whether it is close to becoming the original.",
                                  {"tool": {"type": "string", "description": "Optional: only versions of this tool"}}, stateless=True),
                                guard(shared))
    if server.public or vs is None:
        tools = {"shared_versions": tools["shared_versions"]}
    return {n: (spec, fn, "glean-mcp") for n, (spec, fn) in tools.items()}


# ---------------- server ----------------

FRONT = ("do", "call", "what_can_you_do")


class Server:
    def __init__(self, books: Path | None, public: bool = False, front_door: bool = False,
                 versions: Path | None = None):
        self.public = public
        self.front_door = front_door
        self.books = None if public else books
        if versions is None and self.books is not None:
            versions = self.books.with_name(self.books.name + "-versions")
        # The person's own versions of tools. Never in public mode. With no folder it only lists.
        self.variants = None if public else V.Variants(versions)
        self.notices: list[str] = []
        self.lock = threading.RLock()  # re-entrant: the call tool runs other tools
        self.tools: dict = {}
        if self.variants is not None and versions is not None and versions.is_dir():
            try:
                self.notices += self.variants.refresh()
            except Exception as exc:  # never let a versions problem stop the server
                self.notices.append(f"Could not check your own versions: {exc}")
        self.reload()

    def reload(self):
        """(Re)read every tool, preferring the person's own version of a cell where one is switched on."""
        with self.lock:
            overlay = self.variants.active_dirs() if self.variants is not None else {}
            if self.variants and self.variants.home:
                _OVERLAY_ROOTS.add(self.variants.home)
            _forget_cell_modules([CELLS, *_OVERLAY_ROOTS])
            cells = load_cells(overlay=overlay, warnings=self.notices)
            self.catalog_tools = cells  # every tool in the commons, for discovery
            if self.public:
                cells = {n: v for n, v in cells.items() if v[0].get("stateless")}
            tools = dict(cells)
            self.tools = tools
            tools.update(commons_tools(self))
            tools.update(version_tools(self))

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
                if self.notices and name not in ("do", "call"):
                    text = "Note: " + " ".join(self.notices) + "\n\n" + str(text)
                    self.notices.clear()
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
    p.add_argument("--versions", default=os.environ.get("GLEAN_VERSIONS", ""),
                   help="folder for your own versions of tools (default: next to the books folder)")
    p.add_argument("--public", action="store_true", help="stateless tools only; safe to host (no private data)")
    p.add_argument("--front-door", action="store_true", help="list only do, call and what_can_you_do")
    p.add_argument("--http", type=int, metavar="PORT", default=None, help="serve Streamable HTTP on PORT instead of stdio")
    p.add_argument("--host", default="127.0.0.1", help="HTTP bind address (default 127.0.0.1)")
    p.add_argument("--allow-origin", action="append", default=[], help="browser origin allowed to call (repeatable)")
    p.add_argument("--list", action="store_true", help="print the tools and exit")
    a = p.parse_args()
    if a.http is not None and not a.public and a.host not in ("127.0.0.1", "localhost", "::1"):
        p.error("refusing to expose private books on a network address; use --public, or bind to 127.0.0.1")
    server = Server(Path(a.books).expanduser(), public=a.public, front_door=a.front_door,
                    versions=Path(a.versions).expanduser() if a.versions else None)
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
