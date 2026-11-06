# Pending registry fragments

Optional companion to a pending ledger entry. One file: `registry/pending/<id>.json`.

It is the `commons.json` project object for that id. Leave `entry_hash` null. The fold workflow writes the hash from the new ledger row, updates the manifest when `manifest` is set, upserts the object into `commons.json`, and deletes this file.

`parents` must match the pending ledger entry. Do not edit `commons.json` in the pull request.
