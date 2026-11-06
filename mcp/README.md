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
| Commons | `what_can_you_do`, `search_cells`, `note_missing_capability` |

The full map of job functions, including the ones not built yet, is in [`cells/small-business-core/JOBS.md`](../cells/small-business-core/JOBS.md).

## Safety

- **Writes are checked first.** A change that would break the books (an unknown customer, a bad date, an overpayment, invoicing a job twice) is refused and nothing is saved.
- **Ambiguity is asked, not guessed.** Tools answer `NEEDS INPUT: …` and the AI asks you.
- **Drafts, not sends.** Nothing is emailed or paid on your behalf.
- **Local only.** The server talks to your AI app over stdin/stdout. It opens no network ports and sends your books nowhere.

## The build loop

When you ask for something no tool does, the AI calls `note_missing_capability`. It's written to `wishlist.md` in your books folder. That wishlist is the queue for the next cells. Build them by following [AGENTS.md](../AGENTS.md), then the server picks them up automatically.

## Add a tool to the server

Ship a `tools.json` in your cell (see [`cells/small-business-core/tools.json`](../cells/small-business-core/tools.json)). Each tool declares `name`, `job`, `reads`, `writes`, `description`, and `inputSchema`. Its Python function takes the books folder first, then the declared arguments, and returns plain text. Tool names must be unique across the commons; the server refuses to start on a clash.
