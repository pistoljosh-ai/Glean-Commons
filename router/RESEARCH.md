# Router prior-art research (verified 2026-11-06)

Scratch research for Glean Router intake. Licenses checked via GitHub API (`license.spdx_id`) plus raw `LICENSE` file heads where noted. Stars/pushed_at from GitHub API the same day (America/New_York).

## Comparison table

| Project | URL | SPDX (API + LICENSE) | Stars | Last push (UTC) | What it actually routes | Fit for Glean Router |
| --- | --- | --- | --- | --- | --- | --- |
| **aurelio-labs/semantic-router** | https://github.com/aurelio-labs/semantic-router | **MIT** (LICENSE © 2026 Aurelio AI) | 4024 | 2026-10-22 | User utterance → named **Route** (intent/tool) with confidence; hybrid keyword+embedding; threshold for no-match; optional DecisionRouter (TypeSafe Jev) | **Best primary parent.** Closest to “keywords/intent → give user the right cell.” |
| **lm-sys/RouteLLM** | https://github.com/lm-sys/RouteLLM | **Apache-2.0** | 5685 | 2024-08-10 | Query → **strong vs weak LLM** for cost/quality | Related name only. Cost routing, not catalog/cell routing. Cite for learned thresholds (v2), not primary parent. |
| **567-labs/instructor** (was jxnl/instructor) | https://github.com/567-labs/instructor | **MIT** (LICENSE © 2023 Jason Liu) | 14099 | 2026-11-06 | LLM → **typed structured outputs** (Pydantic) | **Best secondary parent** for typed Intent/Match/Decision when an LLM parse is used (v1+). Not a router by itself. |
| **dottxt-ai/outlines** | https://github.com/dottxt-ai/outlines | **Apache-2.0** | 16005 | 2026-09-21 | Constrained / structured generation | Strong typed-output alternative; heavier than we need for v0. Optional later. |
| **BoundaryML/baml** | https://github.com/BoundaryML/baml | **Apache-2.0** | 9488 | 2026-11-06 | DSL for typed agent functions | Interesting for schema-as-code later; not the first intake. |

## TypeSafe / Jev (Timmy’s inspiration)

Verified from public docs (not a GitHub OSS parent we can pointer-import as source):

- TypeSafe’s **Jev** is a “System One” model: fast typed Choice/Score judgments; **application code owns the decision tree** ([docs.typesafe.ai](https://docs.typesafe.ai/concepts/system-one), [intent routing pattern](https://jevwiki.ai/wiki/patterns/intent-routing.md)).
- Aurelio semantic-router v1 **DecisionRouter** can call TypeSafe Jev as a decision model (stated in their README) — which is why Timmy’s “Jev / Typesafe AI decision tree” inspiration and semantic-router line up.
- No public `typesafe` / `jev` source repo was found to import under a permissive SPDX. Treat as **inspiration + optional paid/API decision model**, not a vendored parent.

## Other conventions (verified)

- **llms.txt** — community proposal for AI-readable site indexes: https://llmstxt.org/ (v2 Aug 2026). Adoption ≠ universal consumption; still useful as a curated agent map.
- **MCP Registry** — official preview catalog of MCP servers: https://registry.modelcontextprotocol.io/ (announced 2025-09-08). Pattern: discover tools via registry; humans/clients decide what to run.

## Recommendation

1. **Primary upstream pointer:** `aurelio-labs/semantic-router` (MIT).
2. **Secondary upstream pointer:** `567-labs/instructor` (MIT) for typed schemas when LLM intent parse arrives.
3. **Do not** make RouteLLM the parent of the Glean Router cell — wrong problem — but may inspire **v2 learned routing from PoU outcomes**.
4. **Pointer first** per INTAKE.md. No vendored code until Timmy says yes.
5. **v0 prototype** (`route.py`) is stdlib keyword+rules that **borrows ideas** (explicit routes, confidence thresholds, hybrid keyword weight, deterministic code owns dispatch) from semantic-router — **no copied source**.

