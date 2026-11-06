# The chain (git + ledger)

Plain words for how Glean Commons keeps a tamper-evident history — without a token and without mining.

## Two layers that fit together

**Git** already chains every commit. Each commit has a unique fingerprint (a hash) that includes the fingerprint of the commit before it, the tree of files, the author, and the message. Change a past file and the hashes break. Forks keep full history.

**The contribution ledger** ([ledger/contributions.json](ledger/contributions.json)) is a second, smaller chain about *ideas and cells*:

- Each entry has an `entry_hash` (sha256 of its own contents).
- Each entry points at the previous entry via `prev_hash` (append order).
- Each entry points at its conceptual parents via `parent_hashes` (ancestry / forks).

So: git answers “was this file tree rewritten?” The ledger answers “who built on whom, and has that story been altered?”

## How forks keep ancestry

When you improve a cell, you do not erase the parent. You:

1. Fork or copy the files.
2. Append a **new** ledger entry whose `parents` list the old `id`, and whose `parent_hashes` copy the parent's `entry_hash`.
3. Register the new project in [`commons.json`](commons.json).

The old entry stays. Credit can flow up the tree later, the way section 4.3 describes.

## Signed commits (recommended)

Turn on commit signing (SSH or GPG) for maintainers. Signed commits make “who wrote this” harder to fake on the git side. The ledger still records the human `creator` and any `ai_assist` in plain text.

## Later, optional: anchor release hashes

When a release matters (a cell many people use, a whitepaper version), take the release’s git tag commit hash and/or the ledger `tip_hash` and **timestamp it on a public chain**. That proves “this exact hash existed by this date” without storing the video or the code on-chain.

Recommended starting point (free):

- **[OpenTimestamps](https://opentimestamps.org/)** — anchors into Bitcoin; no new coin, no mining by us.

Alternatives people use for the same idea: other calendar/attestation services, or writing a hash into a public chain’s memo field. Pick one when we have real releases. Until then, git + this ledger is enough.

## What this is not

- Not a Glean token.
- Not mining.
- Not “AI allocates rewards on its own.” Humans approve merges; the ledger only records.

## Check it yourself

```bash
python3 ledger/verify.py
```

Every pull request runs the same check via [`.github/workflows/verify-ledger.yml`](.github/workflows/verify-ledger.yml).
