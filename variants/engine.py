#!/usr/bin/env python3
"""Variants — your own version of any tool in the commons.

> If you can think it, you can build it. — The Glean System, Draft 1.0, sec 7.4
> AI helps users create tools via voice or text. — sec 4.4

A variant is a small file that says "start from this tool, change these
files like so". It carries the wish in the owner's words, who made it, and
which AI helped.

  yours     saved in your own versions folder (a git repo: history + undo);
            your tool server runs your version instead of the original
  shared    the same file, placed in the commons under variants/shared/
  adopted   someone else's shared variant, running on your machine
  promoted  enough independent people adopted it and a human approved, so it
            became the original; everyone's copy quietly switches over

We do not lose ground: when the original changes, your version is re-fitted
on top of it. If it cannot be, the copy you already had keeps running and
you are told what needs a second look.

Stdlib only. `git` is used when installed (history, patch re-fitting).
"""

from __future__ import annotations

import difflib
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CELLS = ROOT / "cells"
SHARED = ROOT / "variants" / "shared"
ADOPTIONS = ROOT / "variants" / "adoptions"
FORMAT = 1
PROMOTE_AT = 30  # independent adopters before a promotion decision (ANALYST.md)
SKIP_DIRS = {"__pycache__", ".git"}
SKIP_FILES = {"cell.json", ".wish.json"}  # cell.json is bookkeeping the fold rewrites
UPSTREAM = "_upstream"


class Problem(Exception):
    """Something the person (or their AI) needs to hear, in plain words."""


