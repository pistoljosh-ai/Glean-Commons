#!/usr/bin/env python3
"""Build the Glean Commons dashboard from the repo itself.

Reads commons.json, the ledger, every cells/*/tools.json, and
cells/small-business-core/JOBS.md. Writes:

  dashboard/data/*.csv   the figures, one file per dataset
  dashboard/data.json    the same, in one file
  dashboard/index.html   a self-contained page (data embedded; opens anywhere)

Deterministic: same repo in, same files out. CI rebuilds it and fails if the
committed copy is stale, so the dashboard changes with every merge.

Stdlib only. Usage (from the repo root):
  python3 scripts/build_dashboard.py
"""

from __future__ import annotations

import csv
import io
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "dashboard"
sys.path.insert(0, str(ROOT / "ledger"))
import verify  # noqa: E402  (ledger/verify.py)


def agent_of(ai_assist: str) -> str:
    s = (ai_assist or "").lower()
    if "claude" in s:
        return "Claude"
    if "grok" in s or "co-laborer" in s:
        return "Grok Bot"
    if "cursor" in s:
        return "Cursor Agent"
    return "Human" if not s else ai_assist.split(":")[0].strip()


def build() -> dict:
    ledger = json.loads((ROOT / "ledger/contributions.json").read_text(encoding="utf-8"))["entries"]
    commons = json.loads((ROOT / "commons.json").read_text(encoding="utf-8"))["projects"]

    tools = []
    for tj in sorted((ROOT / "cells").glob("*/tools.json")):
        spec = json.loads(tj.read_text(encoding="utf-8"))
        for t in spec["tools"]:
            tools.append({"tool": t["name"], "job": t.get("job", ""), "cell": spec.get("cell", tj.parent.name),
                          "kind": "writes" if t.get("writes") else "reads", "writes": " ".join(t.get("writes", []))})
    server = ROOT / "mcp/server.py"
    if server.exists():
        for name in re.findall(r'"name": "([a-z_]+)", "job": "commons"', server.read_text(encoding="utf-8")):
            tools.append({"tool": name, "job": "commons", "cell": "glean-mcp",
                          "kind": "writes" if name.startswith("note_") else "reads",
                          "writes": "wishlist.md" if name.startswith("note_") else ""})

    per_cell: dict[str, int] = {}
    per_job: dict[str, int] = {}
    for t in tools:
        per_cell[t["cell"]] = per_cell.get(t["cell"], 0) + 1
        per_job[t["job"].lower()] = per_job.get(t["job"].lower(), 0) + 1

    uses_by_hash = {e["entry_hash"]: e.get("uses", 0) for e in ledger}
    projects = [{"id": p["id"], "name": p["name"], "type": p["type"], "status": p["status"], "path": p["path"],
                 "version": p.get("canonical_version", ""), "parents": len(p.get("parents", [])),
                 "tools": per_cell.get(p["id"], 0), "uses": uses_by_hash.get(p.get("entry_hash"), 0)}
                for p in commons]

    jobs = []
    jobs_md = ROOT / "cells/small-business-core/JOBS.md"
    if jobs_md.exists():
        for line in jobs_md.read_text(encoding="utf-8").splitlines():
            m = re.match(r"^\|\s*\*\*(.+?)\*\*\s*\|[^|]*\|\s*([^|]+?)\s*\|", line)
            if m:
                word = m.group(2).split()[0].lower()
                status = {"built": "built", "next": "next"}.get(word, "planned")
                jobs.append({"order": len(jobs) + 1, "job": m.group(1), "status": status,
                             "tools": per_job.get(m.group(1).lower(), 0)})

    ledger_rows = [{"seq": i + 1, "id": e["id"], "title": e["title"], "type": e["type"], "creator": e["creator"],
                    "agent": agent_of(e.get("ai_assist", "")), "parents": "|".join(e["parents"]),
                    "created": e["created"], "version": e["version"], "uses": e.get("uses", 0),
                    "hash": e["entry_hash"][:12], "prev": e["prev_hash"][:12]}
                   for i, e in enumerate(ledger)]

    led_err, com_err = verify.verify_ledger(), verify.verify_commons()
    integrity = [
        {"check": "Ledger hash chain", "result": "verified" if not led_err else "FAILED",
         "detail": f"{len(ledger)} entries; tip {ledger[-1]['entry_hash'][:12]}" if not led_err else "; ".join(led_err)[:200]},
        {"check": "Registry matches manifests", "result": "verified" if not com_err else "FAILED",
         "detail": f"{len(commons)} projects agree" if not com_err else "; ".join(com_err)[:200]},
    ]

    summary = [{
        "projects": len(projects), "entries": len(ledger), "tools": len(tools),
        "jobs_built": sum(1 for j in jobs if j["status"] == "built"), "jobs_total": len(jobs),
        "uses": sum(int(e.get("uses", 0)) for e in ledger),
        "ledger_tip": ledger[-1]["entry_hash"][:12],
    }]
    return {"summary": summary, "jobs": jobs, "ledger": ledger_rows, "projects": projects,
            "tools": tools, "integrity": integrity}


def to_csv(rows: list[dict]) -> str:
    if not rows:
        return ""
    buf = io.StringIO()
    w = csv.DictWriter(buf, fieldnames=list(rows[0]), lineterminator="\n")
    w.writeheader()
    w.writerows(rows)
    return buf.getvalue()


def main() -> int:
    data = build()
    (OUT / "data").mkdir(parents=True, exist_ok=True)
    for name, rows in data.items():
        (OUT / "data" / f"{name}.csv").write_text(to_csv(rows), encoding="utf-8")
    blob = json.dumps(data, indent=1, ensure_ascii=False, sort_keys=True)
    (OUT / "data.json").write_text(blob + "\n", encoding="utf-8")
    template = (OUT / "template.html").read_text(encoding="utf-8")
    safe = blob.replace("</", "<\\/")
    (OUT / "index.html").write_text(template.replace("/*DATA*/null", safe), encoding="utf-8")
    s = data["summary"][0]
    print(f"OK: dashboard built ({s['projects']} projects, {s['entries']} ledger entries, "
          f"{s['tools']} tools, {s['jobs_built']}/{s['jobs_total']} jobs built)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
