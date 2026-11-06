#!/usr/bin/env python3
"""The books — shared data layer for Glean Commons small-business cells.

One folder of plain CSVs (see schema.json). Record facts; derive the rest.

Commands:
  books.py init   <dir>                  create empty books with headers
  books.py check  <dir>                  validate columns, types, and references
  books.py status <dir> [--today DATE]   one-screen summary of the business
  books.py ar     <dir> [--out FILE]     open invoices in invoice-followup's CSV format

Other cells can import it:
  from books import load, invoice_balances

Stdlib only.
"""

from __future__ import annotations

import argparse
import csv
import io
import json
import sys
from datetime import date
from pathlib import Path

SCHEMA = json.loads((Path(__file__).resolve().parent / "schema.json").read_text())
FILES = SCHEMA["files"]


# ---------- reading ----------

def money(v: str) -> float:
    return round(float(str(v).replace("$", "").replace(",", "").strip() or 0), 2)


def read_csv(path: Path) -> list[dict]:
    if not path.exists():
        return []
    with path.open(newline="", encoding="utf-8-sig") as f:
        return [{(k or "").strip(): (v or "").strip() for k, v in row.items()}
                for row in csv.DictReader(f)]


def load(folder) -> dict[str, list[dict]]:
    """Return {file name: rows} for every file in the schema (missing = empty)."""
    folder = Path(folder)
    return {name: read_csv(folder / name) for name in FILES}


# ---------- writing (validated, versioned) ----------

ID_PREFIX = {"customers.csv": "C", "offers.csv": "O", "jobs.csv": "J",
             "payments.csv": "P", "invoices.csv": ""}
FIRST_INVOICE = 1001


def next_id(books: dict, name: str) -> str:
    key = FILES[name]["key"]
    prefix = ID_PREFIX[name]
    nums = []
    for r in books[name]:
        v = r.get(key, "")
        tail = v[len(prefix):] if v.startswith(prefix) else ""
        if tail.isdigit():
            nums.append(int(tail))
    if name == "invoices.csv":
        return str(max(nums + [FIRST_INVOICE - 1]) + 1)
    return f"{prefix}{max(nums + [0]) + 1}"


def write_csv(path: Path, rows: list[dict], columns: list[str]) -> None:
    extra = [c for r in rows for c in r if c not in columns]
    cols = columns + sorted(set(extra), key=extra.index)
    tmp = path.with_suffix(".csv.tmp")
    with tmp.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=cols, extrasaction="ignore")
        w.writeheader()
        for r in rows:
            w.writerow({c: r.get(c, "") for c in cols})
    tmp.replace(path)


def is_git(folder: Path) -> bool:
    return (folder / ".git").exists()


def git(folder: Path, *args: str) -> str:
    import subprocess
    r = subprocess.run(
        ["git", "-C", str(folder), "-c", "user.name=Glean Books",
         "-c", "user.email=books@glean.local", *args],
        capture_output=True, text=True)
    return r.stdout.strip()


def save(folder, books: dict, changed: list[str], message: str) -> list[str]:
    """Validate the whole set of books, then write the changed files.

    Returns a list of problems; if any, nothing is written. When the books
    folder is a git repo, every save is one timestamped commit (history + undo).
    """
    folder = Path(folder)
    errors = check(books)
    if errors:
        return errors
    for name in changed:
        write_csv(folder / name, books[name], list(FILES[name]["columns"]))
    if is_git(folder):
        git(folder, "add", *changed)
        git(folder, "commit", "-q", "-m", message)
    return []


# ---------- derived facts ----------

def invoice_balances(books: dict, today: date | None = None) -> list[dict]:
    """Each invoice with paid, balance, and days_overdue derived from payments."""
    today = today or date.today()
    paid: dict[str, float] = {}
    for p in books["payments.csv"]:
        paid[p["invoice_id"]] = paid.get(p["invoice_id"], 0) + money(p["amount"])
    customers = {c["customer_id"]: c for c in books["customers.csv"]}
    out = []
    for inv in books["invoices.csv"]:
        amt = money(inv["amount"])
        got = round(paid.get(inv["invoice_id"], 0), 2)
        due = date.fromisoformat(inv["due_date"])
        bal = round(amt - got, 2)
        cust = customers.get(inv["customer_id"], {})
        out.append({
            **inv,
            "customer_name": cust.get("name", inv["customer_id"]),
            "email": cust.get("email", ""),
            "amount": amt,
            "paid": got,
            "balance": bal,
            "days_overdue": max(0, (today - due).days) if bal > 0 else 0,
        })
    return out


# ---------- commands ----------

