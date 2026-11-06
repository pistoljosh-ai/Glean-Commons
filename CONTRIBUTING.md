# Contributing

Thank you for building with us. Humans approve every merge. AI helps; it does not merge.

## Before you change anything

1. Open [`commons.json`](commons.json). Find the project.
2. Read its `how_to_change.edit` list and `labels`.
3. Read the whitepaper ([whitepaper/](whitepaper/)) if your change touches the vision.

## Improve an existing project

1. Fork this repo.
2. Edit only the files listed for that project (or propose adding files in the PR).
3. If the change needs a ledger row, add `ledger/pending/<id>.json`. Do not edit `ledger/contributions.json`. The format is in [ledger/pending/README.md](ledger/pending/README.md). Hashes are computed after merge.
4. If the registry text must change, add `registry/pending/<id>.json` instead of editing `commons.json`. Leave `entry_hash` null.
5. Do not commit a rebuilt catalog (`catalog.json`, `catalog.txt`, `llms.txt`) or dashboard (`dashboard/index.html`, `dashboard/data.json`, `dashboard/data/*.csv`). After merge, one job folds the pending rows onto the current tip and rebuilds both.
6. Run `python3 ledger/validate_pending.py` and `python3 ledger/verify.py`.
7. Open a pull request. Apply the labels from `how_to_change`.
8. Wait for a human maintainer.

## Propose a new cell

1. Copy [`cells/_template/`](cells/_template/) to `cells/<your-cell-id>/`.
2. Fill in `cell.md` and `cell.json`. Leave `entry_hash` null.
3. Add `ledger/pending/<your-cell-id>.json` with your `parents`.
4. Add `registry/pending/<your-cell-id>.json` for the `commons.json` object. Leave `entry_hash` null.
5. Open a PR (or use the “Propose a new cell” issue template first).

Pull requests do not append the hash chain. Two open PRs can both be merged; the fold on `main` applies them one at a time so `prev_hash` does not fork.

## Merge queue

GitHub’s merge queue is not available for this repository. The owner is the personal account `pistoljosh-ai` (`owner.type` is `User`). Merge queues exist only for repositories owned by an organization: any public organization repository, or a private repository on GitHub Enterprise Cloud.

This repo therefore does not use a merge queue. The [fold workflow](.github/workflows/fold-ledger.yml) is the serialization: it uses a concurrency group so only one fold runs at a time, and each pending entry is appended onto whatever the tip is at that moment.

If the repository is later transferred to an organization, a maintainer can turn the queue on from Settings → Rules → Rulesets, on `main`, with “Require a merge queue.” CI would also need a `merge_group` trigger. Do not enable that while the owner is a user account. This project does not change branch protection or rulesets.

## Propose without code

Use the issue templates under `.github/ISSUE_TEMPLATE/`:

- **Propose a change to a project** — pick the project id from `commons.json`.
- **Propose a new cell** — describe purpose, who it helps, and parents.

## Rules of the commons

- Credit ancestry. Name parents.
- Name AI assistance when an AI helped.
- Do not overwrite Draft 1.0 of the whitepaper; add a new version file.
- Do not hand-edit `entry_hash`, `prev_hash`, or `parent_hashes`.
- No spam, no fake use counts.
- Be hopeful, practical, and plain.

## License

See [LICENSE-OPTIONS.md](LICENSE-OPTIONS.md). A formal LICENSE is not chosen yet.
