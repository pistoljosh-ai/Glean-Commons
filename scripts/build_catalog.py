#!/usr/bin/env python3
"""Build the Glean Commons catalog from the registry, manifests, and ledger.

Stdlib only. Reads commons.json, each project's manifest, ledger/contributions.json,
and experiments/ when those files exist. Writes catalog.json, catalog.txt, and
llms.txt. Does not modify the ledger or invent Proof of Use numbers.

Usage (from the repo root):
  python3 scripts/build_catalog.py
"""

from __future__ import annotations

import hashlib
import json
import re
from datetime import date
from pathlib import Path

SCHEMA_VERSION = 1
POU_NO_DATA = "no usage data yet"
QUOTE = "Usefulness becomes the new currency."
ORDER = [
    "measured_before_unmeasured",
    "pou_score_desc",
    "uses_desc",
    "ancestry_depth_desc",
    "id_asc",
]
PLACEHOLDERS = (
    "what problem does this solve",
    "cell: (name)",
    "replace this template",
    "do not run on the template",
)


def load_json(path: Path) -> dict:
    with path.open(encoding="utf-8") as handle:
        return json.load(handle)


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def collapse(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


def plain(text: str) -> str:
    text = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", text)
    text = text.replace("**", "").replace("`", "")
    text = collapse(text)
    if len(text) <= 240:
        return text
    cut = text[:237].rsplit(" ", 1)[0]
    return cut + "..."


def first_paragraph(text: str) -> str:
    lines: list[str] = []
    in_code = False
    for raw in text.splitlines():
        stripped = raw.strip()
        if stripped.startswith("```"):
            in_code = not in_code
            continue
        if in_code or not stripped:
            if lines and not stripped:
                break
            continue
        if stripped.startswith("#") or stripped.startswith("|"):
            continue
        if set(stripped) <= set("-:| "):
            continue
        if stripped.startswith(">"):
            stripped = stripped.lstrip(">").strip()
        if stripped:
            lines.append(stripped)
    return plain(" ".join(lines))


def usable_summary(text: str) -> str:
    summary = first_paragraph(text)
    lowered = summary.lower()
    if not summary or any(snip in lowered for snip in PLACEHOLDERS):
        return ""
    return summary


def read_text(path: Path) -> str:
    if path.is_file():
        return path.read_text(encoding="utf-8")
    return ""


def summary_for(root: Path, project: dict, ledger_by_id: dict[str, dict]) -> str:
    entry = ledger_by_id.get(project.get("id", ""))
    if entry and entry.get("notes"):
        notes = plain(str(entry["notes"]))
        if notes:
            return notes
    manifest = manifest_for(root, project)
    if manifest.get("summary"):
        return plain(str(manifest["summary"]))
    candidates: list[Path] = []
    rel = str(project.get("path") or "").strip()
    folder = root if rel in ("", ".") else root / rel
    if folder.is_dir():
        candidates.append(folder / "README.md")
        candidates.append(folder / "cell.md")
    for item in (project.get("how_to_change") or {}).get("edit") or []:
        path = root / item
        if path.suffix.lower() == ".md":
            candidates.append(path)
    seen: set[Path] = set()
    for path in candidates:
        if path in seen:
            continue
        seen.add(path)
        summary = usable_summary(read_text(path))
        if summary:
            return summary
    return str(project.get("name") or project.get("id") or "Untitled")


def when_to_use(project: dict, manifest: dict) -> str:
    custom = manifest.get("when_to_use") or project.get("when_to_use")
    if custom:
        return plain(str(custom))
    name = project.get("name") or project.get("id")
    kind = project.get("type") or "project"
    status = project.get("status") or "unknown"
    if status == "pointer":
        return (
            f"Use when you need a credited pointer to {name} before adapting it; "
            "do not copy the code, make a child cell."
        )
    if status == "template":
        return f"Use when you are starting a new cell from the shared format ({name})."
    if kind == "whitepaper":
        return f"Use when you need the vision and principles behind the commons ({name})."
    if kind == "tool":
        return f"Use when you need the {name} tool instead of writing a new one."
    return f"Use when you need {name} ({kind}, {status}) instead of building it again."


def manifest_for(root: Path, project: dict) -> dict:
    rel = project.get("manifest")
    if not rel:
        return {}
    path = root / rel
    if not path.is_file():
        return {}
    data = load_json(path)
    return data if isinstance(data, dict) else {}


def upstream_block(project: dict) -> dict | None:
    raw = project.get("upstream")
    if not isinstance(raw, dict) or not raw:
        return None
    return {
        "url": raw.get("url"),
        "license": raw.get("license_spdx") or raw.get("license"),
        "credit": raw.get("author_credit") or raw.get("credit") or raw.get("copyright"),
    }


def ancestry_chain(project_id: str, by_id: dict[str, dict]) -> list[str]:
    """Every ancestor id, nearest parent first, walking up to the roots."""
    chain: list[str] = []
    seen = {project_id}

    def walk(pid: str) -> None:
        project = by_id.get(pid) or {}
        for parent in project.get("parents") or []:
            if parent in seen:
                continue
            seen.add(parent)
            chain.append(parent)
            walk(parent)

    walk(project_id)
    return chain


def ancestry_depth(project_id: str, by_id: dict[str, dict], stack: set[str] | None = None) -> int:
    stack = set(stack or ())
    if project_id in stack:
        return 0
    project = by_id.get(project_id) or {}
    parents = [parent for parent in (project.get("parents") or []) if parent != project_id]
    if not parents:
        return 0
    stack.add(project_id)
    best = 0
    for parent in parents:
        step = 1 if parent not in by_id else 1 + ancestry_depth(parent, by_id, stack)
        best = max(best, step)
    return best


def children_of(project_id: str, projects: list[dict]) -> list[str]:
    found = [
        project["id"]
        for project in projects
        if project_id in (project.get("parents") or [])
    ]
    return sorted(found)


def uses_for(project: dict, ledger_by_id: dict[str, dict]) -> int:
    entry = ledger_by_id.get(project.get("id", ""))
    if not entry:
        return 0
    try:
        return int(entry.get("uses") or 0)
    except (TypeError, ValueError):
        return 0


def load_experiments(root: Path) -> list[dict]:
    folder = root / "experiments"
    if not folder.is_dir():
        return []
    found: list[dict] = []
    for path in sorted(folder.glob("*/experiment.json")):
        data = load_json(path)
        if isinstance(data, dict):
            data["_path"] = str(path.parent.relative_to(root))
            found.append(data)
    return found


def _as_float(value: str | None) -> float | None:
    if value is None or str(value).strip() == "":
        return None
    try:
        return float(value)
    except ValueError:
        return None


def _as_bool(value: str | None) -> bool | None:
    if value is None:
        return None
    token = str(value).strip().lower()
    if token in {"1", "true", "yes", "y"}:
        return True
    if token in {"0", "false", "no", "n"}:
        return False
    return None


def _mean(values: list[float]) -> float:
    return sum(values) / len(values)


def _median(values: list[float]) -> float:
    ordered = sorted(values)
    mid = len(ordered) // 2
    if len(ordered) % 2:
        return ordered[mid]
    return (ordered[mid - 1] + ordered[mid]) / 2


def compute_pou(rows: list[dict], window_days: int) -> dict | None:
    """Proof of Use scorecard v0: R × D × B × L × (1 + A).

    Returns None unless every input the scorecard names is actually present.
    R is unique non-creator users scaled to 14 days. D is the median runs per
    active non-creator user. B is hours saved per those users. L is the share
    still active after 4 weeks. A is the relative change in B after an AI
    revision, clamped at 0. Missing creator flags, windows, or a before/after
    revision means the score is not computable.
    """
    if window_days <= 0 or not rows:
        return None
    parsed: list[dict] = []
    for row in rows:
        user = (row.get("user_id") or "").strip()
        benefit = _as_float(row.get("benefit_hours"))
        depth = _as_float(row.get("depth_runs"))
        active = _as_float(row.get("still_active_4w"))
        creator = _as_bool(row.get("is_creator"))
        revision = _as_bool(row.get("ai_revision"))
        if not user or benefit is None or depth is None or active is None:
            return None
        if creator is None or revision is None:
            return None
        parsed.append(
            {
                "user_id": user,
                "benefit_hours": benefit,
                "depth_runs": depth,
                "still_active_4w": active,
                "is_creator": creator,
                "ai_revision": revision,
            }
        )
    people = [row for row in parsed if not row["is_creator"]]
    if not people:
        return None
    by_user: dict[str, list[dict]] = {}
    for row in people:
        by_user.setdefault(row["user_id"], []).append(row)
    benefits = [_mean([item["benefit_hours"] for item in group]) for group in by_user.values()]
    depths = [_mean([item["depth_runs"] for item in group]) for group in by_user.values()]
    active_flags = [
        1.0 if any(item["still_active_4w"] >= 1 for item in group) else 0.0
        for group in by_user.values()
    ]
    before = [
        _mean([item["benefit_hours"] for item in group])
        for group in by_user.values()
        if not any(item["ai_revision"] for item in group)
    ]
    after = [
        _mean([item["benefit_hours"] for item in group])
        for group in by_user.values()
        if any(item["ai_revision"] for item in group)
    ]
    if not before or not after or _mean(before) <= 0:
        return None
    reach = len(by_user) * (14 / window_days)
    depth = _median(depths)
    benefit = _mean(benefits)
    durability = _mean(active_flags)
    uplift = max(0.0, (_mean(after) - _mean(before)) / _mean(before))
    score = reach * depth * benefit * durability * (1 + uplift)
    return {
        "score": round(score, 6),
        "reason": None,
        "components": {
            "R": round(reach, 6),
            "D": round(depth, 6),
            "B": round(benefit, 6),
            "L": round(durability, 6),
            "A": round(uplift, 6),
        },
    }


def _window_days(experiment: dict) -> int | None:
    start, end = experiment.get("start"), experiment.get("end")
    if not start or not end:
        return None
    try:
        return (date.fromisoformat(str(end)) - date.fromisoformat(str(start))).days
    except ValueError:
        return None


def _event_rows(root: Path, experiment: dict) -> list[dict] | None:
    rel = experiment.get("events")
    path = root / rel if rel else root / experiment.get("_path", "") / "events.csv"
    if not path.is_file():
        return None
    import csv

    with path.open(newline="", encoding="utf-8") as handle:
        return [row for row in csv.DictReader(handle) if any((value or "").strip() for value in row.values())]


def pou_for_project(root: Path, project: dict, experiments: list[dict]) -> dict:
    ids = set(project.get("experiments") or [])
    matched = [
        experiment
        for experiment in experiments
        if experiment.get("id") in ids or experiment.get("project_id") == project.get("id")
    ]
    for experiment in matched:
        status = str(experiment.get("status") or "").lower()
        if status not in {"running", "completed"}:
            continue
        window = _window_days(experiment)
        rows = _event_rows(root, experiment)
        if window is None or rows is None:
            continue
        computed = compute_pou(rows, window)
        if computed is not None:
            return computed
    return {"score": None, "reason": POU_NO_DATA, "components": None}


def project_record(
    root: Path,
    project: dict,
    projects: list[dict],
    by_id: dict[str, dict],
    ledger_by_id: dict[str, dict],
    experiments: list[dict],
) -> dict:
    manifest = manifest_for(root, project)
    summary = summary_for(root, project, ledger_by_id)
    pid = project["id"]
    return {
        "id": pid,
        "name": project.get("name") or pid,
        "type": project.get("type"),
        "status": project.get("status"),
        "summary": summary,
        "tags": list(project.get("tags") or []),
        "path": project.get("path"),
        "upstream": upstream_block(project),
        "parents": list(project.get("parents") or []),
        "ancestry": ancestry_chain(pid, by_id),
        "children": children_of(pid, projects),
        "canonical_version": project.get("canonical_version"),
        "variants": project.get("variants") or [],
        "entry_hash": project.get("entry_hash"),
        "uses": uses_for(project, ledger_by_id),
        "pou": pou_for_project(root, project, experiments),
        "how_to_change": project.get("how_to_change") or {},
        "when_to_use": when_to_use(project, manifest),
        "_depth": ancestry_depth(pid, by_id),
    }


def rank_projects(records: list[dict]) -> list[dict]:
    def key(record: dict) -> tuple:
        score = (record.get("pou") or {}).get("score")
        measured = 0 if score is not None else 1
        return (measured, -(score or 0), -int(record.get("uses") or 0), -int(record["_depth"]), record["id"])

    ranked = []
    for record in sorted(records, key=key):
        item = dict(record)
        item.pop("_depth", None)
        ranked.append(item)
    return ranked


def whitepaper_text(root: Path) -> str:
    parts = []
    folder = root / "whitepaper"
    if folder.is_dir():
        for path in sorted(folder.glob("*.md")):
            parts.append(path.read_text(encoding="utf-8"))
    return "\n".join(parts)


def vision_quotes(root: Path) -> tuple[str, str]:
    text = whitepaper_text(root)
    if QUOTE not in text:
        raise SystemExit(f"whitepaper is missing the sentence: {QUOTE}")
    abstract_start = "The Glean System is a decentralized, AI-augmented ecosystem"
    index = text.find(abstract_start)
    if index < 0:
        raise SystemExit("whitepaper is missing the abstract")
    paragraph = text[index:].split("\n\n", 1)[0]
    return QUOTE, collapse(paragraph)


def build(root: Path) -> dict:
    commons_path = root / "commons.json"
    ledger_path = root / "ledger" / "contributions.json"
    commons = load_json(commons_path)
    ledger = load_json(ledger_path)
    projects = commons.get("projects") or []
    by_id = {project["id"]: project for project in projects if project.get("id")}
    ledger_by_id = {entry["id"]: entry for entry in ledger.get("entries") or [] if entry.get("id")}
    experiments = load_experiments(root)
    records = [
        project_record(root, project, projects, by_id, ledger_by_id, experiments)
        for project in projects
        if project.get("id")
    ]
    return {
        "schema_version": SCHEMA_VERSION,
        "generated_from": {
            "ledger_tip": ledger.get("tip_hash"),
            "commons_sha256": sha256_file(commons_path),
        },
        "order": ORDER,
        "projects": rank_projects(records),
    }


def render_json(catalog: dict) -> str:
    return json.dumps(catalog, indent=2, sort_keys=True, ensure_ascii=False) + "\n"


def _fmt_list(values: list) -> str:
    if not values:
        return "none"
    return ", ".join(str(value) for value in values)


def _fmt_pou(pou: dict) -> str:
    if pou.get("score") is None:
        return f"null — {pou.get('reason') or POU_NO_DATA}"
    components = pou.get("components") or {}
    return (
        f"{pou['score']} "
        f"(R={components.get('R')} D={components.get('D')} "
        f"B={components.get('B')} L={components.get('L')} A={components.get('A')})"
    )


def _fmt_upstream(upstream: dict | None) -> str:
    if not upstream:
        return "none"
    return " | ".join(
        [
            str(upstream.get("url") or "none"),
            str(upstream.get("license") or "none"),
            str(upstream.get("credit") or "none"),
        ]
    )


def render_txt(catalog: dict) -> str:
    source = catalog["generated_from"]
    lines = [
        "# Glean Commons catalog",
        f"# schema_version={catalog['schema_version']}",
        f"# ledger_tip={source['ledger_tip']}",
        f"# commons_sha256={source['commons_sha256']}",
        "# order: " + ", ".join(catalog.get("order") or ORDER),
        "",
    ]
    blocks = []
    for project in catalog["projects"]:
        how = json.dumps(project.get("how_to_change") or {}, sort_keys=True, ensure_ascii=False)
        variants = json.dumps(project.get("variants") or [], sort_keys=True, ensure_ascii=False)
        blocks.append(
            "\n".join(
                [
                    f"id: {project['id']}",
                    f"name: {project['name']}",
                    f"type: {project['type']}",
                    f"status: {project['status']}",
                    f"summary: {project['summary']}",
                    f"tags: {_fmt_list(project.get('tags') or [])}",
                    f"path: {project['path']}",
                    f"upstream: {_fmt_upstream(project.get('upstream'))}",
                    f"parents: {_fmt_list(project.get('parents') or [])}",
                    f"ancestry: {_fmt_list(project.get('ancestry') or [])}",
                    f"children: {_fmt_list(project.get('children') or [])}",
                    f"canonical_version: {project.get('canonical_version')}",
                    f"variants: {variants}",
                    f"entry_hash: {project.get('entry_hash')}",
                    f"uses: {project.get('uses')}",
                    f"pou: {_fmt_pou(project.get('pou') or {})}",
                    f"how_to_change: {how}",
                    f"when_to_use: {project.get('when_to_use')}",
                ]
            )
        )
    return "\n".join(lines) + "\n" + "\n\n".join(blocks) + "\n"


def _link_path(path: str | None) -> str:
    if not path or path == ".":
        return "README.md"
    return path


def render_llms(catalog: dict, root: Path) -> str:
    quote, abstract = vision_quotes(root)
    doc_links = [
        ("router/ROUTER.md", "router/ROUTER.md", "Glean Router. Run `python3 router/route.py \"<request>\"` before building."),
        ("catalog.json", "catalog.json", "Machine-readable catalog. Search this first."),
        ("catalog.txt", "catalog.txt", "Plain-text catalog, one block per project."),
        ("README.md", "README.md", "What Glean Commons is."),
        ("PROOF-OF-USE.md", "PROOF-OF-USE.md", "Five signals and the proposed scorecard."),
        ("CONTRIBUTING.md", "CONTRIBUTING.md", "How to fork, improve, and add a ledger entry."),
        ("INTAKE.md", "INTAKE.md", "How to import an upstream project with ancestry."),
        ("MCP.md", "MCP.md", "Future MCP server. Search will serve catalog.json."),
        ("ANALYST.md", "ANALYST.md", "Forks, experiments, and promote or coexist."),
        ("AGENTS.md", "AGENTS.md", "Rules for AI co-laborers."),
    ]
    lines = [
        "# Glean Commons",
        "",
        f"> {quote}",
        "",
        abstract,
        "",
        "## Instructions for AI agents",
        "",
        "- Before building, run `python3 router/route.py \"<request>\"` or read router/ROUTER.md.",
        "- Search the catalog first.",
        "- Prefer the highest Proof-of-Use cell that fits.",
        "- Fork or adapt the winner instead of rebuilding.",
        "- Any new work is a child cell with parents set.",
        "- Propose changes via the pull request and issue templates.",
        "- Humans approve all merges, rewards, and publishing.",
        "- Never fabricate usage.",
        "",
        "## Catalog and docs",
        "",
    ]
    for title, href, note in doc_links:
        lines.append(f"- [{title}]({href}): {note}")
    lines.extend(["", "## Projects", ""])
    for project in catalog["projects"]:
        title = str(project["name"]).replace("[", "(").replace("]", ")")
        summary = str(project["summary"]).replace("\n", " ")
        lines.append(f"- [{title}]({_link_path(project.get('path'))}): {summary}")
    lines.append("")
    return "\n".join(lines)


def write_outputs(root: Path, catalog: dict) -> None:
    (root / "catalog.json").write_text(render_json(catalog), encoding="utf-8")
    (root / "catalog.txt").write_text(render_txt(catalog), encoding="utf-8")
    (root / "llms.txt").write_text(render_llms(catalog, root), encoding="utf-8")


def main() -> int:
    root = Path(__file__).resolve().parents[1]
    catalog = build(root)
    write_outputs(root, catalog)
    source = catalog["generated_from"]
    print(
        f"OK: {len(catalog['projects'])} projects; "
        f"ledger_tip={source['ledger_tip']}; "
        f"commons_sha256={source['commons_sha256']}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
