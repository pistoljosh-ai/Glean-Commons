# Upstream: opentimestamps/opentimestamps-client

Pointer only. No code from this project is stored in Glean Commons.

**Project:** [opentimestamps/opentimestamps-client](https://github.com/opentimestamps/opentimestamps-client)  
**License:** LGPL-3.0-or-later  
**Original author:** Peter Todd  
**Credit:** Peter Todd and the OpenTimestamps contributors  

The commons uses the `ots` command-line client to anchor the ledger tip in Bitcoin (see [`anchors/`](../../../anchors/) and `scripts/anchor_ledger.py`). CI installs it with `pip install opentimestamps-client` at run time. It is called as a separate program, never imported or copied.

## No vendored code

Nothing from the upstream repository is copied here. If any of it is ever copied, the LGPL-3.0 terms and its copyright notices must come with it.

- Ledger id: `upstream-opentimestamps-client`
- Used by: `parallel-ledger-and-anchors`
- Import steps: [`INTAKE.md`](../../../INTAKE.md)