def now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def slug(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", (text or "").lower()).strip("-")[:40] or "my-version"


def is_text(data: bytes) -> bool:
    try:
        data.decode("utf-8")
        return True
    except UnicodeDecodeError:
        return False


def read_tree(folder: Path) -> dict[str, bytes]:
    out = {}
    for path in sorted(folder.rglob("*")):
        rel = path.relative_to(folder)
        if path.is_file() and not (set(rel.parts) & SKIP_DIRS) and path.suffix != ".pyc":
            out[rel.as_posix()] = path.read_bytes()
    return out


def copy_tree(src: Path, dst: Path) -> None:
    shutil.copytree(src, dst, ignore=shutil.ignore_patterns("__pycache__", ".git", "*.pyc"))


def make_diff(rel: str, old: str, new: str) -> str:
    return "".join(difflib.unified_diff(old.splitlines(keepends=True), new.splitlines(keepends=True),
                                        f"a/{rel}", f"b/{rel}"))


def diff_changes(base_dir: Path, mine_dir: Path) -> list[dict]:
    base, mine = read_tree(base_dir), read_tree(mine_dir)
    changes = []
    for rel in sorted(set(base) | set(mine)):
        if Path(rel).name in SKIP_FILES:
            continue
        b, m = base.get(rel), mine.get(rel)
        if b == m:
            continue
        if (b is not None and not is_text(b)) or (m is not None and not is_text(m)):
            raise Problem(f"{rel} is not a text file; versions can only change text files for now.")
        old, new = (b or b"").decode("utf-8"), (m or b"").decode("utf-8")
        changes.append({"path": rel, "base_sha": sha(b) if b is not None else None,
                        "new": new if m is not None else None, "diff": make_diff(rel, old, new)})
    return changes


def variant_id(name: str, payload) -> str:
    return f"{slug(name)}-{sha(json.dumps(payload, sort_keys=True).encode('utf-8'))[:10]}"


def _id_payload(v: dict):
    if v.get("kind") == "upstream":
        return v.get("patch", "")
    return [[c.get("path"), c.get("base_sha"), c.get("new")] for c in v.get("changes", [])]


def validate(v: dict) -> list[str]:
    """Problems with a variant file. Empty list means well-formed."""
    errs = []
    if not isinstance(v, dict):
        return ["not a JSON object"]
    if v.get("format") != FORMAT:
        errs.append(f"format must be {FORMAT}")
    for key in ("id", "name", "wish", "author", "created", "base"):
        if not v.get(key):
            errs.append(f"missing {key}")
    kind = v.get("kind")
    if kind == "cell":
        if not (v.get("base") or {}).get("cell"):
            errs.append("base.cell missing")
        if not v.get("changes"):
            errs.append("no changes")
        for c in v.get("changes", []):
            p = str(c.get("path", ""))
            if not p or p.startswith("/") or ".." in Path(p).parts or Path(p).name in SKIP_FILES or "\\" in p:
                errs.append(f"unsafe or reserved path: {p!r}")
            if c.get("base_sha") is None and c.get("new") is None:
                errs.append(f"{p}: neither adds nor removes anything")
    elif kind == "upstream":
        if not (v.get("base") or {}).get("commit") or not v.get("patch"):
            errs.append("upstream variant needs base.commit and patch")
    else:
        errs.append("kind must be 'cell' or 'upstream'")
    if not errs and v["id"] != variant_id(v["name"], _id_payload(v)):
        errs.append("id does not match the contents (file was altered after it was saved)")
    return errs


def _git_patch(current: str, diff: str, rel: str) -> str | None:
    """Re-fit one file's change onto a file that has moved on.

    Returns the new text, the same text if the change is already in there, or
    None if it will not fit.
    """
    if not shutil.which("git") or not current.endswith("\n") or not diff:
        return None
    with tempfile.TemporaryDirectory() as tmp:
        target = Path(tmp) / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(current, encoding="utf-8")
        run = lambda *flags: subprocess.run(["git", "apply", "--whitespace=nowarn", *flags, "-"], input=diff,  # noqa: E731
                                            text=True, capture_output=True, cwd=tmp).returncode == 0
        if run("--reverse", "--check"):
            return current  # the original already contains this change
        return target.read_text(encoding="utf-8") if run() else None


def apply_changes(base_dir: Path, changes: list[dict], out_dir: Path) -> tuple[str, list[str]]:
    """Build base + changes in out_dir. Returns ('ok' | 'same' | 'conflict', notes).

    'same' means every change is already in the base: the variant was promoted.
    """
    if out_dir.exists():
        shutil.rmtree(out_dir)
    copy_tree(base_dir, out_dir)
    applied, notes = 0, []
    for c in changes:
        target = out_dir / c["path"]
        cur = target.read_bytes() if target.is_file() else None
        new = c["new"].encode("utf-8") if c["new"] is not None else None
        if cur == new:
            continue  # already there
        if cur is not None and c["base_sha"] is not None and sha(cur) == c["base_sha"] or (cur is None and c["base_sha"] is None):
            pass  # the original is exactly what this change was written against
        elif cur is not None and new is not None and c["new"].endswith("\n") and is_text(cur):
            refit = _git_patch(cur.decode("utf-8"), c.get("diff", ""), c["path"])
            if refit is None:
                notes.append(f"{c['path']}: the original changed here too, and the two changes overlap")
                continue
            if refit.encode("utf-8") == cur:
                continue  # already part of the original
            new = refit.encode("utf-8")
            notes.append(f"{c['path']}: re-fitted onto the updated original")
        else:
            notes.append(f"{c['path']}: the original changed in a way this version did not expect")
            continue
        if new is None:
            target.unlink()
        else:
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(new)
        applied += 1
    if any("overlap" in n or "did not expect" in n for n in notes):
        return "conflict", notes
    return ("ok" if applied else "same"), notes


def run_tests(folder: Path, extra_paths: list[str]) -> tuple[bool | None, str]:
    """Run a cell's own tests in folder. (None, ...) when it has none."""
    tests = sorted(folder.glob("test_*.py"))
    if not tests:
        return None, "This tool has no tests of its own."
    env = dict(os.environ)
    env["PYTHONPATH"] = os.pathsep.join([str(folder), *extra_paths, env.get("PYTHONPATH", "")])
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    lines, ok = [], True
    for t in tests:
        try:
            r = subprocess.run([sys.executable, str(t)], cwd=folder, env=env, capture_output=True, text=True, timeout=180)
            passed, out = r.returncode == 0, (r.stdout + r.stderr).strip()
        except subprocess.TimeoutExpired:
            passed, out = False, "timed out"
        ok = ok and passed
        lines.append(f"{'PASS' if passed else 'FAIL'} {t.name}" + ("" if passed else "\n" + out[-1500:]))
    return ok, "\n".join(lines)


# ---------------- a person's own versions ----------------

class Variants:
    def __init__(self, home: Path | None, cells_root: Path = CELLS, shared_root: Path = SHARED):
        self.home = Path(home) if home else None
        self.cells_root, self.shared_root = cells_root, shared_root

    # -- storage --
    def _need_home(self) -> Path:
        if self.home is None:
            raise Problem("No versions folder is set for this server.")
        if not (self.home / "state.json").exists():
            for d in ("saved", "active", "drafts", "outbox"):
                (self.home / d).mkdir(parents=True, exist_ok=True)
            (self.home / ".gitignore").write_text("active/\ndrafts/\noutbox/\n", encoding="utf-8")
            (self.home / "state.json").write_text('{"cells": {}}\n', encoding="utf-8")
            if shutil.which("git") and not (self.home / ".git").exists():
                self._git("init", "-q")
            self._commit("Start keeping my own versions")
        return self.home

    def _git(self, *args: str) -> str:
        r = subprocess.run(["git", "-C", str(self.home), "-c", "user.name=Glean Versions",
                            "-c", "user.email=versions@glean.local", *args], capture_output=True, text=True)
        return r.stdout.strip()

    def _commit(self, message: str) -> None:
        if self.home and (self.home / ".git").exists():
            self._git("add", "-A")
            self._git("commit", "-q", "-m", message)

    def _state(self) -> dict:
        if self.home is None or not (self.home / "state.json").exists():
            return {"cells": {}}
        return json.loads((self.home / "state.json").read_text(encoding="utf-8"))

    def _save_state(self, state: dict) -> None:
        (self._need_home() / "state.json").write_text(json.dumps(state, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    # -- where things are --
    def cells(self) -> list[str]:
        return sorted(d.name for d in self.cells_root.iterdir()
                      if d.is_dir() and not d.name.startswith(("_", ".")))

    def base_dir(self, cell: str) -> Path:
        if cell not in self.cells():
            raise Problem(f"No tool family called '{cell}'. Choose from: {', '.join(self.cells())}.")
        return self.cells_root / cell

    def active_dirs(self) -> dict[str, Path]:
        if self.home is None or not (self.home / "active").is_dir():
            return {}
        return {d.name: d for d in sorted((self.home / "active").iterdir())
                if d.is_dir() and not d.name.startswith(".") and (self.cells_root / d.name).is_dir()}

    def effective_dir(self, cell: str) -> Path:
        return self.active_dirs().get(cell, self.cells_root / cell)

    def _other_paths(self, cell: str) -> list[str]:
        return [str(self.effective_dir(c)) for c in self.cells() if c != cell]

    def draft_dir(self, cell: str) -> Path:
        if self.home is None:
            raise Problem("No versions folder is set for this server.")
        return self.home / "drafts" / cell  # looking never creates anything

    def _draft_file(self, cell: str, file: str) -> Path:
        draft = self.draft_dir(cell)
        if not draft.is_dir():
            raise Problem(f"No change in progress for '{cell}'. Start one first.")
        path = (draft / file).resolve()
        if draft.resolve() not in path.parents or Path(file).name in SKIP_FILES:
            raise Problem(f"'{file}' is outside this tool's folder or is reserved.")
        return path

    def saved(self, cell: str | None = None) -> list[dict]:
        if self.home is None or not (self.home / "saved").is_dir():
            return []
        out = []
        for f in sorted((self.home / "saved").glob("*/*.json")):
            if cell is None or f.parent.name == cell:
                out.append(json.loads(f.read_text(encoding="utf-8")))
        return out

    def find_saved(self, ref: str, cell: str | None = None) -> dict:
        ref_l = (ref or "").strip().lower()
        pool = self.saved(cell)
        hits = [v for v in pool if v["id"].lower() == ref_l] or \
               [v for v in pool if ref_l and (ref_l in v["id"].lower() or ref_l in v["name"].lower())]
        if len(hits) == 1:
            return hits[0]
        if not hits:
            raise Problem(f"No saved version matches '{ref}'.")
        raise Problem(f"'{ref}' matches several versions: {', '.join(v['id'] for v in hits)}. Which one?")

    # -- making a change --
    def start(self, cell: str, wish: str) -> str:
        base = self.base_dir(cell)
        self._need_home()
        draft = self.draft_dir(cell)
        resumed = draft.is_dir()
        if not resumed:
            copy_tree(self.effective_dir(cell), draft)
        (draft / ".wish.json").write_text(json.dumps({"wish": wish.strip(), "started": now()}) + "\n", encoding="utf-8")
        files = [f for f in read_tree(draft) if Path(f).name not in SKIP_FILES]
        return "\n".join([
            f"{'Picked up the change already in progress' if resumed else 'Private working copy ready'} for '{cell}'.",
            f"Wish: {wish.strip()}",
            f"Working copy: {draft}",
            f"Files: {', '.join(files)}",
            "Nothing here affects the original or anyone else. Next: read the files that matter, edit them "
            "(directly in that folder, or with version_read / version_edit), run version_test, then version_save.",
            f"(Original: {base})",
        ])

    def read(self, cell: str, file: str) -> str:
        path = self._draft_file(cell, file)
        if not path.is_file():
            raise Problem(f"'{file}' does not exist in the working copy.")
        return path.read_text(encoding="utf-8")

    def edit(self, cell: str, file: str, find: str = "", replace: str = "", content: str | None = None) -> str:
        path = self._draft_file(cell, file)
        if content is not None:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(content, encoding="utf-8")
            return f"Wrote {file} ({len(content.splitlines())} lines) in the working copy."
        if not path.is_file():
            raise Problem(f"'{file}' does not exist. Pass content to create it.")
        text = path.read_text(encoding="utf-8")
        n = text.count(find) if find else 0
        if n != 1:
            raise Problem(f"The text to find appears {n} times in {file}; it must appear exactly once. Include more of the surrounding text.")
        path.write_text(text.replace(find, replace), encoding="utf-8")
        return f"Changed {file} in the working copy."

    def test(self, cell: str) -> tuple[bool | None, str]:
        draft = self.draft_dir(cell)
        if not draft.is_dir():
            raise Problem(f"No change in progress for '{cell}'.")
        return run_tests(draft, self._other_paths(cell))

    def save(self, cell: str, name: str, author: str = "", ai_assist: str = "") -> str:
        draft, base = self.draft_dir(cell), self.base_dir(cell)
        if not draft.is_dir():
            raise Problem(f"No change in progress for '{cell}'. Start one first.")
        changes = diff_changes(base, draft)
        if not changes:
            raise Problem("The working copy is identical to the original, so there is nothing to save.")
        ok, report = run_tests(draft, self._other_paths(cell))
        if ok is False:
            raise Problem("Not saved: the tool's tests fail with this change. Fix it and try again.\n" + report)
        wish = json.loads((draft / ".wish.json").read_text(encoding="utf-8")).get("wish", "") if (draft / ".wish.json").exists() else ""
        state = self._state()
        entry = state["cells"].setdefault(cell, {"active": None, "history": []})
        v = {"format": FORMAT, "kind": "cell", "id": variant_id(name, _id_payload({"changes": changes})),
             "name": name.strip(), "wish": wish or name.strip(), "author": author.strip() or "me",
             "author_login": "", "ai_assist": ai_assist.strip(), "created": now(),
             "base": {"cell": cell}, "previous": entry.get("active"), "tested": ok is True,
             "status": "testing", "changes": changes}
        out = self.home / "saved" / cell / f"{v['id']}.json"
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps(v, indent=2) + "\n", encoding="utf-8")
        status, notes = self.materialize(cell, v)
        if status != "ok":
            raise Problem("Saved, but it could not be switched on: " + "; ".join(notes))
        entry.setdefault("history", []).append(entry.get("active"))
        entry["active"], entry["note"] = v["id"], ""
        self._save_state(state)
        shutil.rmtree(draft)
        self._commit(f"Save my version of {cell}: {v['name']} — {v['wish']}")
        return (f"Saved and switched on: '{v['name']}' ({v['id']}) for '{cell}'. {len(changes)} file(s) changed; "
                + ("tests pass." if ok else "this tool has no tests, so it is untested.")
                + " Your tools now run your version. Say 'switch back' any time, or share it with version_share.")

    def materialize(self, cell: str, v: dict) -> tuple[str, list[str]]:
        home = self._need_home()
        tmp, live = home / "active" / f".{cell}.building", home / "active" / cell
        status, notes = apply_changes(self.base_dir(cell), v["changes"], tmp)
        if status == "ok":
            if live.exists():
                shutil.rmtree(live)
            tmp.rename(live)
        else:
            shutil.rmtree(tmp, ignore_errors=True)
            if status == "same" and live.exists():
                shutil.rmtree(live)
        return status, notes

    def switch(self, cell: str, to: str) -> str:
        self.base_dir(cell)
        state = self._state()
        entry = state["cells"].setdefault(cell, {"active": None, "history": []})
        word = (to or "").strip().lower()
        if word in ("original", "off", "main", "default"):
            target = None
        elif word in ("previous", "undo", "back", "last"):
            if not entry.get("history"):
                raise Problem(f"There is no earlier version of '{cell}' to go back to.")
            target = entry["history"][-1]
        else:
            target = self.find_saved(to, cell)["id"]
        if target == entry.get("active"):
            return f"'{cell}' is already on {target or 'the original'}."
        if target is None:
            shutil.rmtree(self._need_home() / "active" / cell, ignore_errors=True)
        else:
            status, notes = self.materialize(cell, self.find_saved(target, cell))
            if status == "conflict":
                raise Problem("Could not switch: " + "; ".join(notes))
            if status == "same":
                target = None
        entry.setdefault("history", []).append(entry.get("active"))
        entry["active"], entry["note"] = target, ""
        self._save_state(state)
        self._commit(f"Switch {cell} to {target or 'the original'}")
        return f"'{cell}' now runs {('your version ' + target) if target else 'the original'}. Nothing was deleted; you can switch again any time."

    def refresh(self) -> list[str]:
        """Re-fit every switched-on version onto the current originals. Called when the server starts."""
        state, messages, dirty = self._state(), [], False
        for cell, entry in state["cells"].items():
            vid = entry.get("active")
            if not vid or not (self.cells_root / cell).is_dir():
                continue
            try:
                v = self.find_saved(vid, cell)
            except Problem:
                continue
            status, notes = self.materialize(cell, v)
            if status == "same":
                entry.setdefault("history", []).append(vid)
                entry["active"], entry["note"], dirty = None, "", True
                messages.append(f"Your version '{v['name']}' of {cell} is now part of the original. Nothing left to maintain.")
            elif status == "conflict":
                note = "needs a second look: " + "; ".join(notes)
                if entry.get("note") != note:
                    entry["note"], dirty = note, True
                messages.append(f"The original {cell} changed and your version '{v['name']}' could not be re-fitted. "
                                "Your last working copy keeps running. Ask your AI to redo the change on the new original.")
            elif entry.get("note"):
                entry["note"], dirty = "", True
        if dirty:
            self._save_state(state)
            self._commit("Re-fit my versions onto the updated originals")
        return messages

    def listing(self) -> str:
        state, lines = self._state(), []
        for cell in sorted({v["base"].get("cell", UPSTREAM) for v in self.saved()} | set(state["cells"])):
            entry = state["cells"].get(cell, {})
            lines.append(f"{cell}: running {entry.get('active') or 'the original'}"
                         + (f"  ({entry['note']})" if entry.get("note") else ""))
            for v in self.saved(cell):
                lines.append(f"  - {v['id']}: {v['wish']} (by {v['author']}, {v['created'][:10]})")
        if self.home and (self.home / "drafts").is_dir():
            for d in sorted((self.home / "drafts").iterdir()):
                if d.is_dir():
                    lines.append(f"{d.name}: a change is in progress (not saved yet)")
        return "\n".join(lines) or "You have no versions of your own yet. Every tool is running the original."

    # -- sharing --
    def share(self, ref: str = "", cell: str | None = None, author: str = "", login: str = "") -> str:
        if ref:
            v = self.find_saved(ref, cell)
        else:
            active = self._state()["cells"].get(cell or "", {}).get("active")
            if not active:
                raise Problem("Which version? Name it, or switch one on first.")
            v = self.find_saved(active, cell)
        v = dict(v, author=author.strip() or v["author"], author_login=login.strip().lstrip("@"))
        v.pop("previous", None)
        group = v["base"].get("cell") or UPSTREAM
        box = self._need_home() / "outbox"
        box.mkdir(exist_ok=True)
        (box / f"{v['id']}.json").write_text(json.dumps(v, indent=2) + "\n", encoding="utf-8")
        ledger = {"id": f"variant-{v['id']}", "title": f"Variant of {group}: {v['name']}", "type": "cell",
                  "creator": v["author"], "ai_assist": v.get("ai_assist", ""), "parents": [group if group != UPSTREAM else v["base"].get("upstream", "")],
                  "created": now(), "version": "variant", "commit": "", "uses": 0, "notes": v["wish"]}
        (box / f"{v['id']}.ledger.json").write_text(json.dumps(ledger, indent=2) + "\n", encoding="utf-8")
        return "\n".join([
            f"Ready to share: {box / (v['id'] + '.json')}",
            "It contains only your change to the tool. None of your business data is in it.",
            "Send that file to anyone, or offer it to the whole commons with one pull request that adds two files:",
            f"  variants/shared/{group}/{v['id']}.json        (the file above)",
            f"  ledger/pending/variant-{v['id']}.json   (your credit; a draft is at {box / (v['id'] + '.ledger.json')})",
            "A person reviews it. Once merged, anyone can adopt it, and each adopter counts toward it becoming the original.",
        ])

    def locate(self, source: str) -> dict:
        path = Path(source).expanduser()
        if path.is_file():
            return json.loads(path.read_text(encoding="utf-8"))
        hits = [f for f in sorted(self.shared_root.glob("*/*.json")) if source.strip().lower() in f.stem.lower()] \
            if self.shared_root.is_dir() and source.strip() else []
        if len(hits) == 1:
            return json.loads(hits[0].read_text(encoding="utf-8"))
        if not hits:
            raise Problem(f"No shared version matches '{source}', and it is not a file on this machine.")
        raise Problem(f"'{source}' matches several shared versions: {', '.join(f.stem for f in hits)}. Which one?")

    def adopt(self, source: str, confirm: bool = False, folder: str = "") -> str:
        v = self.locate(source)
        errs = validate(v)
        if errs:
            raise Problem("That file is not a valid version: " + "; ".join(errs))
        if v["kind"] == "upstream":
            return self._adopt_upstream(v, confirm, folder)
        cell = v["base"]["cell"]
        base = self.base_dir(cell)
        if not confirm:
            diffs = "\n".join(c["diff"] for c in v["changes"])
            return "\n".join([
                f"'{v['name']}' for {cell}, by {v['author']}" + (f" with {v['ai_assist']}" if v.get("ai_assist") else ""),
                f"What it is for: {v['wish']}",
                f"Files it changes: {', '.join(c['path'] for c in v['changes'])}",
                "This is someone else's code and it would run on this machine. Read the change before adopting:",
                diffs[:6000] + ("\n… (cut; open the file to read the rest)" if len(diffs) > 6000 else ""),
                "To adopt it, run version_adopt again with confirm set to true.",
            ])
        with tempfile.TemporaryDirectory() as tmp:
            trial = Path(tmp) / cell
            status, notes = apply_changes(base, v["changes"], trial)
            if status == "same":
                return f"Nothing to adopt: '{v['name']}' is already part of the original {cell}."
            if status == "conflict":
                raise Problem("Not adopted: it does not fit the current original. " + "; ".join(notes))
            ok, report = run_tests(trial, self._other_paths(cell))
            if ok is False:
                raise Problem("Not adopted: the tool's tests fail with this version here.\n" + report)
        out = self._need_home() / "saved" / cell / f"{v['id']}.json"
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps(v, indent=2) + "\n", encoding="utf-8")
        self.materialize(cell, v)
        state = self._state()
        entry = state["cells"].setdefault(cell, {"active": None, "history": []})
        entry.setdefault("history", []).append(entry.get("active"))
        entry["active"], entry["note"] = v["id"], ""
        self._save_state(state)
        self._commit(f"Adopt {v['id']} for {cell} (by {v['author']})")
        return "\n".join([
            f"Adopted and switched on: '{v['name']}' for {cell}." + (" Tests pass." if ok else ""),
            "Switch back any time. If it serves you, tell the commons so it counts toward becoming the original:",
            f"  add variants/adoptions/{v['id']}/<your-github-login>.json containing "
            + json.dumps({"variant": v["id"], "since": now()[:10]}),
        ])

    # -- tools that live outside the commons (a pinned upstream project in a local git clone) --
    def capture_upstream(self, folder: str, name: str, wish: str, author: str = "", ai_assist: str = "",
                         commit: str = "", upstream: str = "") -> str:
        repo = Path(folder).expanduser()
        git = lambda *a: subprocess.run(["git", "-C", str(repo), *a], capture_output=True, text=True)  # noqa: E731
        if not repo.is_dir() or git("rev-parse", "--is-inside-work-tree").returncode != 0:
            raise Problem(f"{folder} is not a git folder. Point at your local copy of the project.")
        base = commit.strip() or git("rev-parse", "HEAD").stdout.strip()
        git("add", "-A", "-N")
        patch = git("diff", "--binary", base).stdout
        if not patch.strip():
            raise Problem("That folder has no changes compared with its starting point.")
        v = {"format": FORMAT, "kind": "upstream", "id": variant_id(name, patch), "name": name.strip(), "wish": wish.strip() or name.strip(),
             "author": author.strip() or "me", "author_login": "", "ai_assist": ai_assist.strip(), "created": now(),
             "base": {"upstream": upstream.strip(), "repo": git("remote", "get-url", "origin").stdout.strip(), "commit": base},
             "status": "testing", "patch": patch}
        out = self._need_home() / "saved" / UPSTREAM / f"{v['id']}.json"
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps(v, indent=2) + "\n", encoding="utf-8")
        self._commit(f"Save my version of {upstream or repo.name}: {v['name']} — {v['wish']}")
        return (f"Saved '{v['name']}' ({v['id']}): your change to {upstream or repo.name}, as a patch on commit {base[:10]}. "
                "It is in your versions history. Share it with version_share; others apply it to their own copy with version_adopt.")

    def _adopt_upstream(self, v: dict, confirm: bool, folder: str) -> str:
        head = f"'{v['name']}' by {v['author']}: {v['wish']}\nA patch for {v['base'].get('repo') or v['base'].get('upstream')} at commit {v['base']['commit'][:10]}."
        if not confirm or not folder:
            return head + "\nThis is someone else's code. Read the patch before using it:\n" + v["patch"][:6000] + \
                "\nTo apply it, run version_adopt with confirm true and folder set to your local copy of that project."
        repo = Path(folder).expanduser()
        git = lambda *a, **k: subprocess.run(["git", "-C", str(repo), *a], capture_output=True, text=True, **k)  # noqa: E731
        if git("rev-parse", "HEAD").stdout.strip() != v["base"]["commit"]:
            raise Problem(f"Your copy is not at commit {v['base']['commit'][:10]}. Check that commit out first, then try again.")
        if git("apply", "--check", "-", input=v["patch"]).returncode != 0:
            raise Problem("The patch does not fit your copy (it may already be applied, or you have other changes).")
        git("apply", "-", input=v["patch"])
        return head + f"\nApplied to {repo}. Build and run it the way that project's own instructions say."


