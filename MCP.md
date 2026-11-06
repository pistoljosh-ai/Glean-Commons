# MCP design (spec only — not built yet)

A short design for an optional, **read-mostly** [Model Context Protocol](https://modelcontextprotocol.io/) server so agents can navigate Glean Commons the way they navigate other tool catalogs.

**Status:** design only. Do not implement until Timmy asks.

## Goals

- Let any MCP-capable agent list projects, inspect one, search, and propose a change.
- Mirror what [`commons.json`](commons.json) already makes obvious to humans.
- Keep **write** paths narrow: proposals only. A human always approves.

## Tools

### `list_projects`

Returns the `projects` array from `commons.json` (id, name, type, path, status, tags).

### `get_project`

Args: `id` (string).  
Returns the full project object, including `how_to_change`, plus the folder `cell.json` if present, and the matching ledger entry (by id or `entry_hash`) when found.

### `search`

Args: `query` (string), optional `type`, optional `tag`.  
Simple text search over name, tags, path, and notes. No ranking ML required for v0.

The future MCP search server will serve [`catalog.json`](catalog.json): the generated catalog of every project, with Proof of Use, ancestry, and `when_to_use`. Until that server exists, use `python3 scripts/search.py`. Do not invent usage numbers the catalog marks as missing.

### `propose_change`

Args:

- `project_id` (string, from `commons.json`, or `new` for a new cell)
- `title` (string)
- `body` (markdown: what, why, parents, AI assist)
- `mode`: `issue` \| `pull_request` (default `issue`)

Behavior:

- Opens a GitHub issue (preferred) or a draft PR against `main`.
- Applies labels from that project’s `how_to_change.labels` when known.
- **Never merges. Never pushes to `main`. Never edits the ledger on the server’s own authority** — the agent or human still runs `add_entry.py` in a branch if files change.
- Returns the issue/PR URL.

## Non-goals (v0)

- No minting, payouts, or PoU scoring inside MCP.
- No delete or rewrite of ledger history.
- No anonymous write without a linked GitHub identity.

## Auth

Read tools: public.  
`propose_change`: GitHub auth with permission to open issues/PRs on the commons repo only.

## Alignment

This is scaffolding for sec 4.4 (“helps users create tools,” “identifies duplicated ideas”) without handing the merge button to an AI. Co-laborer, not master.
