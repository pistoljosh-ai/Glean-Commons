# SPDX-License-Identifier: Apache-2.0
"""Callable desk for a local PDF and an external Folio pin.

The first argument is the books folder the tool server always passes.
This tool does not read or write the books. It is not marked stateless,
so the public tool server does not expose it: a slip names a local path.
"""

from __future__ import annotations

import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

from desk import DeskError, checkout_text, provenance_text, slip_text  # noqa: E402


def folio_pdf_desk(_books, action: str = "provenance", path: str = "") -> str:
    try:
        if action in ("provenance", ""):
            return provenance_text()
        if action == "slip":
            if not path:
                return "NEEDS INPUT: path to a local PDF."
            return slip_text(Path(path))
        if action in ("compare-checkout", "compare_checkout"):
            if not path:
                return "NEEDS INPUT: path to a local clone of https://github.com/Forward-Future/folio."
            return checkout_text(Path(path))
        return "NEEDS INPUT: action must be provenance, slip, or compare-checkout."
    except DeskError as exc:
        return str(exc)
