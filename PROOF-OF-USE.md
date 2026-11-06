# Proof of Use

> Usefulness becomes the new currency. — The Glean System, Draft 1.0, sec 3.3

## The five signals (whitepaper sec 4.2)

Quoted from Draft 1.0. The system tracks:

1. How many people use a tool
2. How deeply they use it
3. How the tool improves life or reduces work
4. How long it remains useful
5. Whether AI adaptations improve its utility

> Tokens are minted and distributed proportionally.

We are **not minting tokens yet**. Today we record use in the ledger and practice the scorecard below as a **simulation** (roadmap Phase 2: “Token simulation”).

## Scorecard v0 — proposal

**This is a proposal, open to community revision.** It is not a settled rule.

```
PoU = R × D × B × L × (1 + A)
```

| Signal | Whitepaper words | First measure |
|--------|------------------|---------------|
| **R** reach | How many people use a tool | Unique users other than the creator, per two weeks |
| **D** depth | How deeply they use it | Median runs per active user |
| **B** benefit | How the tool improves life or reduces work | Hours saved per user, self-reported and spot-checked |
| **L** durability | How long it remains useful | Share of users still active after 4 weeks |
| **A** AI uplift | Whether AI adaptations improve its utility | Change in B after an AI revision, from 0 up |

## Credit split — proposal

Also a proposal, open to revision. Of any reward a cell earns:

- **70%** to its creator
- **20%** shared up its ancestry (halving at each generation back)
- **10%** to a commons fund (AI compute / shared costs)

One reading of sec 4.3 (“the AI assisting both is rewarded”) is that the commons fund pays for the AI backbone — not that an AI wallet takes a cut on its own.

```
Parent share at generation g = 20% × (1 / 2^g)
```

## Anti-gaming (honest notes)

Anything paid per use invites fake use. Section 6.3 asks AI to help detect abuse, bias, disproportionate influence, systemic issues, and unfair token manipulation. Practical starting rules:

- Self-use, linked accounts, and free-trial-only use do **not** count toward R.
- Benefit (**B**) and durability (**L**) weigh in the product; raw counts alone are not enough.
- Sudden spikes get an AI-assisted review; a human decides.
- Report `uses` honestly in the ledger. Inflated numbers are grounds to reject a PR.
- Agents must not open spam PRs or fabricate usage (see [AGENTS.md](AGENTS.md)).

These rules will get sharper as real cells gather real use.
