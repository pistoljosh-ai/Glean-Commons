#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Local desk for an external Folio checkout.

Glean Commons code. Folio itself is not imported, vendored, downloaded, or
started. The pinned facts live in upstream/forward-future/folio/PIN.json.
The MIT text in UPSTREAM-LICENSE is Folio's license, not this file's license.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
UPSTREAM = ROOT / "upstream" / "forward-future" / "folio"
PIN_PATH = UPSTREAM / "PIN.json"
LICENSE_PATH = UPSTREAM / "UPSTREAM-LICENSE"
PDF_MAGIC = b"%PDF-"
SYNTHETIC_MARKER = b"SYNTHETIC example. Not a real invoice."
# Folio's own file-import note is 300 MiB. This desk stops there without parsing.
MAX_BYTES = 300 * 1024 * 1024
REQUIRED_PIN = (
    "url",
    "pinned_revision",
    "license_spdx",
    "copyright",
    "license_sha256",
    "vendored_code",
)


class DeskError(Exception):
    """A local file or pin problem. Never a reason to launch Folio."""


def load_pin() -> dict:
    try:
        pin = json.loads(PIN_PATH.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise DeskError(f"Cannot read pin at {PIN_PATH}: {exc}") from exc
    missing = [key for key in REQUIRED_PIN if key not in pin]
    if missing:
        raise DeskError(f"Pin is missing {', '.join(missing)}.")
    if pin.get("vendored_code") is not False:
        raise DeskError("Pin must say vendored_code is false. This desk does not run Folio.")
    revision = str(pin["pinned_revision"])
    if len(revision) != 40 or any(c not in "0123456789abcdef" for c in revision):
        raise DeskError("Pinned revision is not a 40-character git sha.")
    return pin


def license_sha256() -> str:
    try:
        data = LICENSE_PATH.read_bytes()
    except OSError as exc:
        raise DeskError(f"Cannot read {LICENSE_PATH}: {exc}") from exc
    return hashlib.sha256(data).hexdigest()


def provenance_text() -> str:
    pin = load_pin()
    digest = license_sha256()
    recorded = str(pin["license_sha256"])
    license_line = (
        f"UPSTREAM-LICENSE sha256 {digest} matches the pin."
        if digest == recorded
        else f"UPSTREAM-LICENSE sha256 {digest} does not match pin {recorded}."
    )
    lines = [
        "Folio upstream pointer (external program, not vendored)",
        f"Repository: {pin['url']}",
        f"Pinned revision: {pin['pinned_revision']}",
        f"License: {pin['license_spdx']}",
        f"Copyright: {pin['copyright']}",
        license_line,
        "Folio source, installers, and third-party components are not in this repository.",
        "This command did not clone, download, launch, or import Folio.",
        "This desk does not turn on Folio's Ask AI and does not send document text anywhere.",
    ]
    return "\n".join(lines)


def _refuse_symlink(path: Path) -> None:
    if path.is_symlink():
        raise DeskError(f"Refusing a symlink: {path}. Pass the real path.")


def identify_pdf(path: Path) -> dict:
    _refuse_symlink(path)
    if not path.is_file():
        raise DeskError(f"Not a file: {path}")
    with path.open("rb") as handle:
        header = handle.read(len(PDF_MAGIC))
        if header != PDF_MAGIC:
            raise DeskError(
                f"Refusing {path}: it does not start with %PDF-. "
                "The desk does not hash or parse other files."
            )
        digest = hashlib.sha256(header)
        size = len(header)
        while True:
            chunk = handle.read(1024 * 1024)
            if not chunk:
                break
            size += len(chunk)
            if size > MAX_BYTES:
                raise DeskError(
                    f"Refusing {path}: larger than {MAX_BYTES} bytes. "
                    "The desk stopped before finishing the hash and did not call Folio."
                )
            digest.update(chunk)
    marker = False
    with path.open("rb") as handle:
        # The bundled fixture keeps the marker in the first page stream.
        marker = SYNTHETIC_MARKER in handle.read(8192)
    return {
        "path": str(path),
        "bytes": size,
        "sha256": digest.hexdigest(),
        "synthetic_marker": marker,
    }


def slip_text(path: Path) -> str:
    pin = load_pin()
    info = identify_pdf(path)
    marker = "present" if info["synthetic_marker"] else "absent"
    lines = [
        "PDF review slip",
        f"File: {info['path']}",
        f"Bytes: {info['bytes']}",
        f"SHA-256: {info['sha256']}",
        "Header: %PDF-",
        f"Synthetic marker ({SYNTHETIC_MARKER.decode()}): {marker}",
        f"Open this file yourself in Folio at pin {pin['pinned_revision']}.",
        f"Upstream: {pin['url']}",
        f"License: {pin['license_spdx']} ({pin['copyright']}). Folio source is not in this repository.",
        "This desk did not launch Folio, did not download it, did not extract text, "
        "and did not contact a network or an AI provider.",
    ]
    return "\n".join(lines)


def _git_dir(checkout: Path) -> Path:
    _refuse_symlink(checkout)
    if not checkout.is_dir():
        raise DeskError(f"Not a directory: {checkout}")
    git = checkout / ".git"
    if git.is_symlink():
        raise DeskError(f"Refusing a symlink: {git}")
    if git.is_file():
        line = git.read_text(encoding="utf-8").strip()
        prefix = "gitdir:"
        if not line.startswith(prefix):
            raise DeskError(f"{git} is not a gitdir pointer.")
        target = Path(line[len(prefix):].strip())
        if not target.is_absolute():
            target = checkout / target
        git = target
    if not git.is_dir():
        raise DeskError(
            f"Not a git checkout: {checkout}. Clone {load_pin()['url']} yourself. "
            "This desk does not clone or download."
        )
    return git


def _sha_from_ref(git: Path, ref: str) -> str:
    ref_path = git / ref
    if ref_path.is_file() and not ref_path.is_symlink():
        return ref_path.read_text(encoding="utf-8").strip().lower()
    packed = git / "packed-refs"
    if packed.is_file() and not packed.is_symlink():
        for line in packed.read_text(encoding="utf-8").splitlines():
            if not line or line.startswith("#") or line.startswith("^"):
                continue
            parts = line.split(" ", 1)
            if len(parts) != 2:
                continue
            sha, name = parts
            if name.strip() == ref:
                return sha.strip().lower()
    raise DeskError(f"Cannot resolve {ref} under {git}. Folio was not launched.")


def read_head(checkout: Path) -> str:
    git = _git_dir(checkout)
    head_path = git / "HEAD"
    if not head_path.is_file() or head_path.is_symlink():
        raise DeskError(f"Cannot read HEAD in {git}.")
    head = head_path.read_text(encoding="utf-8").strip()
    if head.startswith("ref:"):
        sha = _sha_from_ref(git, head.split(":", 1)[1].strip())
    else:
        sha = head.lower()
    if len(sha) != 40 or any(c not in "0123456789abcdef" for c in sha):
        raise DeskError(f"HEAD in {checkout} is not a commit sha.")
    return sha


def checkout_text(checkout: Path) -> str:
    pin = load_pin()
    head = read_head(checkout)
    pinned = str(pin["pinned_revision"])
    match = "yes" if head == pinned else "no"
    lines = [
        "Folio checkout comparison",
        f"Directory: {checkout}",
        f"HEAD: {head}",
        f"Pinned: {pinned}",
        f"Match: {match}",
        "This compared git metadata only. Folio was not launched, built, or imported.",
    ]
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Identify a local PDF or compare a local Folio clone to the pinned revision. "
        "Does not install or run Folio."
    )
    parser.add_argument(
        "action",
        nargs="?",
        default="provenance",
        choices=("provenance", "slip", "compare-checkout"),
    )
    parser.add_argument("path", nargs="?", default="")
    args = parser.parse_args(argv)
    try:
        if args.action == "provenance":
            print(provenance_text())
            return 0
        if not args.path:
            print(f"NEEDS INPUT: path for {args.action}.", file=sys.stderr)
            return 2
        target = Path(args.path)
        if args.action == "slip":
            print(slip_text(target))
        else:
            print(checkout_text(target))
        return 0
    except DeskError as exc:
        print(str(exc), file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
