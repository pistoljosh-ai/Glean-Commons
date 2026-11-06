# License options

**Chosen Nov 6, 2026:** Apache-2.0 (code) + CC BY-SA 4.0 (docs/media).

Code (scripts, workflows, `*.py`, `*.json` schemas) is Apache-2.0 ([LICENSE](LICENSE)). Whitepaper, docs, diagrams, video, and other media are CC BY-SA 4.0 ([LICENSE-docs](LICENSE-docs)).

## Recommendation

| Material | License | Why |
|----------|---------|-----|
| **Code** (scripts, pipelines, cells’ code) | **Apache-2.0** | Clear attribution; **patent grant**; works well for agents and companies forking tools. |
| **Docs and media** (whitepaper text, diagrams, manifesto, video script) | **CC BY-SA 4.0** | Attribution matches contribution ancestry; **share-alike** keeps derivatives in the commons. |

Together these match the whitepaper’s “every contribution is tracked publicly” and “communities, not corporations, own the tools” without needing a token.

## Alternatives

- **MIT** for code — shorter, very common; weaker patent language than Apache-2.0.
- **CC BY 4.0** for docs — attribution without share-alike (derivatives need not stay open).

## How it was applied

1. `LICENSE` is the Apache License 2.0, with the appendix notice: Copyright 2026 Timmy Gack and Glean Commons contributors.
2. `LICENSE-docs` is the CC BY-SA 4.0 legal code.
3. The README License section states the split.
4. Prefer SPDX identifiers in new source file headers (`SPDX-License-Identifier: Apache-2.0`).
