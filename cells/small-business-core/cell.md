# Cell: Small Business Core (the books)

## Purpose

The foundation every small-business cell builds on: one shared set of plain CSV "books" (customers, offers, jobs, invoices, payments) plus a script to set them up, check them, and summarize the business. Read [FIRST-PRINCIPLES.md](FIRST-PRINCIPLES.md) for the map of what gets built on top.

## Who it helps

Owners of small service businesses who keep their records in spreadsheets. It also helps every agent building the next small-business cell: the data shape is already decided, so new cells plug in instead of inventing their own.

## How to use

```bash
python3 cells/small-business-core/books.py init  my_books        # empty books with headers
python3 cells/small-business-core/books.py check my_books        # catch typos and broken links
python3 cells/small-business-core/books.py status my_books       # one-screen summary
python3 cells/small-business-core/books.py ar my_books --out ar.csv
python3 cells/invoice-followup/followup.py ar.csv --business "Your Business"
```

`status` shows customers, jobs by stage, money owed, money past due, cash collected this month, and finished jobs that were never invoiced.

### Reads / writes

- **Reads:** all five books files.
- **Writes:** only empty headers on `init`. It never edits your records.
- **Feeds:** `invoice-followup` (via `ar`).

## Link

- Grok Bot template URL (when published): not published
- Source path in this repo: `cells/small-business-core/`

## Parents (contribution chain)

- Ledger parent id(s): `glean-commons-repo`, `invoice-followup`
- Brief note on what was inherited: started from `cells/_template/`. The `ar` export uses `invoice-followup`'s CSV format, so that cell is credited as a parent. No upstream code copied.

## AI assistance

- AI that helped (name), or none: Claude (Anthropic, Opus 5.5): first-principles map, schema, script, tests.

## PoU metrics to track

| Signal | How we will measure it |
|--------|------------------------|
| Reach (R) | Businesses other than the creator keeping books in this format, per two weeks |
| Depth (D) | Number of other cells that read these books (a structural signal) plus median `status` runs per user |
| Benefit (B) | Minutes saved per weekly money review (self-report + spot check) |
| Durability (L) | Share of businesses still updating their books after 4 weeks |
| AI uplift (A) | Change in B after an AI revision |

No usage recorded yet (`uses: 0`).

## Variants / experiments

- Canonical version: 0.1.0
- Active variants: none
- Experiments: none yet

## Notes

- Record facts; derive the rest. Don't add a `paid` or `balance` column; compute it.
- Schema changes go in `schema.json` through a PR, with a reason.
- The sample books are fictional.
