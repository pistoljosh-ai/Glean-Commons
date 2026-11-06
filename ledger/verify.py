#!/usr/bin/env python3
"""Verify the Glean Commons contribution ledger hash chain.

Also checks that commons.json and per-project cell.json manifests agree.

Recomputes every entry_hash, checks parent_hashes and prev_hash links.
Exits 0 on success, 1 on any tampering or structural error.
Stdlib only. No dependencies.
"""

from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
LEDGER_PATH = HERE / "contributions.json"
COMMONS_PATH = ROOT / "commons.json"
GENESIS_PREV = "0" * 64

MANIFEST_COMPARE_KEYS = (
    "id",
    "name",
    "type",
    "path",
    "status",
    "maintainers",
    "parents",
    "entry_hash",
    "tags",
)


def canonical_bytes(entry: dict) -> bytes:
    """Canonical JSON of an entry excluding entry_hash."""
    payload = {k: v for k, v in entry.items() if k != "entry_hash"}
    return json.dumps(
        payload,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    ).encode("utf-8")


def compute_hash(entry: dict) -> str:
    return hashlib.sha256(canonical_bytes(entry)).hexdigest()


def load_json(path: Path) -> dict:
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def verify_ledger(path: Path = LEDGER_PATH) -> list[str]:
    errors: list[str] = []
    data = load_json(path)

    if "schema_version" not in data:
        errors.append("missing schema_version")
    entries = data.get("entries")
    if not isinstance(entries, list):
        errors.append("entries must be a list")
        return errors

    by_id: dict[str, dict] = {}
    prev_expected = GENESIS_PREV

    for i, entry in enumerate(entries):
        eid = entry.get("id", f"<index {i}>")
        label = f"entry[{i}] id={eid}"

        required = [
            "id",
            "title",
            "type",
            "creator",
            "ai_assist",
            "parents",
            "parent_hashes",
            "created",
            "version",
            "commit",
            "uses",
            "notes",
            "prev_hash",
            "entry_hash",
        ]
        for key in required:
            if key not in entry:
                errors.append(f"{label}: missing field '{key}'")

        if "id" in entry:
            if entry["id"] in by_id:
                errors.append(f"{label}: duplicate id")
            by_id[entry["id"]] = entry

        expected_hash = compute_hash(entry)
        actual_hash = entry.get("entry_hash")
        if actual_hash != expected_hash:
            errors.append(
                f"{label}: entry_hash mismatch "
                f"(got {actual_hash}, expected {expected_hash})"
            )

        if entry.get("prev_hash") != prev_expected:
            errors.append(
                f"{label}: prev_hash mismatch "
                f"(got {entry.get('prev_hash')}, expected {prev_expected})"
            )

        parents = entry.get("parents") or []
        parent_hashes = entry.get("parent_hashes") or []
        if not isinstance(parents, list) or not isinstance(parent_hashes, list):
            errors.append(f"{label}: parents and parent_hashes must be lists")
        elif len(parents) != len(parent_hashes):
            errors.append(
                f"{label}: parents length ({len(parents)}) != "
                f"parent_hashes length ({len(parent_hashes)})"
            )
        else:
            for pid, ph in zip(parents, parent_hashes):
                if pid not in by_id:
                    errors.append(
                        f"{label}: parent id '{pid}' not found earlier in chain"
                    )
                else:
                    if by_id[pid].get("entry_hash") != ph:
                        errors.append(
                            f"{label}: parent_hashes for '{pid}' does not "
                            f"match that entry's entry_hash"
                        )

        if actual_hash and actual_hash == expected_hash:
            prev_expected = actual_hash
        else:
            prev_expected = actual_hash or prev_expected

    tip = data.get("tip_hash")
    if entries:
        last_hash = entries[-1].get("entry_hash")
        if tip != last_hash:
            errors.append(
                f"tip_hash mismatch (got {tip}, expected {last_hash})"
            )
    elif tip not in (None, GENESIS_PREV, ""):
        errors.append("tip_hash set but entries list is empty")

    return errors


