# Anchors

These files are OpenTimestamps proofs. They are free. Nothing here is a token, a payment, or a secret.

A proof says: these exact bytes existed by a certain time, and they have not changed since. The bytes we stamp are a small text file:

```
ledger_tip: <sha256 of the latest ledger entry>
git_commit: <commit sha>
git_tree: <tree sha>
```

That ties the ledger tip to a git commit. It does not say the entry is true, useful, or approved. It does not say who wrote it. It does not move money.

## Sample already here

`anchors/stamps/00c3f9dae1f9880c42a8c4241427da4098ed174f.txt` records `main` at that commit, including ledger tip `404259c47ec197b569860f3bc15acdfe024f35dc5d8c69cae2f374885c0604f2`. The `.ots` beside it was accepted by public calendars. Bitcoin has not confirmed it yet, so `ots verify` says the attestation is pending and exits non-zero. That means "not in a block yet," not "the file changed." The daily upgrade job commits the Bitcoin proof when it exists.

## Check a proof

Install the open-source client ([opentimestamps-client](https://github.com/opentimestamps/opentimestamps-client)):

```bash
pip install opentimestamps-client
ots verify anchors/stamps/<commit>.txt.ots
```

The `.txt` file must sit next to the `.ots` file, unchanged. `ots verify` prints the time once Bitcoin has confirmed the proof.

A fresh stamp is only a calendar promise. Bitcoin confirmation usually takes a few hours. The scheduled workflow runs `ots upgrade` and commits the stronger proof when it is ready. Until then, verify may say the proof is pending. That is normal.

## What a green verify means

The ledger tip hash and the commit/tree hashes in the text file were committed to a public calendar, and later to Bitcoin, before the time `ots` prints. Anyone can check that without an account.

## What it does not mean

- It is not a review and not a merge approval.
- It is not Proof of Use and not a reward.
- A pending calendar stamp is not a Bitcoin timestamp yet.
- If the `.txt` file changes, verification fails. That is the point.
