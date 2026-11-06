#!/usr/bin/env python3
"""Ranked keyword search over catalog.json.

Stdlib only.

  python3 scripts/search.py "invoice follow-up"
  python3 scripts/search.py "agent loop" --type upstream --json
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path


def tokenize(text: str) -> list[str]:
    return re.findall(r"[a-z0-9]+", text.lower())


def _match(query_token: str, field_tokens: list[str]) -> bool:
    for token in field_tokens:
        if token == query_token:
            return True
        if len(query_token) >= 4 and token.startswith(query_token):
            return True
    return False


def _pou_key(project: dict) -> tuple:
    score = (project.get("pou") or {}).get("score")
    if score is None:
        return (1, 0.0)
    return (0, -float(score))


def search_projects(
    projects: list[dict],
    query: str,
    type_name: str | None = None,
    tag: str | None = None,
) -> list[dict]:
    """Score name, summary, tags, and when_to_use. Drop non-matches.

    Tie-break is Proof of Use (measured scores before none), then uses, then id.
    """
    query_tokens = tokenize(query)
    want_type = type_name.lower() if type_name else None
    want_tag = tag.lower() if tag else None
    hits: list[dict] = []
    for project in projects:
        if want_type and str(project.get("type") or "").lower() != want_type:
            continue
        tags = [str(item) for item in (project.get("tags") or [])]
        if want_tag and want_tag not in {item.lower() for item in tags}:
            continue
        if not query_tokens:
            continue
        fields = {
            "name": tokenize(str(project.get("name") or "")),
            "summary": tokenize(str(project.get("summary") or "")),
            "tags": tokenize(" ".join(tags)),
            "when_to_use": tokenize(str(project.get("when_to_use") or "")),
        }
        weights = {"name": 5, "summary": 3, "tags": 4, "when_to_use": 2}
        score = 0
        for token in query_tokens:
            for field, weight in weights.items():
                if _match(token, fields[field]):
                    score += weight
        if score <= 0:
            continue
        hit = dict(project)
        hit["match_score"] = score
        hits.append(hit)
    hits.sort(key=lambda item: (-item["match_score"], _pou_key(item), -int(item.get("uses") or 0), item.get("id") or ""))
    return hits


def load_catalog(path: Path) -> dict:
    with path.open(encoding="utf-8") as handle:
        return json.load(handle)


def default_catalog() -> Path:
    cwd = Path.cwd() / "catalog.json"
    if cwd.is_file():
        return cwd
    return Path(__file__).resolve().parents[1] / "catalog.json"


def render_text(hits: list[dict], query: str) -> str:
    if not hits:
        return f'No matches for "{query}".\n'
    lines = [f'{len(hits)} match(es) for "{query}".', ""]
    for index, hit in enumerate(hits, start=1):
        pou = (hit.get("pou") or {}).get("score")
        pou_text = "none" if pou is None else str(pou)
        lines.append(
            f"{index}. {hit.get('id')}  match={hit.get('match_score')}  pou={pou_text}  uses={hit.get('uses')}"
        )
        lines.append(f"   {hit.get('name')}")
        lines.append(f"   {hit.get('when_to_use')}")
        lines.append(f"   path: {hit.get('path')}")
        lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Search the Glean Commons catalog")
    parser.add_argument("query", help="Keywords, for example: invoice follow-up")
    parser.add_argument("--type", dest="type_name", help="Exact project type, such as cell")
    parser.add_argument("--tag", help="Exact tag")
    parser.add_argument("--json", action="store_true", help="Print JSON matches")
    parser.add_argument("--catalog", type=Path, default=None, help="Path to catalog.json")
    args = parser.parse_args(argv)
    path = args.catalog or default_catalog()
    if not path.is_file():
        print(f"catalog not found: {path}", file=sys.stderr)
        return 1
    catalog = load_catalog(path)
    hits = search_projects(catalog.get("projects") or [], args.query, args.type_name, args.tag)
    if args.json:
        print(json.dumps(hits, indent=2, sort_keys=True, ensure_ascii=False))
    else:
        print(render_text(hits, args.query), end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
