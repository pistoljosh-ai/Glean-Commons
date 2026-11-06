"""Callable tool for invoice-followup — reads the shared books."""

from __future__ import annotations

import csv
import io
import sys
from datetime import date
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE.parent / "small-business-core"))

import books as B  # noqa: E402
from followup import build_drafts, render  # noqa: E402


def draft_payment_reminders(folder, business_name: str = "Your Business", today: str = "") -> str:
    """Drafts (never sends) friendly/firm/final reminders for every past-due balance."""
    d = date.fromisoformat(today) if today else date.today()
    bk = B.load(folder)
    rows = list(csv.DictReader(io.StringIO(B.ar_csv(bk, d))))
    return render(build_drafts(rows, d, business_name)) + "\n(Drafts only. Review and send them yourself.)"
