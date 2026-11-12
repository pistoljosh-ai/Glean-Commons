#!/usr/bin/env python3
"""End to end: speak a change to a tool, keep it, switch, share, adopt. Stdlib only."""

import shutil
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import server as S  # noqa: E402

OLD, NEW = r"Thank you,\n{business}", r"With thanks,\n{business}"
TODAY = {"business_name": "Demo Co", "today": "2026-11-06"}


def call(srv, tool_name, **args):
    r = srv.call(tool_name, args)
    assert not r["isError"], r
    return r["content"][0]["text"]


def books_with_a_late_invoice(srv):
    call(srv, "add_offer", name="House wash", price=350)
    call(srv, "add_customer", name="Hendricks Family", email="h@example.com")
    call(srv, "add_job", customer="hendricks", offer="house", status="done")
    call(srv, "create_invoice", job="hendricks", issued_date="2026-09-01", terms_days=15)


def test_speak_a_change_and_keep_it():
    tmp = Path(tempfile.mkdtemp())
    try:
        maria = S.Server(tmp / "maria-books")
        books_with_a_late_invoice(maria)
        assert "Thank you," in call(maria, "draft_payment_reminders", **TODAY)

        # the front door understands "I want it different"
        for said, tool in {"customize how my reminders sound": "version_start", "customize the invoice tool": "version_start",
                           "I want the reminder to be worded differently": "version_start", "switch back to the original": "version_switch",
                           "what versions have people shared": "shared_versions", "try the version someone else made": "version_adopt",
                           "who owes me money?": "open_invoices", "what changed today": "history"}.items():
            assert S.rank_tools(said, maria.tools)[0][1] == tool, (said, S.rank_tools(said, maria.tools))
        assert "version_start" in call(maria, "do", request="chase the late payers")

        out = call(maria, "version_start", tool="draft_payment_reminders", wish="sign off the final notice more warmly")
        assert "Private working copy ready for 'invoice-followup'" in out
        assert OLD in call(maria, "version_read", tool="invoice-followup", file="followup.py")
        call(maria, "version_edit", tool="invoice-followup", file="followup.py", find=OLD, replace=NEW)
        assert call(maria, "version_test", tool="invoice-followup").startswith("Tests pass")
        assert "Thank you," in call(maria, "draft_payment_reminders", **TODAY)  # not live until saved
        assert "Saved and switched on" in call(maria, "version_save", tool="invoice-followup", name="warm sign-off", author="Maria")

        assert "With thanks," in call(maria, "draft_payment_reminders", **TODAY)  # her tools now run her version
        assert "Owed to you:      $350.00" in call(maria, "business_status", today="2026-11-06")  # everything else still works
        assert "running warm-sign-off" in call(maria, "my_versions")
        assert OLD in (S.CELLS / "invoice-followup" / "followup.py").read_text()  # the commons is untouched

        call(maria, "version_switch", tool="draft_payment_reminders", to="original")
        assert "Thank you," in call(maria, "draft_payment_reminders", **TODAY)
        call(maria, "version_switch", tool="draft_payment_reminders", to="previous")
        assert "With thanks," in call(maria, "draft_payment_reminders", **TODAY)

        # it survives a restart
        again = S.Server(tmp / "maria-books")
        assert "With thanks," in call(again, "draft_payment_reminders", **TODAY)

        # share one file; someone else adopts it after seeing the change
        shared = call(maria, "version_share", tool="invoice-followup", author="Maria Example", github_login="maria")
        path = next((tmp / "maria-books-versions" / "outbox").glob("warm-sign-off-*.json"))
        assert str(path) in shared and "h@example.com" not in path.read_text()  # no business data in it
        sam = S.Server(tmp / "sam-books")
        books_with_a_late_invoice(sam)
        preview = call(sam, "version_adopt", source=str(path))
        assert "someone else's code" in preview and "Thank you," in call(sam, "draft_payment_reminders", **TODAY)
        assert "Adopted and switched on" in call(sam, "version_adopt", source=str(path), confirm=True)
        assert "With thanks," in call(sam, "draft_payment_reminders", **TODAY)

        # a version that breaks falls back to the original instead of taking the tools down
        (tmp / "maria-books-versions" / "active" / "invoice-followup" / "tools.py").write_text("raise RuntimeError('boom')\n")
        maria.reload()
        out = call(maria, "draft_payment_reminders", **TODAY)
        assert "failed to load" in out and "running the original instead" in out and "Thank you," in out
        # and the next start rebuilds her version from her saved history
        healed = S.Server(tmp / "maria-books")
        assert "With thanks," in call(healed, "draft_payment_reminders", **TODAY)
    finally:
        shutil.rmtree(tmp)


def test_needs_input_not_crashes():
    tmp = Path(tempfile.mkdtemp())
    try:
        srv = S.Server(tmp / "books")
        assert call(srv, "version_test", tool="invoice-followup").startswith("NEEDS INPUT: No change in progress")
        assert call(srv, "version_start", tool="zzzz qqqq", wish="x").startswith("NEEDS INPUT: Which tool")
        assert "no versions of your own yet" in call(srv, "my_versions")
        assert not (tmp / "books-versions").exists()  # looking creates nothing
    finally:
        shutil.rmtree(tmp)


def test_public_endpoint_only_browses():
    srv = S.Server(None, public=True)
    names = set(srv.tools)
    assert "shared_versions" in names and not names & {"version_start", "version_save", "version_adopt", "my_versions"}
    assert srv.variants is None
    assert "Unknown tool" in srv.call("version_save", {"tool": "x", "name": "y"})["content"][0]["text"]
    assert isinstance(call(srv, "shared_versions"), str)


if __name__ == "__main__":
    for name, fn in list(globals().items()):
        if name.startswith("test_"):
            fn()
    print("OK: your-own-version tools pass end to end")
