# Running a small business — from first principles

> Tasks that drain your life — invoices, spreadsheets, scheduling, follow-ups — happen automatically. — The Glean System, Draft 1.0, sec 2

This is the map the small-business cells grow on. We add **one cell at a time**. Each new cell reads and writes the same **books**, so every cell makes the others more useful. That's how the commons compounds.

## What a small business is

Strip it down and every small business runs one loop:

```
  1 Offer ──► 2 Customer ──► 3 Quote ──► 4 Schedule ──► 5 Do the work
     ▲                                                        │
     │                                                        ▼
  9 Learn ◄── 8 Keep the books ◄── 7 Get paid ◄────── 6 Invoice
```

| # | Stage | The question it answers | Cell |
|---|-------|-------------------------|------|
| 0 | **The books** | What is true about my business right now? | **`small-business-core`** (this cell) |
| 1 | Offer | What do I sell, and for how much? | — |
| 2 | Customer | Who are my customers and how do I reach them? | — |
| 3 | Quote | What will this job cost them? | — |
| 4 | Schedule | When am I doing what? | — |
| 5 | Do the work | What's left to do on this job? | — |
| 6 | Invoice | What do they owe me? | — |
| 7 | Get paid | Who's late, and what do I say? | [`invoice-followup`](../invoice-followup/) |
| 8 | Keep the books | Where did the money go? | — |
| 9 | Learn | What's working? What should I change? | — |

The empty rows are the build queue. Fill them one at a time.

## The first principle: one set of books

Every stage above reads or writes the same few facts. If each tool keeps its own copy, they drift apart and the owner becomes the glue. So the commons keeps **one set of books**: plain CSV files in a folder anyone can open in Excel, Google Sheets, or a text editor.

| File | One row is… | Key |
|------|-------------|-----|
| `customers.csv` | a person or company you serve | `customer_id` |
| `offers.csv` | something you sell, with a price | `offer_id` |
| `jobs.csv` | a piece of work for a customer | `job_id` |
| `invoices.csv` | a bill for a job | `invoice_id` |
| `payments.csv` | money that came in | `payment_id` |

Exact columns live in [`schema.json`](schema.json). Rules:

1. **Record facts, derive the rest.** An invoice isn't "paid" because someone typed `yes`. It's paid because `payments.csv` adds up to its amount. Balances, overdue days and totals are always computed, never stored.
2. **Plain files, no lock-in.** CSV with a header row. No database, no account, no subscription. This is the whitepaper's complaint about tools that become an indirect tax (sec 1).
3. **Every cell declares what it reads and writes.** Then any agent can see how cells connect before building.
4. **Drafts, not actions.** Cells prepare messages, quotes and reports. A human sends them.

## How a new stage cell plugs in

1. Read the books with `books.py` (or the same CSVs).
2. Write only the files your stage owns. A quote cell writes quotes; it doesn't edit payments.
3. If you need a new column or file, change `schema.json` in a PR and say why.
4. Ship a **`tools.json`** that declares each callable tool: name, the job it does, what it reads and writes, a plain description, and an input schema. The Glean tool server picks it up automatically, so the moment your cell merges, anyone can use it by talking to their AI. See this cell's [`tools.json`](tools.json).
5. Add your cell to the table above.
