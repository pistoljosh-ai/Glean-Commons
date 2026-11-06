# Glean Router

Typed decision tree in front of the catalog. It recommends EXACT, ADAPT, COMPOSE, BUILD, or ASK. It does not merge, mint, or copy upstream code.

Design: [ROUTER.md](ROUTER.md). Prior art: [RESEARCH.md](RESEARCH.md).

```bash
python3 router/route.py "agent loop"
python3 router/route.py --demo
python3 router/test_route.py
```

The default catalog is the live [`catalog.json`](../catalog.json). `--demo` uses [sample_catalog.json](sample_catalog.json), which keeps the EXAMPLE cells labeled as examples.

## Sample demo

```
=== DEMO expect EXACT ===
prompt: I need invoice follow-up reminders for unpaid bills
outcome: EXACT
primary: example-invoice-followup score=1.0
why: Strong match to a proven cell — serve the canonical winner in seconds.

=== DEMO expect ADAPT ===
prompt: invoice follow-up emails tailored for a plumbing shop
outcome: ADAPT
primary: example-invoice-followup score=0.6825
parents: ['example-invoice-followup']
why: Close match — fork as a child variant with parent credit; human merges.

=== DEMO expect COMPOSE ===
prompt: schedule plumbing jobs and draft polite confirmation emails
outcome: COMPOSE
primary: example-email-drafter score=0.5016
parents: ['example-email-drafter', 'example-plumbing-scheduler']
why: Two cells cover parts of the ask. Propose a new combined cell with both as parents (credit both).

=== DEMO expect BUILD ===
prompt: translate handwritten Spanish quotes into QuickBooks line items
outcome: BUILD
why: Nothing in the catalog cleared the floor. Draft a new cell; register after human approve.
```
