"""Callable tools for the books — what an AI calls when the owner speaks.

Every function takes the books folder first, then keyword arguments that
match tools.json, and returns plain text for the AI to relay. Writes are
validated against the whole set of books before anything is saved, and each
save is one commit when the books folder is a git repo.

People talk loosely ("Acme", "the Cedar job"), so lookups accept an id or
part of a name. If a reference matches more than one thing, the tool asks
instead of guessing.
"""

from __future__ import annotations

from datetime import date, timedelta
from pathlib import Path

import books as B


class Ask(Exception):
    """Raised when the tool needs the person to clarify."""


def _today(d: str = "") -> str:
    return (date.fromisoformat(d) if d else date.today()).isoformat()


def _find(rows: list[dict], key: str, ref: str, label: str, fields=("name",)) -> dict:
    ref = (ref or "").strip()
    if not ref:
        raise Ask(f"Which {label}?")
    exact = [r for r in rows if r.get(key, "").lower() == ref.lower()]
    if exact:
        return exact[0]
    hits = [r for r in rows if any(ref.lower() in r.get(f, "").lower() for f in fields)]
    if len(hits) == 1:
        return hits[0]
    if not hits:
        raise Ask(f"No {label} matches '{ref}'.")
    opts = "; ".join(f"{r[key]} ({' / '.join(r.get(f, '') for f in fields if r.get(f))})" for r in hits[:8])
    raise Ask(f"'{ref}' matches more than one {label}: {opts}. Which one?")


def _customer(bk, ref):
    return _find(bk["customers.csv"], "customer_id", ref, "customer", ("name", "email"))


def _job(bk, ref):
    names = {c["customer_id"]: c["name"] for c in bk["customers.csv"]}
    rows = [{**j, "_who": names.get(j["customer_id"], "")} for j in bk["jobs.csv"]]
    hit = _find(rows, "job_id", ref, "job", ("description", "_who"))
    return next(j for j in bk["jobs.csv"] if j["job_id"] == hit["job_id"])


def _offer(bk, ref):
    return _find(bk["offers.csv"], "offer_id", ref, "offer", ("name",))


def _save(folder, bk, changed, msg) -> str:
    errors = B.save(folder, bk, changed, msg)
    if errors:
        raise Ask("Not saved — the books would be inconsistent: " + "; ".join(errors))
    return msg


def guard(fn):
    def run(folder, **kw):
        try:
            return fn(Path(folder), **kw)
        except Ask as a:
            return f"NEEDS INPUT: {a}"
    run.__name__ = fn.__name__
    run.__doc__ = fn.__doc__
    return run


# ---------------- read ----------------

@guard
def business_status(folder: Path, today: str = "") -> str:
    """One-screen summary: customers, jobs, owed, past due, collected, unbilled work."""
    return B.status_text(B.load(folder), date.fromisoformat(_today(today)))


@guard
def find_customers(folder: Path, query: str = "") -> str:
    bk = B.load(folder)
    rows = [c for c in bk["customers.csv"]
            if not query or query.lower() in (c["name"] + " " + c.get("email", "")).lower()]
    if not rows:
        return "No customers found."
    return "\n".join(f"{c['customer_id']}: {c['name']} {c.get('email', '')} {c.get('phone', '')}".rstrip()
                     for c in rows)


@guard
def list_jobs(folder: Path, status: str = "", customer: str = "") -> str:
    bk = B.load(folder)
    names = {c["customer_id"]: c["name"] for c in bk["customers.csv"]}
    cid = _customer(bk, customer)["customer_id"] if customer else ""
    rows = [j for j in bk["jobs.csv"]
            if (not status or j["status"] == status) and (not cid or j["customer_id"] == cid)]
    if not rows:
        return "No matching jobs."
    return "\n".join(
        f"{j['job_id']}: {names.get(j['customer_id'], j['customer_id'])} — {j.get('description') or '(no description)'}"
        f" [{j['status']}{(' ' + j['scheduled_date']) if j.get('scheduled_date') else ''}]"
        for j in rows)


@guard
def open_invoices(folder: Path, today: str = "") -> str:
    inv = [i for i in B.invoice_balances(B.load(folder), date.fromisoformat(_today(today))) if i["balance"] > 0]
    if not inv:
        return "Nothing owed. Every invoice is paid."
    inv.sort(key=lambda i: -i["days_overdue"])
    return "\n".join(
        f"#{i['invoice_id']} {i['customer_name']}: ${i['balance']:,.2f} owed of ${i['amount']:,.2f}, "
        + (f"{i['days_overdue']} days late" if i["days_overdue"] else f"due {i['due_date']}")
        for i in inv)


@guard
def history(folder: Path, limit: int = 15) -> str:
    if not B.is_git(folder):
        return "Version history is off for these books (not a git folder)."
    out = B.git(folder, "log", f"-{int(limit)}", "--date=format:%Y-%m-%d %H:%M", "--format=%h  %ad  %s")
    return out or "No changes recorded yet."


# ---------------- write ----------------

@guard
def add_customer(folder: Path, name: str, email: str = "", phone: str = "",
                 address: str = "", notes: str = "") -> str:
    bk = B.load(folder)
    dupe = [c for c in bk["customers.csv"] if c["name"].strip().lower() == name.strip().lower()]
    if dupe:
        raise Ask(f"{name} is already a customer ({dupe[0]['customer_id']}).")
    cid = B.next_id(bk, "customers.csv")
    bk["customers.csv"].append(dict(customer_id=cid, name=name.strip(), email=email,
                                    phone=phone, address=address, notes=notes))
    return _save(folder, bk, ["customers.csv"], f"Add customer {cid}: {name.strip()}")


