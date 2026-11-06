#!/usr/bin/env python3
"""Glean Router v0 — stdlib-only keyword + rules prototype.

Borrows *ideas* (not code) from Aurelio Labs semantic-router:
  routes with explicit utterances/tags, confidence threshold for "no match",
  hybrid keyword weighting, deterministic dispatch in application code.
Primary upstream parent (pointer): https://github.com/aurelio-labs/semantic-router (MIT).
Typed Intent/Match/Decision shapes are inspired by Instructor-style schemas
(https://github.com/567-labs/instructor, MIT) but implemented with dataclasses.

No network. No embeddings. Deterministic. Humans still approve any BUILD/ADAPT registration.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import asdict, dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, Iterable, List, Optional, Sequence, Tuple

# --- Tunable thresholds (themselves A/B-testable; see ROUTER.md) ---
EXACT_THRESHOLD = 0.72
ADAPT_THRESHOLD = 0.45
COMPOSE_PART_THRESHOLD = 0.32
ASK_AMBIGUITY_GAP = 0.08  # if top-2 scores within this gap → ASK
STOPWORDS = {
    "a", "an", "the", "to", "for", "of", "and", "or", "my", "our", "me", "i",
    "need", "want", "help", "please", "with", "a", "on", "in", "is", "it",
    "that", "this", "from", "can", "you", "we", "us", "get", "make", "do",
}

TASK_VERBS = {
    "follow", "followup", "remind", "chase", "schedule", "draft", "write",
    "send", "track", "invoice", "bill", "search", "build", "create", "improve",
    "compare", "promote", "verify", "route", "explain", "video",
}


class Outcome(str, Enum):
    EXACT = "EXACT"
    ADAPT = "ADAPT"
    COMPOSE = "COMPOSE"
    BUILD = "BUILD"
    ASK = "ASK"


@dataclass
class Intent:
    """Parsed ask — anonymizable; store keywords/domain/task, not raw private text by default."""

    keywords: List[str]
    domain: Optional[str]
    task_verb: Optional[str]
    constraints: List[str] = field(default_factory=list)
    raw_prompt_kept: bool = False  # v0 demo may keep prompt; production default False


@dataclass
class Match:
    project_id: str
    name: str
    score: float
    reasons: List[str]
    pou_score: Optional[float]
    uses: int
    tags_hit: List[str]


@dataclass
class Decision:
    outcome: Outcome
    intent: Intent
    primary: Optional[Match]
    secondary: List[Match]
    parents_for_new_cell: List[str]
    clarifying_question: Optional[str]
    rationale: str
    thresholds: dict


def tokenize(text: str) -> List[str]:
    words = re.findall(r"[a-z0-9]+(?:-[a-z0-9]+)?", text.lower())
    return [w for w in words if w not in STOPWORDS and len(w) > 1]


def parse_intent(prompt: str) -> Intent:
    toks = tokenize(prompt)
    # domain heuristics (v0 rules; replaceable by typed classifier later)
    domain = None
    joined = " ".join(toks)
    domain_rules = [
        ("invoice", ("invoice", "billing", "receivable", "unpaid", "ar")),
        ("plumbing", ("plumbing", "plumber", "pipe", "drain")),
        ("scheduling", ("schedule", "appointment", "booking")),
        ("email", ("email", "mail", "draft")),
        ("video", ("video", "explainer", "remotion", "shorts")),
        ("ledger", ("ledger", "hash", "ancestry", "contribution")),
        ("routing", ("route", "router", "catalog", "search", "commons")),
        ("loops", ("loop", "loopy", "agent", "skill")),
    ]
    for name, keys in domain_rules:
        if any(k in toks or k in joined for k in keys):
            domain = name
            break
    task_verb = next((t for t in toks if t in TASK_VERBS or t.rstrip("s") in TASK_VERBS), None)
    constraints: List[str] = []
    if "plumbing" in toks or "plumber" in toks:
        constraints.append("trades:plumbing")
    if "small" in toks and "business" in toks:
        constraints.append("segment:small-business")
    return Intent(keywords=toks, domain=domain, task_verb=task_verb, constraints=constraints)


def _pou(p: dict) -> Optional[float]:
    pou = p.get("pou")
    if pou is None:
        pou = p.get("proof_of_use")
    if pou is None and "pou_score" in p:
        pou = p.get("pou_score")
    if pou is None:
        return None
    if isinstance(pou, dict):
        score = pou.get("score")
        if score is None:
            return None
        try:
            return float(score)
        except (TypeError, ValueError):
            return None
    try:
        return float(pou)
    except (TypeError, ValueError):
        return None


def normalize_project(project: dict) -> dict:
    """Live catalog.json names, with earlier assumed aliases still accepted.

    Live fields: id, name, summary, tags, when_to_use, uses, pou.{score,reason,components}.
    Sample fixture uses the same names. Aliases cover title/description/proof_of_use.
    """
    tags = project.get("tags")
    if tags is None:
        tags = project.get("tag")
    if isinstance(tags, str):
        tags = [tags]
    uses = project.get("uses")
    if uses is None:
        uses = project.get("use_count") or 0
    pid = project.get("id") or project.get("project_id")
    return {
        "id": pid,
        "name": project.get("name") or project.get("title") or pid,
        "summary": project.get("summary") if project.get("summary") is not None else (project.get("description") or ""),
        "when_to_use": project.get("when_to_use") or project.get("when") or "",
        "tags": list(tags or []),
        "pou": project.get("pou") if "pou" in project else project.get("proof_of_use", project.get("pou_score")),
        "uses": uses,
    }


def score_project(intent: Intent, project: dict) -> Match:
    """Keyword overlap over name/summary/tags/when_to_use; PoU and uses as light boosts.

    Idea kinship with semantic-router hybrid: exact token hits matter, then rank.
    """
    project = normalize_project(project)
    hay = " ".join(
        [
            project.get("id") or "",
            project.get("name") or "",
            project.get("summary") or "",
            project.get("when_to_use") or "",
            " ".join(project.get("tags") or []),
        ]
    ).lower()
    hay_tokens = set(tokenize(hay))
    tags = [t.lower() for t in (project.get("tags") or [])]
    reasons: List[str] = []
    tags_hit: List[str] = []
    if not intent.keywords:
        return Match(
            project_id=project["id"],
            name=project.get("name") or project["id"],
            score=0.0,
            reasons=["empty intent"],
            pou_score=_pou(project),
            uses=int(project.get("uses") or 0),
            tags_hit=[],
        )

    hits = [k for k in intent.keywords if k in hay_tokens or any(k in t for t in tags)]
    hit_ratio = len(hits) / max(len(set(intent.keywords)), 1)
    for k in hits:
        for t in tags:
            if k == t or k in t:
                tags_hit.append(t)
    tags_hit = sorted(set(tags_hit))
    score = hit_ratio
    if intent.domain and intent.domain in hay:
        score += 0.18
        reasons.append(f"domain:{intent.domain}")
    if intent.task_verb and intent.task_verb in hay_tokens:
        score += 0.08
        reasons.append(f"verb:{intent.task_verb}")
    for c in intent.constraints:
        if "plumbing" in c and ("plumbing" in hay or "trades" in hay):
            score += 0.1
            reasons.append("constraint:plumbing")
    pou = _pou(project)
    uses = int(project.get("uses") or 0)
    # light PoU/uses tie-break boost (mirrors planned catalog search ranking)
    if pou is not None:
        score += 0.06 * min(max(pou, 0.0), 1.0)
        reasons.append(f"pou:{pou}")
    if uses:
        score += min(0.04, uses / 1000.0)
        reasons.append(f"uses:{uses}")
    if hits:
        reasons.append(f"hits:{','.join(hits[:8])}")
    # clamp
    score = round(min(score, 1.0), 4)
    return Match(
        project_id=project["id"],
        name=project.get("name") or project["id"],
        score=score,
        reasons=reasons,
        pou_score=pou,
        uses=uses,
        tags_hit=tags_hit,
    )



def _unique_keyword_coverage(intent: Intent, a: Match, b: Match, catalog_projects: Sequence[dict]) -> bool:
    """True when each match uniquely covers at least one intent keyword the other misses."""
    by_id = {normalize_project(proj)["id"]: normalize_project(proj) for proj in catalog_projects}

    def covered(m: Match) -> set:
        proj = by_id.get(m.project_id) or {}
        hay = " ".join(
            [
                proj.get("id") or "",
                proj.get("name") or "",
                proj.get("summary") or "",
                proj.get("when_to_use") or "",
                " ".join(proj.get("tags") or []),
            ]
        ).lower()
        toks = set(tokenize(hay))
        return {k for k in intent.keywords if k in toks or any(k in t for t in (proj.get("tags") or []))}

    ca, cb = covered(a), covered(b)
    return bool(ca - cb) and bool(cb - ca)


def _looks_multi_part(intent: Intent) -> bool:
    """Conjunction-style asks (schedule X and draft Y) prefer COMPOSE over ASK."""
    keys = set(intent.keywords)
    multi_signals = {
        "schedule", "schedules", "scheduling", "draft", "write", "email",
        "emails", "invoice", "follow", "followup", "plumbing", "confirm",
        "confirmation", "remind", "reminder",
    }
    return len(keys & multi_signals) >= 2 and len(intent.keywords) >= 4


def classify(intent: Intent, ranked: Sequence[Match], *, multi_part: bool = False, catalog_projects: Sequence[dict] | None = None) -> Decision:
    thr = {
        "exact": EXACT_THRESHOLD,
        "adapt": ADAPT_THRESHOLD,
        "compose_part": COMPOSE_PART_THRESHOLD,
        "ask_gap": ASK_AMBIGUITY_GAP,
    }
    if not ranked or ranked[0].score < COMPOSE_PART_THRESHOLD:
        return Decision(
            outcome=Outcome.BUILD,
            intent=intent,
            primary=None,
            secondary=[],
            parents_for_new_cell=[],
            clarifying_question=None,
            rationale="Nothing in the catalog cleared the floor. Draft a new cell; register after human approve.",
            thresholds=thr,
        )

    top = ranked[0]
    second = ranked[1] if len(ranked) > 1 else None

    if top.score >= EXACT_THRESHOLD and not (
        multi_part and second and second.score >= COMPOSE_PART_THRESHOLD
    ):
        return Decision(
            outcome=Outcome.EXACT,
            intent=intent,
            primary=top,
            secondary=list(ranked[1:3]),
            parents_for_new_cell=[],
            clarifying_question=None,
            rationale="Strong match to a proven cell — serve the canonical winner in seconds.",
            thresholds=thr,
        )

    # COMPOSE before ASK when the ask clearly wants two capabilities
    projects = catalog_projects or []
    if (
        second
        and top.project_id != second.project_id
        and top.score >= COMPOSE_PART_THRESHOLD
        and second.score >= COMPOSE_PART_THRESHOLD
        and top.score < EXACT_THRESHOLD
        and multi_part
        and projects
        and _unique_keyword_coverage(intent, top, second, projects)
    ):
        return Decision(
            outcome=Outcome.COMPOSE,
            intent=intent,
            primary=top,
            secondary=[second],
            parents_for_new_cell=[top.project_id, second.project_id],
            clarifying_question=None,
            rationale=(
                "Two cells cover parts of the ask. Propose a new combined cell "
                "with both as parents (credit both)."
            ),
            thresholds=thr,
        )

    # Ambiguous near-ties → ASK one clarifying question
    if (
        second
        and top.score >= ADAPT_THRESHOLD
        and abs(top.score - second.score) <= ASK_AMBIGUITY_GAP
        and top.project_id != second.project_id
    ):
        q = (
            f"Did you mean '{top.name}' or '{second.name}'? "
            "Say which one (or describe the combo)."
        )
        return Decision(
            outcome=Outcome.ASK,
            intent=intent,
            primary=top,
            secondary=[second],
            parents_for_new_cell=[],
            clarifying_question=q,
            rationale="Top two matches are too close; ask once before acting.",
            thresholds=thr,
        )

    if top.score >= ADAPT_THRESHOLD:
        return Decision(
            outcome=Outcome.ADAPT,
            intent=intent,
            primary=top,
            secondary=list(ranked[1:3]),
            parents_for_new_cell=[top.project_id],
            clarifying_question=None,
            rationale="Close match — fork as a child variant with parent credit; human merges.",
            thresholds=thr,
        )

    return Decision(
        outcome=Outcome.BUILD,
        intent=intent,
        primary=top if top.score > 0 else None,
        secondary=list(ranked[1:3]),
        parents_for_new_cell=[],
        clarifying_question=None,
        rationale="Weak coverage only. Build new; log demand so the wanted board ranks it.",
        thresholds=thr,
    )


def route(prompt: str, catalog: dict) -> Decision:
    intent = parse_intent(prompt)
    projects = [normalize_project(p) for p in (catalog.get("projects") or [])]
    ranked = sorted(
        (score_project(intent, p) for p in projects),
        key=lambda m: (m.score, m.pou_score or 0.0, m.uses),
        reverse=True,
    )
    # Explicit conjunction ("X and Y") is the compose signal; domain adjectives alone → ADAPT.
    multi = " and " in f" {prompt.lower()} "
    return classify(intent, ranked, multi_part=multi, catalog_projects=projects)


def load_catalog(path: Path) -> dict:
    return json.loads(path.read_text())


def decision_to_dict(d: Decision) -> dict:
    return {
        "outcome": d.outcome.value,
        "intent": asdict(d.intent),
        "primary": asdict(d.primary) if d.primary else None,
        "secondary": [asdict(m) for m in d.secondary],
        "parents_for_new_cell": d.parents_for_new_cell,
        "clarifying_question": d.clarifying_question,
        "rationale": d.rationale,
        "thresholds": d.thresholds,
    }


DEMO_PROMPTS = [
    ("EXACT", "I need invoice follow-up reminders for unpaid bills"),
    ("ADAPT", "invoice follow-up emails tailored for a plumbing shop"),
    ("COMPOSE", "schedule plumbing jobs and draft polite confirmation emails"),
    ("BUILD", "translate handwritten Spanish quotes into QuickBooks line items"),
]


def _catalog_path(explicit: Optional[Path], demo: bool) -> Path:
    """Live catalog.json by default. --demo uses the labeled sample fixture."""
    if explicit is not None:
        return explicit
    here = Path(__file__).resolve().parent
    if demo:
        return here / "sample_catalog.json"
    return here.parent / "catalog.json"


def main(argv: Optional[Sequence[str]] = None) -> int:
    ap = argparse.ArgumentParser(description="Glean Router v0 (stdlib keyword rules)")
    ap.add_argument(
        "--catalog",
        type=Path,
        default=None,
        help="Path to catalog.json (default: repo catalog.json; sample_catalog.json with --demo)",
    )
    ap.add_argument("prompt", nargs="?", help="User prompt to route")
    ap.add_argument("--demo", action="store_true", help="Run 4 labeled demo prompts")
    ap.add_argument("--json", action="store_true", help="Print JSON")
    args = ap.parse_args(argv)
    catalog = load_catalog(_catalog_path(args.catalog, args.demo))

    if args.demo:
        results = []
        for expected, prompt in DEMO_PROMPTS:
            d = route(prompt, catalog)
            results.append({"expected_label": expected, "prompt": prompt, "decision": decision_to_dict(d)})
            if not args.json:
                print(f"\n=== DEMO expect {expected} ===")
                print(f"prompt: {prompt}")
                print(f"outcome: {d.outcome.value}")
                if d.primary:
                    print(f"primary: {d.primary.project_id} score={d.primary.score}")
                if d.parents_for_new_cell:
                    print(f"parents: {d.parents_for_new_cell}")
                if d.clarifying_question:
                    print(f"ask: {d.clarifying_question}")
                print(f"why: {d.rationale}")
        if args.json:
            print(json.dumps(results, indent=2))
        return 0

    if not args.prompt:
        ap.print_help()
        return 2
    d = route(args.prompt, catalog)
    if args.json:
        print(json.dumps(decision_to_dict(d), indent=2))
    else:
        print(f"outcome: {d.outcome.value}")
        print(f"keywords: {d.intent.keywords}")
        print(f"domain: {d.intent.domain} verb: {d.intent.task_verb}")
        if d.primary:
            print(f"primary: {d.primary.project_id} ({d.primary.score}) {d.primary.name}")
        for m in d.secondary:
            print(f"  also: {m.project_id} ({m.score})")
        if d.parents_for_new_cell:
            print(f"parents_for_new_cell: {d.parents_for_new_cell}")
        if d.clarifying_question:
            print(f"question: {d.clarifying_question}")
        print(f"rationale: {d.rationale}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
