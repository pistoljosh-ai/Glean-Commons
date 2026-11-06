#!/usr/bin/env python3
"""Quick stdlib tests for Glean Router v0."""
from __future__ import annotations

import unittest
from pathlib import Path

from route import DEMO_PROMPTS, Outcome, load_catalog, route

CATALOG = load_catalog(Path(__file__).resolve().parent / "sample_catalog.json")


class TestRouterDemo(unittest.TestCase):
    def test_demo_outcomes(self):
        for expected, prompt in DEMO_PROMPTS:
            with self.subTest(expected=expected, prompt=prompt):
                d = route(prompt, CATALOG)
                self.assertEqual(d.outcome.value, expected)

    def test_exact_parents_empty(self):
        d = route(DEMO_PROMPTS[0][1], CATALOG)
        self.assertEqual(d.outcome, Outcome.EXACT)
        self.assertEqual(d.parents_for_new_cell, [])
        self.assertIsNotNone(d.primary)

    def test_adapt_parents_single(self):
        d = route(DEMO_PROMPTS[1][1], CATALOG)
        self.assertEqual(d.outcome, Outcome.ADAPT)
        self.assertEqual(len(d.parents_for_new_cell), 1)

    def test_compose_two_parents(self):
        d = route(DEMO_PROMPTS[2][1], CATALOG)
        self.assertEqual(d.outcome, Outcome.COMPOSE)
        self.assertEqual(len(d.parents_for_new_cell), 2)

    def test_build_no_primary_required(self):
        d = route(DEMO_PROMPTS[3][1], CATALOG)
        self.assertEqual(d.outcome, Outcome.BUILD)

    def test_deterministic(self):
        p = DEMO_PROMPTS[0][1]
        a = route(p, CATALOG)
        b = route(p, CATALOG)
        self.assertEqual(a.outcome, b.outcome)
        self.assertEqual(a.primary.score if a.primary else None, b.primary.score if b.primary else None)


if __name__ == "__main__":
    unittest.main()
