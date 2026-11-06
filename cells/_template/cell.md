# Cell: (name)

## Purpose

What problem does this solve in one or two sentences?

## Who it helps

Who uses it (role, context)? What weekly pain does it remove?

## Link

- Grok Bot template URL (when published):
- Source path in this repo:

## Parents (contribution chain)

- Ledger parent id(s):
- Brief note on what was inherited:

## AI assistance

- AI that helped (name), or none:

## PoU metrics to track

| Signal | How we will measure it |
|--------|------------------------|
| Reach (R) | Unique users other than the creator, per two weeks |
| Depth (D) | Median runs per active user |
| Benefit (B) | Hours saved per user (self-report + spot check) |
| Durability (L) | Share still active after 4 weeks |
| AI uplift (A) | Change in B after an AI revision |

## Variants / experiments

- Canonical version:
- Active variants:
- Experiments (ids under `experiments/`):

## Notes

Anything a forker should know.

## Submitting this cell

Do not edit the shared ledger or registry in your pull request. Copy this folder to `cells/<id>/`, leave `entry_hash` null in `cell.json`, and add:

- `ledger/pending/<id>.json` — the contribution, without hashes. See [ledger/pending/README.md](../../ledger/pending/README.md).
- `registry/pending/<id>.json` — the `commons.json` object, with `entry_hash` null.

`python3 ledger/validate_pending.py` checks both. After merge, the fold writes the hash chain, the catalog, and the dashboard. Do not commit those generated files. Put tests in `test_*.py` next to this file so CI runs them.
