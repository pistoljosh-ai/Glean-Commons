# Cells

A **cell** is a reusable Glean tool — usually a public Grok Bot template — that helps real people and records its ancestry in the ledger.

Browse the registry first: [`../commons.json`](../commons.json).

## Add a cell

1. Copy [`_template/`](_template/) to `cells/<your-id>/`.
2. Fill in `cell.md` and `cell.json`. Leave `entry_hash` null.
3. Add `ledger/pending/<your-id>.json` with the parent ids. Do not edit `ledger/contributions.json`.
4. Add `registry/pending/<your-id>.json` with `canonical_version`, `variants`, and `experiments`. Leave `entry_hash` null. Do not edit `commons.json`.
5. Put tests in `cells/<your-id>/test_*.py`. CI runs those files.
6. Open a PR. A human merges. The fold on `main` writes the hashes and rebuilds the catalog and the dashboard. Do not commit `catalog.json` or `dashboard/`.

## Forks and better versions

Forks can become the new canonical version when Proof of Use shows they help more people — or they can **coexist** when people simply prefer different variants. See [ANALYST.md](../ANALYST.md) and [experiments/](../experiments/).