def cmd_init(folder: Path) -> int:
    folder.mkdir(parents=True, exist_ok=True)
    made = []
    for name, spec in FILES.items():
        path = folder / name
        if path.exists():
            continue
        with path.open("w", newline="", encoding="utf-8") as f:
            csv.writer(f).writerow(spec["columns"].keys())
        made.append(name)
    note = ""
    if not is_git(folder):
        import shutil
        if shutil.which("git"):
            git(folder, "init", "-q")
            note = "; version history on (git)"
    if is_git(folder) and made:
        git(folder, "add", *made)
        git(folder, "commit", "-q", "-m", "Open the books")
    print(f"Books ready in {folder} ({len(made)} new file(s): {', '.join(made) or 'none'}){note}")
    return 0


def check(books: dict) -> list[str]:
    errors = []
    keys = {name: {r.get(spec["key"]) for r in books[name]} for name, spec in FILES.items()}
    for name, spec in FILES.items():
        seen = set()
        for i, row in enumerate(books[name], start=2):  # row 1 is the header
            where = f"{name} line {i}"
            k = row.get(spec["key"], "")
            if k in seen:
                errors.append(f"{where}: duplicate {spec['key']} '{k}'")
            seen.add(k)
            for col, rule in spec["columns"].items():
                v = row.get(col, "")
                if not v:
                    if rule.get("required"):
                        errors.append(f"{where}: missing {col}")
                    continue
                t = rule.get("type")
                try:
                    if t == "money":
                        money(v)
                    elif t == "date":
                        date.fromisoformat(v)
                except ValueError:
                    errors.append(f"{where}: {col} '{v}' is not a valid {t}")
                if "enum" in rule and v not in rule["enum"]:
                    errors.append(f"{where}: {col} '{v}' not one of {rule['enum']}")
                if "ref" in rule and v not in keys[rule["ref"]]:
                    errors.append(f"{where}: {col} '{v}' not found in {rule['ref']}")
    return errors


def cmd_check(folder: Path) -> int:
    errors = check(load(folder))
    if errors:
        print(f"{len(errors)} problem(s):")
        for e in errors:
            print("  - " + e)
        return 1
    counts = ", ".join(f"{len(v)} {k[:-4]}" for k, v in load(folder).items())
    print(f"OK: books are consistent ({counts})")
    return 0


def status_text(books: dict, today: date) -> str:
    inv = invoice_balances(books, today)
    open_inv = [i for i in inv if i["balance"] > 0]
    late = [i for i in open_inv if i["days_overdue"] > 0]
    jobs = books["jobs.csv"]
    by = lambda s: sum(1 for j in jobs if j["status"] == s)
    month = today.strftime("%Y-%m")
    collected = sum(money(p["amount"]) for p in books["payments.csv"] if p["date"].startswith(month))
    lines = [
        f"Business status — {today.isoformat()}",
        f"  Customers:        {len(books['customers.csv'])}",
        f"  Jobs:             {by('quoted')} quoted, {by('scheduled')} scheduled, "
        f"{by('in_progress')} in progress, {by('done')} done",
        f"  Owed to you:      ${sum(i['balance'] for i in open_inv):,.2f} across {len(open_inv)} invoice(s)",
        f"  Past due:         ${sum(i['balance'] for i in late):,.2f} across {len(late)} invoice(s)",
        f"  Collected {month}: ${collected:,.2f}",
    ]
    done_unbilled = {j["job_id"] for j in jobs if j["status"] == "done"} - {
        i.get("job_id") for i in books["invoices.csv"]}
    if done_unbilled:
        lines.append(f"  Done, not invoiced: {', '.join(sorted(done_unbilled))}")
    return "\n".join(lines)


def ar_csv(books: dict, today: date) -> str:
    """Open invoices in the CSV shape cells/invoice-followup reads."""
    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow(["invoice", "customer", "email", "amount", "due_date", "paid"])
    for i in invoice_balances(books, today):
        if i["balance"] > 0:
            w.writerow([i["invoice_id"], i["customer_name"], i["email"],
                        f"{i['balance']:.2f}", i["due_date"], ""])
    return buf.getvalue()


def main() -> int:
    p = argparse.ArgumentParser(description="The books for small-business cells")
    p.add_argument("command", choices=["init", "check", "status", "ar"])
    p.add_argument("folder")
    p.add_argument("--today", default="")
    p.add_argument("--out", default="")
    a = p.parse_args()
    folder = Path(a.folder)
    today = date.fromisoformat(a.today) if a.today else date.today()

    if a.command == "init":
        return cmd_init(folder)
    if a.command == "check":
        return cmd_check(folder)
    books = load(folder)
    errors = check(books)
    if errors:
        print("Books have problems; run `books.py check` first.", file=sys.stderr)
        return 1
    text = status_text(books, today) + "\n" if a.command == "status" else ar_csv(books, today)
    if a.out:
        Path(a.out).write_text(text, encoding="utf-8")
        print(f"Wrote {a.out}")
    else:
        sys.stdout.write(text)
    return 0


if __name__ == "__main__":
    sys.exit(main())
