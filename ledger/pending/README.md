# Pending ledger entries

A pull request adds a new contribution here. It does not edit `ledger/contributions.json`.

One file per entry: `ledger/pending/<id>.json`. Do not set `entry_hash`, `prev_hash`, or `parent_hashes`. After merge, the fold workflow appends each file onto the current tip with `ledger/add_entry.py`, in order of `created` then `id`, and deletes the file.

```json
{
  "id": "your-cell-id",
  "title": "Short title",
  "type": "cell",
  "creator": "Your Name",
  "ai_assist": "Name the AI, or leave empty",
  "parents": ["glean-commons-repo"],
  "created": "2026-11-06T12:00:00Z",
  "version": "0.1.0",
  "commit": "",
  "uses": 0,
  "notes": "What this is, and the license if it is an upstream pointer."
}
```

`type` is one of `whitepaper`, `repo`, `cell`, `video`, `idea`, `other`.

`parents` must already be in the chain, or be other pending ids with an earlier `created` time.

Check before you open the PR:

```bash
python3 ledger/validate_pending.py
python3 ledger/verify.py
```