@guard
def add_offer(folder: Path, name: str, price: float, unit: str = "") -> str:
    bk = B.load(folder)
    oid = B.next_id(bk, "offers.csv")
    bk["offers.csv"].append(dict(offer_id=oid, name=name.strip(), unit=unit, price=f"{float(price):.2f}"))
    return _save(folder, bk, ["offers.csv"], f"Add offer {oid}: {name.strip()} ${float(price):,.2f}")


@guard
def add_job(folder: Path, customer: str, description: str = "", offer: str = "",
            status: str = "quoted", scheduled_date: str = "") -> str:
    bk = B.load(folder)
    c = _customer(bk, customer)
    o = _offer(bk, offer) if offer else {}
    jid = B.next_id(bk, "jobs.csv")
    bk["jobs.csv"].append(dict(job_id=jid, customer_id=c["customer_id"], offer_id=o.get("offer_id", ""),
                               description=description or o.get("name", ""), status=status,
                               scheduled_date=scheduled_date, done_date=""))
    when = f" on {scheduled_date}" if scheduled_date else ""
    return _save(folder, bk, ["jobs.csv"], f"Add job {jid} for {c['name']}: {description or o.get('name', '')} [{status}]{when}")


@guard
def update_job(folder: Path, job: str, status: str = "", scheduled_date: str = "",
               done_date: str = "", description: str = "") -> str:
    bk = B.load(folder)
    j = _job(bk, job)
    if status:
        j["status"] = status
        if status == "done" and not (done_date or j.get("done_date")):
            done_date = _today()
    for k, v in (("scheduled_date", scheduled_date), ("done_date", done_date), ("description", description)):
        if v:
            j[k] = v
    if not (status or scheduled_date or done_date or description):
        raise Ask("What should change on the job: status, date, or description?")
    return _save(folder, bk, ["jobs.csv"], f"Update job {j['job_id']}: " + ", ".join(
        f"{k}={v}" for k, v in (("status", status), ("scheduled", scheduled_date),
                                ("done", done_date), ("description", description)) if v))


@guard
def create_invoice(folder: Path, job: str, amount: float | None = None, issued_date: str = "",
                   terms_days: int = 30) -> str:
    bk = B.load(folder)
    j = _job(bk, job)
    if any(i.get("job_id") == j["job_id"] for i in bk["invoices.csv"]):
        raise Ask(f"Job {j['job_id']} is already invoiced.")
    if amount is None:
        o = next((o for o in bk["offers.csv"] if o["offer_id"] == j.get("offer_id")), None)
        if not o:
            raise Ask(f"How much should the invoice for job {j['job_id']} be? It has no priced offer.")
        amount = B.money(o["price"])
    issued = _today(issued_date)
    due = (date.fromisoformat(issued) + timedelta(days=int(terms_days))).isoformat()
    iid = B.next_id(bk, "invoices.csv")
    bk["invoices.csv"].append(dict(invoice_id=iid, job_id=j["job_id"], customer_id=j["customer_id"],
                                   amount=f"{float(amount):.2f}", issued_date=issued, due_date=due))
    who = next(c["name"] for c in bk["customers.csv"] if c["customer_id"] == j["customer_id"])
    return _save(folder, bk, ["invoices.csv"], f"Invoice #{iid} to {who}: ${float(amount):,.2f}, due {due}")


@guard
def record_payment(folder: Path, invoice: str = "", customer: str = "", amount: float | None = None,
                   date_paid: str = "", method: str = "") -> str:
    bk = B.load(folder)
    owed = [i for i in B.invoice_balances(bk) if i["balance"] > 0]
    if invoice:
        target = next((i for i in B.invoice_balances(bk) if i["invoice_id"] == str(invoice).lstrip("#")), None)
        if not target:
            raise Ask(f"No invoice #{invoice}.")
    elif customer:
        cid = _customer(bk, customer)["customer_id"]
        theirs = [i for i in owed if i["customer_id"] == cid]
        if not theirs:
            raise Ask("That customer has no open invoices.")
        if len(theirs) > 1:
            raise Ask("They have several open invoices: " + ", ".join(
                f"#{i['invoice_id']} (${i['balance']:,.2f})" for i in theirs) + ". Which one?")
        target = theirs[0]
    else:
        raise Ask("Which invoice or customer is the payment for?")
    amt = target["balance"] if amount is None else round(float(amount), 2)
    if amt <= 0:
        raise Ask(f"Invoice #{target['invoice_id']} is already paid.")
    if amt > target["balance"] + 0.005:
        raise Ask(f"${amt:,.2f} is more than the ${target['balance']:,.2f} owed on #{target['invoice_id']}.")
    pid = B.next_id(bk, "payments.csv")
    bk["payments.csv"].append(dict(payment_id=pid, invoice_id=target["invoice_id"], amount=f"{amt:.2f}",
                                   date=_today(date_paid), method=method))
    left = round(target["balance"] - amt, 2)
    tail = "paid in full" if left <= 0 else f"${left:,.2f} still owed"
    return _save(folder, bk, ["payments.csv"],
                 f"Payment {pid}: ${amt:,.2f} from {target['customer_name']} on #{target['invoice_id']} ({tail})")


@guard
def undo_last_change(folder: Path) -> str:
    if not B.is_git(folder):
        return "Undo needs version history (git) on the books folder."
    last = B.git(folder, "log", "-1", "--format=%h %s")
    if not last or last.endswith("Open the books"):
        return "Nothing to undo."
    B.git(folder, "revert", "--no-edit", "HEAD")
    return f"Undid: {last}. (The undo is itself recorded, so nothing is lost.)"
