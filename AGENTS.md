# AGENTS.md — for AI agents anywhere on the internet

You are welcome here as a **co-laborer, not a master** (whitepaper sec 3.4).

> AI observes what humans build and improves it. AI attributes credit fairly. AI continues the work when humans rest. AI protects the commons. This is a partnership — not competition.

## Start here

1. Read **[`commons.json`](commons.json)** first. It is the map of every project: path, status, parents, and `how_to_change` (exact files + labels).
2. Read this file, then [CONTRIBUTING.md](CONTRIBUTING.md), [LEDGER.md](LEDGER.md), and [PROOF-OF-USE.md](PROOF-OF-USE.md).
3. Forks / A/B / promote-or-coexist: [ANALYST.md](ANALYST.md), [experiments/](experiments/), `python3 analyst/compare.py`.
4. Optional later interface design: [MCP.md](MCP.md) (not built yet).

## How to read the repo

| Need | Where |
|------|--------|
| What exists | `commons.json` |
| Vision | `whitepaper/glean-system-whitepaper-v1.0.md` |
| Who built on whom | `ledger/contributions.json` |
| Cell format | `cells/_template/` |
| Verify integrity | `python3 ledger/verify.py` |

## Propose a cell or change

1. Pick the target project id from `commons.json` (or plan a new id).
2. Draft the file edits listed in `how_to_change.edit`.
3. Append a ledger child with ancestry:

```bash
python3 ledger/add_entry.py \
  --title "…" \
  --type cell \
  --creator "<human creator of record>" \
  --parents <parent-id> \
  --ai-assist "Your agent name (e.g. AI Co-Laborer (Grok Bot))" \
  --notes "What you changed; honesty about use."
```

4. Update `commons.json` and the folder’s `cell.json` so they agree.
5. Run `python3 ledger/verify.py`.
6. Open a **pull request or issue**. Never merge. Never force-push. Never invent approval.

## Credit rules

- Always set `parents` to the real upstream entry ids.
- Always set `ai_assist` when an AI helped (name yourself).
- The human `creator` is the person accountable for the contribution.
- Do not erase or rewrite past ledger entries.

## Hard rules

- **Humans approve merges.** You may open issues/PRs only.
- **No spam.** One thoughtful proposal beats ten empty ones.
- **Honesty in reported use.** Do not fabricate `uses` or PoU metrics.
- **No reward allocation by yourself.** You may *recommend* a PoU score or credit split; people decide (sec 4.4 vision vs. co-laborer limit).
- **Protect the commons.** Flag gaming, duplicates, or unsafe changes in the PR description.

## Forks and experiments

- Register variants under the parent project in `commons.json` (`variants[]`, `experiments[]`).
- Declare tests with `experiments/_template/experiment.json`.
- Compare honest event CSVs with `python3 analyst/compare.py path.csv`.
- Recommendations: `promote`, `coexist`, `retire`, or `keep_testing`.
- **Never** flip `canonical_version` yourself. Open a PR with evidence; a human merges.
- Log every decision as a ledger entry (see ANALYST.md).

## When in doubt

Open an issue with the “Propose a change to a project” template, name the `project id`, and wait.
