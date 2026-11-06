# Upstream: Forward-Future/loopy (Loop Library)

Pointer only. No code from this project is stored in Glean Commons.

**Loopy** is the [Loop Library](https://signals.forwardfuture.com/loop-library/) and an installable Loopy skill, published by [Forward Future](https://github.com/Forward-Future/loopy). A **loop** is a small unit of work with four parts: a goal, a check, a next step, and a stopping point.

## Why it fits Glean

A loop is a cell with Proof of Use built in. Each run yields evidence: the check says whether the step helped, and the stopping point says when to stop. Glean rewards tools by how much they actually help, and this pointer is the ancestry record for that idea. It does not copy the work.

## Upstream

- Repository: https://github.com/Forward-Future/loopy
- Loop Library: https://signals.forwardfuture.com/loop-library/
- License: MIT — https://github.com/Forward-Future/loopy/blob/main/LICENSE
- Copyright: Copyright (c) 2026 Forward Future
- Credit: Forward Future / Matthew Berman (primary commits [@mberman84](https://github.com/mberman84)) and community PR contributors

## No vendored code

Nothing from the upstream repository is copied into this folder. A local adaptation becomes a new cell whose parent is `upstream-forward-future-loopy`. If any upstream code is ever copied, keep the MIT notice and the copyright line above.

- Ledger id: `upstream-forward-future-loopy`
- Registry: [`commons.json`](../../../commons.json)
- Import steps: [`INTAKE.md`](../../../INTAKE.md)
