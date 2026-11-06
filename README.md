# Glean Commons

> An open digital commons powered by Proof of Use, where tools, ideas, and services are rewarded by how much they actually help people. AI as co-laborer, not master. Every idea has an ancestry. Built not for machines, companies, or markets, but for humanity.

This repository is the open home of **The Glean System** — Draft 1.0 (2025) by Timmy Gack — and the first working pieces of its digital commons.

**Usefulness becomes the new currency.**

## Start here

**[`commons.json`](commons.json)** is the registry of every project and cell in this repo. Open it first. Each entry tells you:

- what the project is and where it lives
- who maintains it
- which ledger entry it links to
- **exactly which files to edit** and which PR/issue labels to use (`how_to_change`)

Humans and AI agents both start there. Agents: also read [AGENTS.md](AGENTS.md). Optional later MCP design: [MCP.md](MCP.md).

## What this is

From the whitepaper:

> The Glean System is a decentralized, AI-augmented ecosystem built to rebalance human life around freedom, contribution, and shared prosperity… a digital commons powered by Proof of Use — a new economic principle where value is created and distributed based on how much human-helping tools, ideas, and services are actually used.

Core ideas, in the whitepaper's words:

- **Humans first** — human time, dignity, and freedom are the most valuable resources on Earth (sec 3.1).
- **Decentralized ownership** — no single company owns the ecosystem; every contribution is tracked publicly (sec 3.2).
- **Proof of Use** — if you build something and others use it, you earn (sec 3.3).
- **AI as co-laborer, not master** — AI observes, improves, attributes credit, continues the work, and protects the commons (sec 3.4).
- **Contribution chain** — every idea has an ancestry; value flows up the tree (sec 4.3).

## How it works today (three layers)

We are early. No token. No marketplace yet. Three layers that already work:

1. **This repo + open mirrors** — code, history, forks, and the public contribution ledger. Git holds version history; the ledger is a hash-linked chain of who built what on whom (see [CHAIN.md](CHAIN.md)).
2. **Grok Bot templates as "cells"** — the place people actually use tools. A cell is a reusable bot or tool, free to copy, with a ledger entry that names its parents.
3. **Public ledger for use and ancestry** — [LEDGER.md](LEDGER.md) and [ledger/contributions.json](ledger/contributions.json). Later, release hashes can be anchored on a public chain (e.g. OpenTimestamps). On-chain anchoring of hashes only — no mining, no Glean token yet.

## Repo map

| Path | What it is |
|------|------------|
| [commons.json](commons.json) | **Registry — start here** |
| [whitepaper/](whitepaper/) | Draft 1.0, original `.docx`, and diagrams |
| [LEDGER.md](LEDGER.md) / [ledger/](ledger/) | Contribution chain + hash verify/append |
| [CHAIN.md](CHAIN.md) | How git + the hash-linked ledger form a chain |
| [PROOF-OF-USE.md](PROOF-OF-USE.md) | Five signals + proposed scorecard v0 |
| [CONTRIBUTING.md](CONTRIBUTING.md) | How humans fork, improve, and add entries |
| [AGENTS.md](AGENTS.md) | How AI agents plug in agentically |
| [MCP.md](MCP.md) | Optional later MCP server design (spec only) |
| [ANALYST.md](ANALYST.md) | Commons Analyst: forks, A/B tests, promote / coexist |
| [analyst/](analyst/) | `compare.py` + sample events CSV |
| [experiments/](experiments/) | A/B experiment declarations |
| [cells/](cells/) | Cell format and template |
| [video/](video/) | Placeholder for the vision explainer pipeline |
| [LICENSE-OPTIONS.md](LICENSE-OPTIONS.md) | Apache-2.0 (code) + CC BY-SA 4.0 (docs/media) |

## Use or fork a cell

1. Open [commons.json](commons.json) and find the cell (or browse [cells/](cells/)).
2. Copy or fork it. Improve it.
3. Add a new ledger entry with `python3 ledger/add_entry.py …` that lists the parent cell's `id`.
4. Update `commons.json` and the cell's `cell.json` so they stay in sync.
5. Open a pull request with the labels from `how_to_change`. A human merges it.

See [CONTRIBUTING.md](CONTRIBUTING.md). Agents: [AGENTS.md](AGENTS.md).

## Project status

**Honestly early.** This is Phase 1 of the whitepaper roadmap: ideation, foundational AI assistant, open-source repo setup. The whitepaper is here. The ledger is seeded and hash-linked. The cell format and a vision-explainer video pipeline are in progress. Proof of Use rewards are simulated as ledger points — not minted tokens. Everything here is open for community revision.

## Forks, variants, and A/B tests

When a fork helps more people, it can become the new canonical version — or **coexist** when people prefer different variants. The Commons Analyst recommends; humans approve. See [ANALYST.md](ANALYST.md), [experiments/](experiments/), and `python3 analyst/compare.py`.

## Verify

```bash
python3 ledger/verify.py
```

Checks every ledger hash and that `commons.json` agrees with each project's `cell.json`.

## License

Code (scripts, workflows, `*.py`, `*.json` schemas) is Apache-2.0 ([LICENSE](LICENSE)). Whitepaper, docs, diagrams, video, and other media are CC BY-SA 4.0 ([LICENSE-docs](LICENSE-docs)).

---

*"This is the beginning of a new world — one built not for machines, companies, or markets, but for humanity."* — The Glean System, Draft 1.0, sec 9
