"""Sanity checks for Composio per-toolkit priority slug lists."""

from src.integrations import composio


def test_gmail_priority_includes_send_and_draft_flow():
    slugs = composio._COMPOSIO_PRIORITY_SLUGS_BY_TOOLKIT.get("GMAIL", ())
    assert "GMAIL_CREATE_EMAIL_DRAFT" in slugs
    assert "GMAIL_SEND_DRAFT" in slugs
    assert "GMAIL_SEND_EMAIL" in slugs
    assert "GMAIL_FETCH_EMAILS" in slugs
