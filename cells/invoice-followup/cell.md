# Cell: Invoice follow-up drafter

## Purpose

Turns a CSV of open invoices into polite, escalating reminder drafts for the past-due ones, so chasing payment takes minutes instead of an afternoon. It only drafts; a person reads, edits, and sends.

## Who it helps

Owners and office managers at small service businesses (lawn care, pest control, nurseries, trades) who export open invoices from QuickBooks, Square, or their field-service tool. It removes the weekly chore of finding who's late and writing each reminder by hand.

## How to use

```bash
python3 cells/invoice-followup/followup.py invoices.csv --business "Your Business" --out drafts.md
python3 cells/invoice-followup/test_followup.py
```

CSV columns: `invoice, customer, email, amount, due_date (YYYY-MM-DD)`, optional `paid`.

Tiers by days past due: **friendly** (1+), **firm** (15+), **final** (45+). Oldest and largest come first. Paid and not-yet-due rows are skipped.

## Link

- Grok Bot template URL (when published): not published
- Source path in this repo: `cells/invoice-followup/`

## Parents (contribution chain)

- Ledger parent id(s): `glean-commons-repo`
- Brief note on what was inherited: started from `cells/_template/` (which is registered under `glean-commons-repo`). The router returned BUILD and catalog search found no invoice or receivables cell, so this is a new child rather than an adaptation. No upstream code copied.

## AI assistance

- AI that helped (name), or none: Claude (Anthropic, Opus 5.5): cell design, script, tests.

## PoU metrics to track

| Signal | How we will measure it |
|--------|------------------------|
| Reach (R) | Unique businesses other than the creator who ran it, per two weeks |
| Depth (D) | Median runs per active business |
| Benefit (B) | Minutes saved per weekly AR review (self-report + spot check) |
| Durability (L) | Share still running weekly after 4 weeks |
| AI uplift (A) | Change in B after an AI revision of the templates |

No usage recorded yet (`uses: 0`).

## Variants / experiments

- Canonical version: 0.1.0
- Active variants: none
- Experiments (ids under `experiments/`): none. A good first test: softer vs. firmer tier-2 wording, measured by days-to-pay.

## Notes

- Never add auto-send without a human approval step.
- The tier thresholds and wording live at the top of `followup.py` in `TIERS`; fork there.