def verify_commons(commons_path: Path = COMMONS_PATH) -> list[str]:
    """Ensure commons.json projects match their folder manifests."""
    errors: list[str] = []
    if not commons_path.exists():
        errors.append(f"commons.json not found at {commons_path}")
        return errors

    commons = load_json(commons_path)
    projects = commons.get("projects")
    if not isinstance(projects, list):
        errors.append("commons.json: projects must be a list")
        return errors

    seen_ids: set[str] = set()
    for i, proj in enumerate(projects):
        label = f"commons.projects[{i}]"
        pid = proj.get("id")
        if not pid:
            errors.append(f"{label}: missing id")
            continue
        if pid in seen_ids:
            errors.append(f"{label}: duplicate id '{pid}'")
        seen_ids.add(pid)

        for key in ("name", "type", "path", "status", "maintainers", "parents", "tags", "how_to_change"):
            if key not in proj:
                errors.append(f"{label} id={pid}: missing '{key}'")

        how = proj.get("how_to_change") or {}
        if isinstance(how, dict):
            if "edit" not in how or "labels" not in how:
                errors.append(
                    f"{label} id={pid}: how_to_change needs 'edit' and 'labels'"
                )

        manifest_rel = proj.get("manifest")
        if not manifest_rel:
            continue
        manifest_path = ROOT / manifest_rel
        if not manifest_path.exists():
            errors.append(
                f"{label} id={pid}: manifest missing at {manifest_rel}"
            )
            continue
        try:
            manifest = load_json(manifest_path)
        except json.JSONDecodeError as exc:
            errors.append(f"{label} id={pid}: bad JSON in manifest: {exc}")
            continue

        for key in MANIFEST_COMPARE_KEYS:
            if key not in proj:
                continue
            if key not in manifest:
                errors.append(
                    f"{label} id={pid}: manifest missing key '{key}'"
                )
                continue
            if proj[key] != manifest[key]:
                errors.append(
                    f"{label} id={pid}: mismatch on '{key}' "
                    f"(commons={proj[key]!r}, manifest={manifest[key]!r})"
                )

        # entry_hash, if set, should exist in the ledger (when ledger present)
        eh = proj.get("entry_hash")
        if eh and LEDGER_PATH.exists():
            ledger = load_json(LEDGER_PATH)
            hashes = {e.get("entry_hash") for e in ledger.get("entries", [])}
            ids = {e.get("id") for e in ledger.get("entries", [])}
            # Allow linking to a parent/repo hash when a project has no
            # dedicated ledger row yet (e.g. cell-template, ledger tool).
            if eh not in hashes and pid not in ids:
                # Soft check: hash must at least be a known tip or entry
                if eh not in hashes:
                    errors.append(
                        f"{label} id={pid}: entry_hash not found in ledger"
                    )

    return errors


def verify(ledger_path: Path = LEDGER_PATH) -> list[str]:
    errors = verify_ledger(ledger_path)
    errors.extend(verify_commons(COMMONS_PATH))
    return errors


def main() -> int:
    path = Path(sys.argv[1]) if len(sys.argv) > 1 else LEDGER_PATH
    if not path.exists():
        print(f"FAIL: ledger not found at {path}", file=sys.stderr)
        return 1
    errors = verify(path)
    if errors:
        print(f"FAIL: {len(errors)} error(s)", file=sys.stderr)
        for e in errors:
            print(f"  - {e}", file=sys.stderr)
        return 1
    data = load_json(path)
    n = len(data.get("entries", []))
    commons = load_json(COMMONS_PATH) if COMMONS_PATH.exists() else {}
    pcount = len(commons.get("projects", []))
    print(
        f"OK: {n} ledger entr{'y' if n == 1 else 'ies'} verified; "
        f"{pcount} commons project(s) agree with manifests; "
        f"tip={data.get('tip_hash')}"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