# ---------------- the commons side: who shared what, and who uses it ----------------

def shared_variants(root: Path = ROOT) -> list[dict]:
    folder = root / "variants" / "shared"
    return [json.loads(f.read_text(encoding="utf-8")) for f in sorted(folder.glob("*/*.json"))] if folder.is_dir() else []


def adopters(variant: dict, root: Path = ROOT) -> list[str]:
    folder = root / "variants" / "adoptions" / variant["id"]
    own = (variant.get("author_login") or "").lower()
    return sorted({f.stem.lower() for f in folder.glob("*.json")} - {own}) if folder.is_dir() else []


def standing(root: Path = ROOT) -> list[dict]:
    """Every shared variant with its honest adopter count and what should happen next."""
    rows = []
    for v in shared_variants(root):
        n = len(adopters(v, root))
        if v.get("status") == "canonical":
            nxt = "promoted: it is the original now"
        elif n >= PROMOTE_AT:
            nxt = "ready for a promotion decision (a person approves)"
        else:
            nxt = f"keep testing ({n} of {PROMOTE_AT} independent adopters)"
        fits = ""
        cell = v["base"].get("cell")
        if cell and (root / "cells" / cell).is_dir() and v.get("status") != "canonical":
            with tempfile.TemporaryDirectory() as tmp:
                status, _ = apply_changes(root / "cells" / cell, v["changes"], Path(tmp) / cell)
            fits = {"ok": "yes", "same": "already in the original", "conflict": "needs re-fitting"}[status]
            if status == "conflict":
                nxt = "needs re-fitting onto the updated original; " + nxt
        rows.append({"id": v["id"], "fits": fits, "tool": v["base"].get("cell") or v["base"].get("upstream") or v["base"].get("repo", ""),
                     "name": v["name"], "wish": v["wish"], "author": v["author"], "ai_assist": v.get("ai_assist", ""),
                     "created": v["created"][:10], "adopters": n, "status": v.get("status", "testing"), "next": nxt})
    return rows
