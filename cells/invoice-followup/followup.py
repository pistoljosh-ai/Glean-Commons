#!/usr/bin/env python3
"""Invoice follow-up drafter — a Glean Commons cell.

Reads a CSV of open invoices and writes polite, escalating reminder drafts
for the ones that are past due. Drafts only: nothing is sent. A human reads,
edits, and sends.

CSV columns (header row required):
  invoice, customer, email, amount, due_date (YYYY-MM-DD), [paid]

Usage:
  python3 cells/invoice-followup/followup.py invoices.csv [--today YYYY-MM-DD]
      [--business "Your Business"] [--out drafts.md]

Stdlib only.
"""

from __future__ import annotations

import argparse
import csv
import sys
from datetime import date
from pathlib import Path

# (min days overdue, tier name, subject, body)
TIERS = [
    (1, "friendly",
     "Quick reminder: invoice {invoice}",
     "Hi {customer},\n\n"
     "Just a friendly note that invoice {invoice} for ${amount} was due on "
     "{due_date}. If it's already on its way, thank you and please ignore this.\n\n"
     "Thanks,\n{business}"),
    (15, "firm",
     "Invoice {invoice} is {days} days past due",
     "Hi {customer},\n\n"
     "Invoice {invoice} for ${amount} is now {days} days past due (due {due_date}). "
     "Could you let me know when we can expect payment? Happy to resend the "
     "invoice or set up a payment plan if that helps.\n\n"
     "Thanks,\n{business}"),
    (45, "final",
     "Final notice: invoice {invoice}",
     "Hi {customer},\n\n"
     "Invoice {invoice} for ${amount} is {days} days past due. Please arrange "
     "payment or reply within 7 days so we can sort this out together before "
     "taking further steps.\n\n"
     "Thank you,\n{business}"),
]

TRUTHY = {"y", "yes", "true", "1", "paid", "x"}


def tier_for(days: int):
    chosen = None
    for min_days, name, subject, body in TIERS:
        if days >= min_days:
            chosen = (name, subject, body)
    return chosen


def build_drafts(rows, today: date, business: str) -> list[dict]:
    drafts = []
    for row in rows:
        r = {k.strip().lower(): (v or "").strip() for k, v in row.items() if k}
        if r.get("paid", "").lower() in TRUTHY:
            continue
        try:
            due = date.fromisoformat(r["due_date"])
            amount = float(r["amount"].replace("$", "").replace(",", ""))
        except (KeyError, ValueError):
            continue
        days = (today - due).days
        tier = tier_for(days)
        if not tier:
            continue
        name, subject, body = tier
        fields = {
            "invoice": r.get("invoice", "?"),
            "customer": r.get("customer") or "there",
            "amount": f"{amount:,.2f}",
            "due_date": due.isoformat(),
            "days": days,
            "business": business,
        }
        drafts.append({
            "to": r.get("email", ""),
            "tier": name,
            "days": days,
            "amount": amount,
            "subject": subject.format(**fields),
            "body": body.format(**fields),
        })
    drafts.sort(key=lambda d: (-d["days"], -d["amount"]))
    return drafts


def render(drafts: list[dict]) -> str:
    if not drafts:
        return "No past-due invoices. Nothing to send.\n"
    total = sum(d["amount"] for d in drafts)
    out = [f"# {len(drafts)} reminder draft(s) — ${total:,.2f} past due\n"]
    for d in drafts:
        out.append(f"## [{d['tier']}] {d['subject']}")
        out.append(f"To: {d['to'] or '(no email on file)'}\n")
        out.append(d["body"] + "\n")
    return "\n".join(out)


def main() -> int:
    p = argparse.ArgumentParser(description="Draft invoice reminders")
    p.add_argument("csv")
    p.add_argument("--today", default="")
    p.add_argument("--business", default="Your Business")
    p.add_argument("--out", default="")
    a = p.parse_args()

    today = date.fromisoformat(a.today) if a.today else date.today()
    with open(a.csv, newline="", encoding="utf-8-sig") as f:
        drafts = build_drafts(csv.DictReader(f), today, a.business)
    text = render(drafts)
    if a.out:
        Path(a.out).write_text(text, encoding="utf-8")
        print(f"Wrote {len(drafts)} draft(s) to {a.out}")
    else:
        sys.stdout.write(text)
    return 0


if __name__ == "__main__":
    sys.exit(main())
