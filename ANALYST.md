# Commons Analyst

Spec for the AI that watches the scaffolding — forks, variants, and experiments — and recommends what should become canonical.

Grounded in the whitepaper:

- Sec 4.2: track “whether AI adaptations improve its utility.”
- Sec 4.4: AI “auto-improves tools for usefulness” and “ensures the ecosystem evolves toward maximum benefit for humanity.”
- Sec 3.4: **AI as Co-Laborer, Not Master.** The Analyst recommends. Humans decide.

## Role

The Commons Analyst is a **super analyst over the scaffolding**, not a governor:

1. Notice forks and variants of a cell.
2. Help declare fair A/B (or multi-variant) experiments.
3. Compare honest Proof of Use signals.
4. Recommend one of four decisions.
5. Log the decision as a hash-linked ledger entry with evidence.
6. **Stop.** A human must approve every promotion.

## Lifecycle

```
fork → variant → experiment → decision
```

| Stage | What happens |
|-------|----------------|
| **Fork** | Someone improves a cell. New ledger entry parents the old one. New folder / template link. |
| **Variant** | The fork is registered under the parent project in `commons.json` as a variant (`status`: testing \| candidate \| canonical \| retired). |
| **Experiment** | An A/B (or A/B/n) test is declared under `experiments/` and linked from the project. Traffic or users are split; events are logged. |
| **Decision** | Analyst recommends; human approves; ledger records the outcome. |

## Decision types

| Decision | When | Effect |
|----------|------|--------|
| **promote** | Variant wins **broadly** on the agreed metric(s) | Variant becomes `canonical_version`. Old canonical stays in the ledger and as a retired/archived variant. Ancestry preserved. |
| **coexist** | Variant wins for a **segment or preference**, not everyone | Both stay. Routing by preference / tag (e.g. “short captions” vs “detailed”). Neither erases the other. |
| **retire** | Variant loses clearly, or is harmful / abandoned | Mark `retired`. Keep ledger history. Do not delete. |
| **keep testing** | Not enough data, or too close to call | Extend the experiment. Do not promote. |

## Plain rules (minimum bar)

**Sample size.** Do not recommend `promote` or `retire` with fewer than **30 independent users per variant** (unique humans, not the creator). Below that, the only honest recommendation is `keep testing`. Preference segments for `coexist` need at least **20 users per segment** that prefers it.

**Honest metrics.** Primary metric must map to Proof of Use signals (see [PROOF-OF-USE.md](PROOF-OF-USE.md)): reach, depth, benefit (hours saved), durability, and AI uplift. Say which one is primary **before** the test starts. Do not switch the goalpost after seeing results.

**Anti-gaming.**

- Creator self-use and linked accounts do not count.
- Sudden spikes get flagged; human reviews.
- Fabricated CSVs or `uses` fields are grounds to reject the decision PR.
- The Analyst must show the raw counts, not only a p-value.

**Humans approve every promotion.** The Analyst opens a PR or issue with the recommendation and evidence. Merge = approval. No autonomous rewrite of `canonical_version`.

## Ledger logging

Every decision appends a ledger entry, for example:

```bash
python3 ledger/add_entry.py \
  --title "Decision: promote invoice-followup-v2" \
  --type other \
  --creator "Timmy Gack" \
  --parents invoice-followup-v1,invoice-followup-v2 \
  --ai-assist "Commons Analyst (Grok Bot)" \
  --notes "promote; metric=benefit_hours; n=42/38; see experiments/exp-001; evidence hash …"
```

Include in `notes`: decision type, experiment id, primary metric, sample sizes, and a pointer to the experiment folder.

## Tooling (free, local)

- Declare tests with [`experiments/_template/experiment.json`](experiments/_template/experiment.json).
- Compare event CSVs with [`analyst/compare.py`](analyst/compare.py) (Python 3 stdlib).
- Registry fields live on each project in [`commons.json`](commons.json): `canonical_version`, `variants[]`, `experiments[]`.

## What the Analyst must not do

- Merge PRs or change `canonical_version` without a human.
- Allocate token rewards.
- Hide negative results.
- Pretend preference is universal when the data says `coexist`.
