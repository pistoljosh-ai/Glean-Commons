# Experiments

A/B (and A/B/n) tests for Glean cells and pipelines. Free, file-based, honest.

## How to declare a test

1. Copy `_template/` to `experiments/<experiment-id>/`.
2. Fill in `experiment.json` (variants, metric, start date).
3. Link it from the parent project in [`commons.json`](../commons.json) under `experiments[]`.
4. Collect per-variant usage events as CSV (see `analyst/sample_events.csv` for the shape).
5. Run:

```bash
python3 analyst/compare.py experiments/<id>/events.csv --metric benefit_hours
```

6. Paste the recommendation into a PR. A human decides. Log the decision in the ledger ([ANALYST.md](../ANALYST.md)).

## Status values

`planned` → `running` → `completed` \| `aborted`

## Result values

`promote` \| `coexist` \| `retire` \| `keep_testing` \| `null` (while running)
