# Contributing

Thank you for building with us. Humans approve every merge. AI helps; it does not merge.

## Before you change anything

1. Open [`commons.json`](commons.json). Find the project.
2. Read its `how_to_change.edit` list and `labels`.
3. Read the whitepaper ([whitepaper/](whitepaper/)) if your change touches the vision.

## Improve an existing project

1. Fork this repo.
2. Edit only the files listed for that project (or propose adding files in the PR).
3. If the change creates a new version of a cell or idea, append a ledger entry:

```bash
python3 ledger/add_entry.py \
  --title "…" \
  --type cell \
  --creator "Your Name" \
  --parents <parent-id> \
  --ai-assist "…" \
  --notes "What improved."
```

4. Keep `commons.json` and the project's `cell.json` in sync.
5. Run `python3 ledger/verify.py`.
6. Open a pull request. Apply the labels from `how_to_change`.
7. Wait for a human maintainer.

## Propose a new cell

1. Copy [`cells/_template/`](cells/_template/) to `cells/<your-cell-id>/`.
2. Fill in `cell.md` and `cell.json`.
3. Append a ledger entry with the right `parents`.
4. Add the project to `commons.json` with a clear `how_to_change`.
5. Open a PR (or use the “Propose a new cell” issue template first).

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
