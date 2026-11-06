# Import with ancestry

How an outside project enters Glean Commons. A human approves every import.

## Pointer first

Start with a pointer, not a copy. Add `upstream/<org>/<repo>/README.md` that says what the project is, links to the source, and names the license. Do not vendor code on the first import.

## Verify the license

Read the upstream license before registering the project. Record the SPDX id, license URL, and copyright line in `commons.json` and in the ledger notes.

## Credit upstream in the ledger

Add `ledger/pending/<id>.json`. Do not append `ledger/contributions.json` yourself. The creator is the upstream author, not the person who filed the pointer. Set `parents` to `glean-commons-repo`, or to the cell this import extends. Put the upstream URL, license, and copyright in `notes`. Add `registry/pending/<id>.json` for the registry object, with `entry_hash` left null. The fold on `main` runs `ledger/add_entry.py` and writes the hash.

## Adaptations are child cells

A local change is a new cell. Its ledger parents include the upstream pointer id. Do not turn the pointer folder into a fork. If code is copied, keep the upstream license notice.

## No-license repos are link-only

If the upstream repo has no license, the import is a link only: URL, a short description, and ledger credit. Do not copy files, snippets, or assets.

## Human approves every import

Agents may draft the pointer, the registry object, and the ledger command. A human approves the import before it lands on `main`.
