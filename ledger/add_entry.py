#!/usr/bin/env python3
"""Append a correctly hashed entry to the Glean Commons contribution ledger.

Usage:
  python3 ledger/add_entry.py --title "..." --type cell --creator "Name" \\
      [--parents id1,id2] [--ai-assist "..."] [--version "0.1.0"] \\
      [--commit ""] [--uses 0] [--notes "..."] [--id custom-id] [--created ISO8601]

Stdlib only. No dependencies. Does not commit to git — only updates the JSON file.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

LEDGER_PATH = Path(__file__).resolve().parent / "contributions.json"
GENESIS_PREV = "0" * 64


def canonical_bytes(entry: dict) -> bytes:
    payload = {k: v for k, v in entry.items() if k != "entry_hash"}
    return json.dumps(
        payload,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    ).encode("utf-8")


def compute_hash(entry: dict) -> str:
    return hashlib.sha256(canonical_bytes(entry)).hexdigest()


def slugify(text: str) -> str:
    s = text.lower().strip()
    s = re.sub(r"[^a-z0-9]+", "-", s)
    return s.strip("-")[:48] or "entry"


def load_ledger(path: Path) -> dict:
    if not path.exists():
        return {
            "schema_version": 1,
            "description": (
                "Glean Commons contribution-chain ledger. "
                "Append-only. Each entry is hash-linked."
            ),
            "hash_alg": "sha256",
            "canonical": "JSON object excluding entry_hash; sort_keys=true; separators=(',', ':'); UTF-8",
            "genesis_prev_hash": GENESIS_PREV,
            "tip_hash": GENESIS_PREV,
            "entries": [],
        }
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def save_ledger(path: Path, data: dict) -> None:
    with path.open("w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
        f.write("\n")


def append_entry(data: dict, spec: dict) -> dict:
    """Append one entry onto the current tip. Hashes come only from this function.

    spec keys: id, title, type, creator, parents, ai_assist, created, version,
    commit, uses, notes. parents is a list of ids. Does not write the file.
    """
    entries = data.setdefault("entries", [])
    by_id = {e["id"]: e for e in entries}

    parent_ids = [str(pid).strip() for pid in (spec.get("parents") or []) if str(pid).strip()]
    parent_hashes = []
    for pid in parent_ids:
        if pid not in by_id:
            raise ValueError(f"parent id '{pid}' not in ledger")
        parent_hashes.append(by_id[pid]["entry_hash"])

    created = spec.get("created") or datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    eid = (spec.get("id") or "").strip() or f"{slugify(spec['title'])}-{created[:10]}"
    if eid in by_id:
        raise ValueError(f"id '{eid}' already exists")

    prev_hash = entries[-1]["entry_hash"] if entries else GENESIS_PREV
    entry = {
        "id": eid,
        "title": spec["title"],
        "type": spec["type"],
        "creator": spec["creator"],
        "ai_assist": spec.get("ai_assist") or "",
        "parents": parent_ids,
        "parent_hashes": parent_hashes,
        "created": created,
        "version": spec.get("version") or "0.1.0",
        "commit": spec.get("commit") if spec.get("commit") is not None else "",
        "uses": int(spec.get("uses") or 0),
        "notes": spec.get("notes") or "",
        "prev_hash": prev_hash,
    }
    entry["entry_hash"] = compute_hash(entry)
    entries.append(entry)
    data["tip_hash"] = entry["entry_hash"]
    return entry


def main() -> int:
    p = argparse.ArgumentParser(description="Append a hashed ledger entry")
    p.add_argument("--title", required=True)
    p.add_argument("--type", required=True, dest="etype",
                   help="whitepaper | repo | cell | video | idea | other")
    p.add_argument("--creator", required=True)
    p.add_argument("--parents", default="",
                   help="Comma-separated parent entry ids")
    p.add_argument("--ai-assist", default="", dest="ai_assist")
    p.add_argument("--version", default="0.1.0")
    p.add_argument("--commit", default="")
    p.add_argument("--uses", type=int, default=0)
    p.add_argument("--notes", default="")
    p.add_argument("--id", default="", dest="eid")
    p.add_argument("--created", default="",
                   help="ISO 8601 UTC; default now")
    p.add_argument("--ledger", default=str(LEDGER_PATH))
    args = p.parse_args()

    path = Path(args.ledger)
    data = load_ledger(path)
    parent_ids = [x.strip() for x in args.parents.split(",") if x.strip()]
    try:
        entry = append_entry(
            data,
            {
                "id": args.eid,
                "title": args.title,
                "type": args.etype,
                "creator": args.creator,
                "ai_assist": args.ai_assist,
                "parents": parent_ids,
                "created": args.created,
                "version": args.version,
                "commit": args.commit,
                "uses": args.uses,
                "notes": args.notes,
            },
        )
    except ValueError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1
    prev_hash = entry["prev_hash"]
    save_ledger(path, data)

    print(f"OK: appended {entry['id']}")
    print(f"entry_hash={entry['entry_hash']}")
    print(f"prev_hash={prev_hash}")
    print(f"tip_hash={data['tip_hash']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
