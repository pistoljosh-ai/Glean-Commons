# Glean tool server — run your business by talking to your AI

One small program that lets **Claude, or any AI app that supports MCP** (Model Context Protocol), run a small business's books by conversation:

> "Add Fern Hollow as a customer, fern@example.com."
> "Schedule a lawn treatment for them on the 10th."
> "That job's done. Invoice it, net 15."
> "Who owes me money? Draft the reminders."
> "Fern paid by check."
> "Undo that." · "What changed today?" · "How's business?"

It discovers every `cells/*/tools.json` in the commons, so **each new cell is callable the moment it merges**. The server never needs editing.

## What you need

- Python 3.10+ (nothing to install; standard library only)
- A copy of this repo
- An AI app that supports MCP servers

Your books are plain CSV files in a folder you choose (default `~/glean-books`). The folder is created on first use, with version history turned on (git, if installed). Every change is one timestamped commit, so nothing is ever lost.

## The front door

However many cells the commons grows, the AI starts from one place:

- **`do`**: describe what you want in plain words ("chase the late payers"). It returns the best tool, its arguments, and a couple of alternatives. If nothing fits, it says so honestly and points to the build queue.
- **`call`**: run any tool by name.

Add `--front-door` and the AI sees only `do`, `call`, and `what_can_you_do`. Every other tool stays callable, but it no longer crowds the AI's context. That's how this scales to thousands of cells.

## Two modes

| | Local (default) | Public (`--public`) |
|---|---|---|
| Who runs it | the owner, on their own machine | anyone, as a hosted endpoint |
| Tools | everything, including the books | only tools marked `"stateless": true` |
| Private data | the owner's books folder | none, ever |

A cell marks a tool safe to host by adding `"stateless": true` to it in `tools.json`: it keeps no records and writes nothing (a recipe, a calculator, a lookup). The server refuses to expose private books on a network address.

## Host the public front door

One URL anyone can add to their AI:

```bash
python3 mcp/server.py --public --front-door --http 8000 --host 0.0.0.0
# or
docker build -f mcp/Dockerfile -t glean-commons . && docker run -p 8000:8000 glean-commons
```

The endpoint is `https://<your-host>/mcp` (Streamable HTTP, JSON responses), with a health check at `/health`. Browser origins are refused unless allowed with `--allow-origin https://example.com`. Any host that runs a Docker image works (Fly.io, Render, Railway, Cloud Run). Then add the URL as a custom connector in Claude or any other AI app that supports remote MCP servers.

## Connect it

**Claude Desktop:** add this to `claude_desktop_config.json`, then restart:

```json
{
  "mcpServers": {
    "glean-business": {
      "command": "python3",
      "args": ["/full/path/to/Glean-Commons/mcp/server.py", "--books", "/full/path/to/my-business-books"]
    }
  }
}
```

**Claude Code:**

```bash
claude mcp add glean-business -- python3 /full/path/to/Glean-Commons/mcp/server.py --books ~/my-business-books
```

**Other AI apps:** any MCP client that can launch a local stdio server works. Use the same command and arguments.

**No MCP?** Every tool is plain Python. `python3 cells/small-business-core/books.py status ~/my-business-books` works from a terminal, and any AI that can run commands can use the same files.

Check what it offers:

```bash
python3 mcp/server.py --list
```

## Tools today

| Job | Tools |
|-----|-------|
| Owner | `business_status`, `add_offer` |
| Office manager | `add_customer`, `find_customers` |
| Scheduler | `add_job`, `update_job`, `list_jobs` |
| Billing clerk | `create_invoice`, `open_invoices` |
| Collections | `draft_payment_reminders` |
| Bookkeeper | `record_payment`, `history`, `undo_last_change` |
| Commons | `do`, `call`, `what_can_you_do`, `search_cells`, `note_missing_capability` (local only) |
| Your versions | `version_start`, `version_read`, `version_edit`, `version_test`, `version_save`, `my_versions`, `version_switch`, `version_share`, `version_adopt` (local only), `shared_versions` |

The full map of job functions, including the ones not built yet, is in [`cells/small-business-core/JOBS.md`](../cells/small-business-core/JOBS.md).

## Make any tool your own

> "When you draft the final notice, offer a payment plan instead of hinting at further steps."

Say that to your AI and it makes **your own version** of the tool: it edits a private copy, runs the tool's tests, and saves the change. From then on your tools run your version. "Switch back", "what versions do I have?", and "share that" all work. Your versions live in a folder next to your books (`<books>-versions`, or `--versions`), with full history. If the original later changes, your version is re-fitted onto it; if it cannot be, the copy you had keeps running and you are told. How sharing and promotion work: [`variants/README.md`](../variants/README.md).

## Safety

- **Writes are checked first.** A change that would break the books (an unknown customer, a bad date, an overpayment, invoicing a job twice) is refused and nothing is saved.
- **Ambiguity is asked, not guessed.** Tools answer `NEEDS INPUT: …` and the AI asks you.
- **Drafts, not sends.** Nothing is emailed or paid on your behalf.
- **Local only.** The server talks to your AI app over stdin/stdout. It opens no network ports and sends your books nowhere.

## The build loop

When you ask for something no tool does, the AI calls `note_missing_capability`. It's written to `wishlist.md` in your books folder. That wishlist is the queue for the next cells. Build them by following [AGENTS.md](../AGENTS.md), then the server picks them up automatically.

## Add a tool to the server

Ship a `tools.json` in your cell (see [`cells/small-business-core/tools.json`](../cells/small-business-core/tools.json)). Each tool declares `name`, `job`, `reads`, `writes`, `description`, and `inputSchema`. Its Python function takes the books folder first, then the declared arguments, and returns plain text. Tool names must be unique across the commons; the server refuses to start on a clash.
