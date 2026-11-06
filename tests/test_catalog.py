#!/usr/bin/env python3
"""Tests for the catalog builder and search CLI."""

from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import build_catalog  # noqa: E402
import search  # noqa: E402


def _project(pid: str, **extra) -> dict:
    base = {
        "id": pid,
        "name": pid,
        "type": "cell",
        "status": "active",
        "path": f"{pid}/",
        "parents": [],
        "tags": [],
        "uses": 0,
        "summary": "",
        "when_to_use": "",
        "pou": {"score": None, "reason": "no usage data yet", "components": None},
    }
    base.update(extra)
    return base


class SearchTests(unittest.TestCase):
    def test_name_match_outranks_summary_match(self) -> None:
        projects = [
            _project("notes", name="Notes", summary="invoice tips for later"),
            _project("invoice-cell", name="Invoice follow-up"),
        ]
        hits = search.search_projects(projects, "invoice")
        self.assertEqual([hit["id"] for hit in hits], ["invoice-cell", "notes"])
        self.assertGreater(hits[0]["match_score"], hits[1]["match_score"])

    def test_prefix_matches_loops_and_agent_tag(self) -> None:
        projects = [
            _project(
                "upstream-forward-future-loopy",
                name="Upstream: Forward-Future/loopy (Loop Library)",
                type="upstream",
                tags=["upstream", "agent-skills", "loops"],
                summary="Import pointer only.",
            )
        ]
        hits = search.search_projects(projects, "agent loop")
        self.assertEqual(len(hits), 1)
        self.assertGreater(hits[0]["match_score"], 0)

    def test_type_and_tag_filters(self) -> None:
        projects = [
            _project("a", name="Loop cell", type="cell", tags=["loops"]),
            _project("b", name="Loop doc", type="doc", tags=["loops"]),
        ]
        self.assertEqual(
            [hit["id"] for hit in search.search_projects(projects, "loop", type_name="cell")],
            ["a"],
        )
        self.assertEqual(
            [hit["id"] for hit in search.search_projects(projects, "loop", tag="loops")],
            ["a", "b"],
        )
        self.assertEqual(search.search_projects(projects, "loop", tag="missing"), [])

    def test_tie_break_prefers_measured_pou_then_uses(self) -> None:
        projects = [
            _project("low-use", name="Loop tool", uses=1, pou={"score": None, "reason": "no usage data yet"}),
            _project("high-use", name="Loop tool", uses=9, pou={"score": None, "reason": "no usage data yet"}),
            _project("measured", name="Loop tool", uses=0, pou={"score": 2, "reason": None}),
        ]
        hits = search.search_projects(projects, "loop")
        self.assertEqual([hit["id"] for hit in hits], ["measured", "high-use", "low-use"])

    def test_cli_json(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            catalog = {
                "projects": [_project("only", name="Invoice follow-up", summary="send the invoice")],
            }
            path = Path(tmp) / "catalog.json"
            path.write_text(json.dumps(catalog), encoding="utf-8")
            proc = subprocess.run(
                [sys.executable, str(ROOT / "scripts" / "search.py"), "invoice", "--json", "--catalog", str(path)],
                check=True,
                capture_output=True,
                text=True,
            )
            payload = json.loads(proc.stdout)
            self.assertEqual(payload[0]["id"], "only")


class PouTests(unittest.TestCase):
    def test_score_from_complete_events(self) -> None:
        rows = [
            {"user_id": "u1", "benefit_hours": "10", "depth_runs": "5", "still_active_4w": "1", "is_creator": "1", "ai_revision": "0"},
            {"user_id": "u2", "benefit_hours": "2", "depth_runs": "4", "still_active_4w": "1", "is_creator": "0", "ai_revision": "0"},
            {"user_id": "u3", "benefit_hours": "4", "depth_runs": "2", "still_active_4w": "0", "is_creator": "0", "ai_revision": "0"},
            {"user_id": "u4", "benefit_hours": "6", "depth_runs": "6", "still_active_4w": "1", "is_creator": "0", "ai_revision": "1"},
        ]
        result = build_catalog.compute_pou(rows, 14)
        self.assertIsNotNone(result)
        assert result is not None
        self.assertEqual(result["score"], 64)
        self.assertEqual(result["components"]["R"], 3)
        self.assertEqual(result["components"]["D"], 4)
        self.assertEqual(result["components"]["B"], 4)
        self.assertAlmostEqual(result["components"]["L"], 2 / 3, places=6)
        self.assertEqual(result["components"]["A"], 1)
        self.assertIsNone(result["reason"])

    def test_missing_inputs_do_not_invent_a_score(self) -> None:
        rows = [
            {"user_id": "u2", "benefit_hours": "2", "depth_runs": "4", "still_active_4w": "1"},
        ]
        self.assertIsNone(build_catalog.compute_pou(rows, 14))
        self.assertIsNone(build_catalog.compute_pou([], 14))
        self.assertIsNone(build_catalog.compute_pou(rows, 0))


class BuildTests(unittest.TestCase):
    def _fixture(self, root: Path, with_events: bool) -> None:
        projects = [
            {
                "id": "root-doc",
                "name": "Root",
                "type": "whitepaper",
                "status": "published",
                "path": "whitepaper/",
                "manifest": None,
                "parents": [],
                "tags": ["vision"],
                "canonical_version": "1",
                "variants": [],
                "experiments": [],
                "entry_hash": "abc",
                "how_to_change": {"edit": ["whitepaper/vision.md"], "labels": ["type:docs"], "note": "read"},
            },
            {
                "id": "child-tool",
                "name": "Child tool",
                "type": "tool",
                "status": "active",
                "path": "child/",
                "manifest": None,
                "parents": ["root-doc"],
                "tags": ["tool"],
                "canonical_version": "0.1.0",
                "variants": [],
                "experiments": ["exp-measured"] if with_events else [],
                "entry_hash": "def",
                "how_to_change": {"edit": ["child/README.md"], "labels": ["type:tool"], "note": "use"},
            },
        ]
        (root / "commons.json").write_text(
            json.dumps({"schema_version": 1, "projects": projects}, indent=2) + "\n",
            encoding="utf-8",
        )
        entries = [
            {
                "id": "root-doc",
                "title": "Root",
                "uses": 0,
                "notes": "Visionary framework for a human-centered commons.",
                "entry_hash": "abc",
            },
            {
                "id": "child-tool",
                "title": "Child",
                "uses": 4,
                "notes": "A tool that already exists.",
                "entry_hash": "def",
            },
        ]
        ledger = {"schema_version": 1, "tip_hash": "def", "entries": entries}
        ledger_path = root / "ledger"
        ledger_path.mkdir()
        (ledger_path / "contributions.json").write_text(json.dumps(ledger, indent=2) + "\n", encoding="utf-8")
        paper = root / "whitepaper"
        paper.mkdir()
        (paper / "vision.md").write_text(
            "Usefulness becomes the new currency.\n\n"
            "The Glean System is a decentralized, AI-augmented ecosystem built to rebalance human life "
            "around freedom, contribution, and shared prosperity. It proposes a digital commons.\n",
            encoding="utf-8",
        )
        if with_events:
            exp = root / "experiments" / "exp-measured"
            exp.mkdir(parents=True)
            (exp / "experiment.json").write_text(
                json.dumps(
                    {
                        "id": "exp-measured",
                        "project_id": "child-tool",
                        "status": "completed",
                        "start": "2026-01-01",
                        "end": "2026-01-15",
                    }
                ),
                encoding="utf-8",
            )
            (exp / "events.csv").write_text(
                "user_id,benefit_hours,depth_runs,still_active_4w,is_creator,ai_revision\n"
                "u1,10,5,1,1,0\n"
                "u2,2,4,1,0,0\n"
                "u3,4,2,0,0,0\n"
                "u4,6,6,1,0,1\n",
                encoding="utf-8",
            )

    def test_ancestry_children_and_rank(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self._fixture(root, with_events=True)
            before = (root / "ledger" / "contributions.json").read_bytes()
            catalog = build_catalog.build(root)
            self.assertEqual((root / "ledger" / "contributions.json").read_bytes(), before)
            by_id = {item["id"]: item for item in catalog["projects"]}
            self.assertEqual(by_id["child-tool"]["ancestry"], ["root-doc"])
            self.assertEqual(by_id["child-tool"]["parents"], ["root-doc"])
            self.assertEqual(by_id["root-doc"]["children"], ["child-tool"])
            self.assertEqual(by_id["root-doc"]["ancestry"], [])
            self.assertEqual(by_id["child-tool"]["uses"], 4)
            self.assertEqual(by_id["child-tool"]["pou"]["score"], 64)
            self.assertEqual(by_id["root-doc"]["pou"]["score"], None)
            self.assertEqual(by_id["root-doc"]["pou"]["reason"], "no usage data yet")
            self.assertEqual([item["id"] for item in catalog["projects"]], ["child-tool", "root-doc"])
            self.assertEqual(catalog["generated_from"]["ledger_tip"], "def")
            self.assertEqual(catalog["schema_version"], 1)
            again = build_catalog.build(root)
            self.assertEqual(build_catalog.render_json(catalog), build_catalog.render_json(again))

    def test_no_events_stays_unscored(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self._fixture(root, with_events=False)
            catalog = build_catalog.build(root)
            for project in catalog["projects"]:
                self.assertIsNone(project["pou"]["score"])
                self.assertEqual(project["pou"]["reason"], "no usage data yet")

    def test_llms_quotes_the_whitepaper(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self._fixture(root, with_events=False)
            text = build_catalog.render_llms(build_catalog.build(root), root)
            self.assertTrue(text.startswith("# Glean Commons\n"))
            self.assertIn("> Usefulness becomes the new currency.", text)
            self.assertIn("## Instructions for AI agents", text)
            self.assertIn("Never fabricate usage.", text)
            self.assertIn("[catalog.json](catalog.json):", text)
            self.assertIn("[INTAKE.md](INTAKE.md):", text)
            self.assertIn("The Glean System is a decentralized, AI-augmented ecosystem", text)

    def test_live_repo_catalog_matches_builder(self) -> None:
        catalog_path = ROOT / "catalog.json"
        if not catalog_path.is_file():
            self.skipTest("catalog not generated yet")
        built = build_catalog.build(ROOT)
        on_disk = json.loads(catalog_path.read_text(encoding="utf-8"))
        self.assertEqual(built, on_disk)
        self.assertEqual(build_catalog.render_txt(built), (ROOT / "catalog.txt").read_text(encoding="utf-8"))
        self.assertEqual(build_catalog.render_llms(built, ROOT), (ROOT / "llms.txt").read_text(encoding="utf-8"))
        ledger = json.loads((ROOT / "ledger" / "contributions.json").read_text(encoding="utf-8"))
        self.assertEqual(built["generated_from"]["ledger_tip"], ledger["tip_hash"])


if __name__ == "__main__":
    unittest.main()
