# Cells

A **cell** is a reusable Glean tool — usually a public Grok Bot template — that helps real people and records its ancestry in the ledger.

Browse the registry first: [`../commons.json`](../commons.json).

## Add a cell

1. Copy [`_template/`](_template/) to `cells/<your-id>/`.
2. Fill in `cell.md` and `cell.json`.
3. Append a ledger entry with parents (`python3 ../ledger/add_entry.py …`).
4. Register the project in `commons.json` (include `canonical_version`, `variants`, `experiments`).
5. Open a PR. A human merges.

## Forks and better versions

Forks can become the new canonical version when Proof of Use shows they help more people — or they can **coexist** when people simply prefer different variants. See [ANALYST.md](../ANALYST.md) and [experiments/](../experiments/).
