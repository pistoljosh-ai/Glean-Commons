# Contribution ledger

> Every idea has an ancestry. — The Glean System, Draft 1.0, sec 4.3

The machine-readable ledger is [`ledger/contributions.json`](ledger/contributions.json). It is **append-only** and **hash-linked**, so anyone can check that nothing was quietly rewritten. See [CHAIN.md](CHAIN.md) for how this pairs with git.

## Schema (each entry)

| Field | Meaning |
|-------|---------|
| `id` | Stable id (e.g. `whitepaper-v1.0`) |
| `title` | Human title |
| `type` | `whitepaper` \| `repo` \| `cell` \| `video` \| `idea` \| `other` |
| `creator` | Human creator of record |
| `ai_assist` | AI that helped, or `""` |
| `parents` | List of parent entry `id`s |
| `parent_hashes` | Those parents' `entry_hash` values (same order) |
| `created` | ISO 8601 UTC |
| `version` | Semver-ish string |
| `commit` | Optional git commit SHA once published |
| `uses` | Reported use count (honest; start at 0) |
| `notes` | Short free text |
| `prev_hash` | `entry_hash` of the previous entry (or 64 zeros for genesis) |
| `entry_hash` | `sha256` of the entry's canonical JSON **without** `entry_hash` |

Canonical form: UTF-8 JSON object, keys sorted, separators `(',', ':')`, field `entry_hash` excluded before hashing.

The file also has `tip_hash` (hash of the latest entry) and `schema_version`.

## Seed entries

1. **whitepaper-v1.0** — Timmy Gack (root). Draft 1.0 of The Glean System.
2. **glean-commons-repo** — this repository; parent: whitepaper; AI assist: AI Co-Laborer (Grok Bot).
3. **vision-explainer-video** — vision explainer pipeline; parent: whitepaper; AI assist: AI Co-Laborer (Grok Bot).

## How a fork adds a child

1. Improve a cell or doc.
2. Add `ledger/pending/<id>.json` with the same fields `add_entry.py` accepts (`id`, `title`, `type`, `creator`, `parents`, `created`, `version`, `uses`, `notes`, `ai_assist`). Do not include `entry_hash`, `prev_hash`, or `parent_hashes`.
3. If the registry changes, add `registry/pending/<id>.json` and leave `entry_hash` null. Do not edit `commons.json` or `contributions.json` in the PR.
4. Run `python3 ledger/validate_pending.py` and `python3 ledger/verify.py`.
5. Open a PR. A human merges. The fold on `main` calls `add_entry.py` once per pending file, onto the tip at that moment, then rebuilds the catalog and the dashboard. Do not commit those generated files in the PR.

Value is meant to flow “up the tree” to early contributors (whitepaper sec 4.3). The proposed credit split lives in [PROOF-OF-USE.md](PROOF-OF-USE.md) and is open to revision.

## Scripts

- `ledger/verify.py` — recomputes hashes, checks links, checks commons/manifest sync; exits nonzero on tampering.
- `ledger/add_entry.py` — appends one correctly hashed entry onto the current tip. The fold workflow is the caller on `main`. Do not commit its output from a pull request.
- `ledger/validate_pending.py` — checks `ledger/pending` and `registry/pending` without writing the chain.
- `ledger/fold_pending.py` — appends pending entries in `created` then `id` order and removes the files.
