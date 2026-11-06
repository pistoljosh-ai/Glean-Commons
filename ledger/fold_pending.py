#!/usr/bin/env python3
"""Fold ledger/pending/*.json onto the current tip, one entry at a time.

Uses ledger/add_entry.py for every hash. Never accepts a handwritten
entry_hash, prev_hash, or parent_hashes.

  python3 ledger/fold_pending.py

Pending files are removed after a successful append. Optional registry
fragments live in registry/pending/<id>.json. Their entry_hash is filled
from the new ledger row, then the fragment is removed.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

from add_entry import append_entry, load_ledger, save_ledger

ALLOWED_TYPES = {"whitepaper", "repo", "cell", "video", "idea", "other"}
FORBIDDEN_HASH_KEYS = ("entry_hash", "prev_hash", "parent_hashes")


def repo_root_from_here() -> Path:
    return Path(__file__).resolve().parents[1]


def pending_dir(root: Path) -> Path:
    return root / "ledger" / "pending"


def registry_dir(root: Path) -> Path:
    return root / "registry" / "pending"


def _load_json(path: Path) -> dict:
    with path.open(encoding="utf-8") as handle:
        data = json.load(handle)
    if not isinstance(data, dict):
        raise ValueError(f"{path}: JSON value must be an object")
    return data


def iter_pending_files(root: Path) -> list[Path]:
    folder = pending_dir(root)
    if not folder.is_dir():
        return []
    return sorted(path for path in folder.glob("*.json") if path.is_file())


def _parents(spec: dict) -> list[str]:
    raw = spec.get("parents")
    if raw is None:
        return []
    if isinstance(raw, str):
        return [part.strip() for part in raw.split(",") if part.strip()]
    if isinstance(raw, list):
        return [str(part).strip() for part in raw if str(part).strip()]
    raise ValueError("parents must be a list of ids")


def check_spec(spec: dict, path: Path) -> list[str]:
    errors: list[str] = []
    label = path.name
    for key in FORBIDDEN_HASH_KEYS:
        if key in spec and spec[key] not in (None, "", []):
            errors.append(f"{label}: do not set {key}; fold computes it")
    required = ("id", "title", "type", "creator", "created")
    for key in required:
        if not str(spec.get(key) or "").strip():
            errors.append(f"{label}: missing {key}")
    if "parents" not in spec:
        errors.append(f"{label}: missing parents")
    else:
        try:
            _parents(spec)
        except ValueError as exc:
            errors.append(f"{label}: {exc}")
    etype = spec.get("type")
    if etype and etype not in ALLOWED_TYPES:
        errors.append(
            f"{label}: type {etype!r} is not one of {', '.join(sorted(ALLOWED_TYPES))}"
        )
    eid = str(spec.get("id") or "")
    if eid and path.stem != eid:
        errors.append(f"{label}: filename must be {eid}.json")
    if "uses" in spec and spec["uses"] is not None:
        try:
            if int(spec["uses"]) < 0:
                errors.append(f"{label}: uses must be >= 0")
        except (TypeError, ValueError):
            errors.append(f"{label}: uses must be an integer")
    return errors


def load_pending_specs(root: Path) -> tuple[list[tuple[Path, dict]], list[str]]:
    specs: list[tuple[Path, dict]] = []
    errors: list[str] = []
    seen: set[str] = set()
    for path in iter_pending_files(root):
        try:
            spec = _load_json(path)
        except (OSError, json.JSONDecodeError, ValueError) as exc:
            errors.append(f"{path.name}: {exc}")
            continue
        errors.extend(check_spec(spec, path))
        eid = str(spec.get("id") or "")
        if eid:
            if eid in seen:
                errors.append(f"{path.name}: duplicate id {eid}")
            seen.add(eid)
        specs.append((path, spec))
    return specs, errors


def fold_order(specs: list[tuple[Path, dict]]) -> list[tuple[Path, dict]]:
    def key(item: tuple[Path, dict]) -> tuple:
        spec = item[1]
        return (str(spec.get("created") or ""), str(spec.get("id") or ""), item[0].name)

    return sorted(specs, key=key)


def check_parents(specs: list[tuple[Path, dict]], ledger_ids: set[str]) -> list[str]:
    errors: list[str] = []
    known = set(ledger_ids)
    for _path, spec in fold_order(specs):
        eid = str(spec.get("id") or "")
        try:
            parents = _parents(spec)
        except ValueError:
            continue
        for pid in parents:
            if pid not in known:
                errors.append(
                    f"{eid or _path.name}: parent '{pid}' is not in the ledger "
                    "or an earlier pending entry"
                )
        if eid:
            known.add(eid)
    return errors


def check_registry(root: Path, specs: list[tuple[Path, dict]]) -> list[str]:
    errors: list[str] = []
    by_id = {str(spec.get("id") or ""): spec for _path, spec in specs}
    folder = registry_dir(root)
    if not folder.is_dir():
        return errors
    for path in sorted(folder.glob("*.json")):
        try:
            project = _load_json(path)
        except (OSError, json.JSONDecodeError, ValueError) as exc:
            errors.append(f"registry {path.name}: {exc}")
            continue
        eid = str(project.get("id") or "")
        if path.stem != eid:
            errors.append(f"registry {path.name}: filename must match id")
        if eid not in by_id:
            errors.append(f"registry {path.name}: no ledger/pending/{eid}.json")
            continue
        if project.get("entry_hash") not in (None, ""):
            errors.append(f"registry {path.name}: leave entry_hash empty; fold writes it")
        try:
            pending_parents = _parents(by_id[eid]) if "parents" in by_id[eid] else []
        except ValueError:
            pending_parents = []
        fragment_parents = project.get("parents")
        if isinstance(fragment_parents, list) and pending_parents and fragment_parents != pending_parents:
            errors.append(
                f"registry {path.name}: parents {fragment_parents} "
                f"do not match the pending entry {pending_parents}"
            )
        manifest_rel = project.get("manifest")
        if manifest_rel:
            manifest_path = root / manifest_rel
            if not manifest_path.is_file():
                errors.append(f"registry {path.name}: manifest missing at {manifest_rel}")
            else:
                try:
                    manifest = _load_json(manifest_path)
                except (OSError, json.JSONDecodeError, ValueError) as exc:
                    errors.append(f"registry {path.name}: bad manifest: {exc}")
                else:
                    if manifest.get("id") not in (None, eid):
                        errors.append(
                            f"registry {path.name}: manifest id {manifest.get('id')!r} != {eid}"
                        )
                    if manifest.get("entry_hash") not in (None, ""):
                        errors.append(
                            f"{manifest_rel}: leave entry_hash empty; fold writes it"
                        )
    return errors


def validate(root: Path | None = None) -> list[str]:
    root = root or repo_root_from_here()
    specs, errors = load_pending_specs(root)
    ledger_path = root / "ledger" / "contributions.json"
    if ledger_path.is_file():
        ledger = load_ledger(ledger_path)
        ledger_ids = {entry["id"] for entry in ledger.get("entries") or []}
    else:
        ledger_ids = set()
    for _path, spec in specs:
        eid = str(spec.get("id") or "")
        if eid and eid in ledger_ids:
            errors.append(f"{eid}: id already exists in the ledger")
    errors.extend(check_parents(specs, ledger_ids))
    errors.extend(check_registry(root, specs))
    return errors


def _write_json(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        json.dump(data, handle, indent=2, ensure_ascii=False)
        handle.write("\n")


def _upsert_project(commons: dict, project: dict) -> None:
    projects = commons.setdefault("projects", [])
    for index, existing in enumerate(projects):
        if existing.get("id") == project.get("id"):
            projects[index] = project
            return
    projects.append(project)


def _apply_registry(root: Path, eid: str, entry_hash: str) -> None:
    path = registry_dir(root) / f"{eid}.json"
    if not path.is_file():
        return
    project = _load_json(path)
    project["entry_hash"] = entry_hash
    commons_path = root / "commons.json"
    if commons_path.is_file():
        commons = _load_json(commons_path)
    else:
        commons = {"schema_version": 1, "projects": []}
    _upsert_project(commons, project)
    _write_json(commons_path, commons)
    manifest_rel = project.get("manifest")
    if manifest_rel:
        manifest_path = root / manifest_rel
        if manifest_path.is_file():
            manifest = _load_json(manifest_path)
            manifest["entry_hash"] = entry_hash
            _write_json(manifest_path, manifest)
    path.unlink()


def fold(root: Path | None = None) -> list[dict]:
    """Append every valid pending entry onto the tip. Returns new entries."""
    root = root or repo_root_from_here()
    errors = validate(root)
    if errors:
        raise SystemExit("pending entries are not foldable:\n" + "\n".join(f"  - {e}" for e in errors))
    ledger_path = root / "ledger" / "contributions.json"
    data = load_ledger(ledger_path)
    specs, _errors = load_pending_specs(root)
    appended: list[dict] = []
    for path, spec in fold_order(specs):
        eid = str(spec["id"])
        by_id = {entry["id"]: entry for entry in data.get("entries") or []}
        if eid in by_id:
            _apply_registry(root, eid, by_id[eid]["entry_hash"])
            path.unlink(missing_ok=True)
            continue
        entry = append_entry(
            data,
            {
                "id": eid,
                "title": spec["title"],
                "type": spec["type"],
                "creator": spec["creator"],
                "ai_assist": spec.get("ai_assist") or "",
                "parents": _parents(spec),
                "created": spec["created"],
                "version": spec.get("version") or "0.1.0",
                "commit": spec.get("commit") or "",
                "uses": spec.get("uses") or 0,
                "notes": spec.get("notes") or "",
            },
        )
        save_ledger(ledger_path, data)
        _apply_registry(root, eid, entry["entry_hash"])
        path.unlink(missing_ok=True)
        appended.append(entry)
    return appended


def main() -> int:
    root = repo_root_from_here()
    appended = fold(root)
    if not appended:
        tip = ""
        ledger_path = root / "ledger" / "contributions.json"
        if ledger_path.is_file():
            tip = load_ledger(ledger_path).get("tip_hash") or ""
        print(f"OK: nothing to fold; tip={tip}")
        return 0
    for entry in appended:
        print(
            f"FOLDED id={entry['id']} entry_hash={entry['entry_hash']} "
            f"prev_hash={entry['prev_hash']}"
        )
    print(f"TIP {appended[-1]['entry_hash']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
