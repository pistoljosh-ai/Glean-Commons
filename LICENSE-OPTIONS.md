# License options (not chosen yet)

No `LICENSE` file is in the repo until Timmy picks one. Until then, treat this draft as all rights reserved.

## Recommendation

| Material | License | Why |
|----------|---------|-----|
| **Code** (scripts, pipelines, cells’ code) | **Apache-2.0** | Clear attribution; **patent grant**; works well for agents and companies forking tools. |
| **Docs and media** (whitepaper text, diagrams, manifesto, video script) | **CC BY-SA 4.0** | Attribution matches contribution ancestry; **share-alike** keeps derivatives in the commons. |

Together these match the whitepaper’s “every contribution is tracked publicly” and “communities, not corporations, own the tools” without needing a token.

## Alternatives

- **MIT** for code — shorter, very common; weaker patent language than Apache-2.0.
- **CC BY 4.0** for docs — attribution without share-alike (derivatives need not stay open).

## How to apply later

1. Add `LICENSE` (Apache-2.0) and `LICENSE-DOCUMENTS` (CC BY-SA 4.0), or a short `NOTICE` that points to both.
2. Note the choice in the README and in a ledger entry.
3. Prefer SPDX identifiers in new source file headers (`SPDX-License-Identifier: Apache-2.0`).
