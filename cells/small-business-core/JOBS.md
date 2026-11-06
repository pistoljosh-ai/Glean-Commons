# Job functions — what the commons can do for a small business

> Tasks that drain your life — invoices, spreadsheets, scheduling, follow-ups — happen automatically. — The Glean System, Draft 1.0, sec 2

A small business owner does many jobs that bigger companies hire people for. Each job here is a set of callable tools. "Built" means you can do it today by talking to your AI through the [Glean tool server](../../mcp/). The rest is the build queue, in rough order of how much time it gives back.

| Job | What they do | Status | Tools / next cell |
|-----|--------------|--------|-------------------|
| **Owner** | Knows how the business is doing and sets prices | Built | `business_status`, `add_offer` |
| **Office manager** | Keeps customer records straight | Built | `add_customer`, `find_customers` |
| **Scheduler** | Books jobs and tracks them to done | Built (basic) | `add_job`, `update_job`, `list_jobs` · next: calendar view, recurring jobs |
| **Billing clerk** | Turns finished work into invoices | Built | `create_invoice`, `open_invoices` |
| **Collections** | Chases late payments | Built (drafts) | `draft_payment_reminders` |
| **Bookkeeper** | Records money in, keeps history | Built (money in) | `record_payment`, `history`, `undo_last_change` |
| **Estimator** | Writes quotes customers can accept | Next | `quote` cell: line items → quote document → job on acceptance |
| **Purchasing / expenses** | Records money out | Next | needs `expenses.csv` in the schema; then profit per job and per month |
| **Receptionist** | Takes new requests and turns them into jobs | Planned | intake from a message or call notes → customer + quoted job |
| **Dispatcher** | Orders the day's stops | Planned | route a day's scheduled jobs |
| **Marketer** | Brings customers back | Planned | win-back drafts for customers with no recent jobs |
| **Analyst** | Says what's working | Planned | best customers, best offers, slow payers, seasonality |

## Two gaps worth naming

1. **Money out.** The books record money coming in but not money going out, so there's no profit yet. Adding `expenses.csv` is the highest-leverage next step, because the bookkeeper, owner, and analyst jobs all get better at once.
2. **Quotes.** The loop starts at a quote, and right now jobs begin as a typed "quoted" row. A real quote cell closes the front of the loop.

## How a job gets built

1. Someone asks their AI for it. The AI calls `note_missing_capability` and it lands on the wishlist.
2. A builder (human or AI) runs `python3 router/route.py "<the need>"` to check nothing already does it.
3. They build a child cell on the shared books, with a `tools.json`, following [AGENTS.md](../../AGENTS.md).
4. Once merged, the tool server exposes it to every AI with no further work, and this table gets a new "Built" row.
