import json
import textwrap
from datetime import datetime, timezone

import defect_review_scan as scan


def _cfg(tmp_path, monkeypatch, jql='issuetype = Bug AND status = "New"'):
    cfg = tmp_path / "wiki.config.yaml"
    cfg.write_text(textwrap.dedent(f"""
        project:
          key: OLAC
          name: "CID"
          config_dir: {tmp_path}/config
        jira:
          base_url: https://example.atlassian.net
          jql: |
            project = OLAC
        defect_review:
          enabled: true
          candidate_jql: '{jql}'
    """))
    monkeypatch.setenv("WIKI_CONFIG", str(cfg))
    monkeypatch.setenv("STATE_DIR", str(tmp_path / "state"))


def _issue(key="OLAC-1", updated="2026-07-04T09:00:00.000+0000", comments=None):
    return {"key": key, "fields": {
        "summary": "s", "updated": updated,
        "comment": {"comments": comments or []},
    }}


def _comment(text, created=None, updated=None):
    c = {"body": {"type": "doc", "version": 1, "content": [
        {"type": "paragraph", "content": [{"type": "text", "text": text}]}]}}
    if created:
        c["created"] = created
    if updated:
        c["updated"] = updated
    return c


NOW = datetime(2026, 7, 4, 9, 30, tzinfo=timezone.utc)
MARKER = "🤖 Automated defect review —"
NEW_MARKER = "🤖 Automated defect review"


def test_old_marker_comments_still_skip_with_new_marker(tmp_path, monkeypatch):
    """No-retrigger guarantee: tickets reviewed under the old marker must
    stay skipped after the marker change (spec §2, no-retrigger)."""
    _cfg(tmp_path, monkeypatch)
    issue = _issue(comments=[_comment("user words"),
                             _comment(f"{MARKER} need details")])  # OLD marker
    entry = {"emailed_for_updated": None, "question_rounds": 0, "pending_asks": []}
    assert scan.skip_reason(issue, NEW_MARKER, entry, NOW) == "bot-spoke-last"


def test_new_default_marker_is_prefix_of_old(tmp_path, monkeypatch):
    _cfg(tmp_path, monkeypatch)
    import config as cfg_mod
    new = cfg_mod.defect_review_config()["marker"]
    assert new == NEW_MARKER
    assert MARKER.startswith(new), "marker change broke prefix-compatibility"


def test_candidate_jql_wraps_config(tmp_path, monkeypatch):
    _cfg(tmp_path, monkeypatch)
    assert scan.candidate_jql() == 'project = OLAC AND (issuetype = Bug AND status = "New")'


def test_cooldown_blocks_recent_activity():
    assert scan.in_cooldown("2026-07-04T09:25:00.000+0000", NOW) is True
    assert scan.in_cooldown("2026-07-04T09:00:00.000+0000", NOW) is False


def test_skip_bot_spoke_last(tmp_path, monkeypatch):
    _cfg(tmp_path, monkeypatch)
    issue = _issue(comments=[_comment("user words"), _comment(f"{MARKER} need details")])
    entry = {"emailed_for_updated": None, "question_rounds": 0, "pending_asks": []}
    assert scan.skip_reason(issue, MARKER, entry, NOW) == "bot-spoke-last"


def test_skip_email_pending_same_updated(tmp_path, monkeypatch):
    _cfg(tmp_path, monkeypatch)
    issue = _issue(updated="2026-07-04T09:00:00.000+0000")
    entry = {"emailed_for_updated": "2026-07-04T09:00:00.000+0000",
             "question_rounds": 1, "pending_asks": []}
    assert scan.skip_reason(issue, MARKER, entry, NOW) == "email-pending"


def test_new_activity_after_email_is_reviewable(tmp_path, monkeypatch):
    _cfg(tmp_path, monkeypatch)
    issue = _issue(updated="2026-07-04T09:10:00.000+0000",
                   comments=[_comment(f"{MARKER} asked"), _comment("submitter answer")])
    entry = {"emailed_for_updated": "2026-07-04T08:00:00.000+0000",
             "question_rounds": 1, "pending_asks": []}
    assert scan.skip_reason(issue, MARKER, entry, NOW) is None


def test_clean_new_ticket_is_reviewable(tmp_path, monkeypatch):
    _cfg(tmp_path, monkeypatch)
    issue = _issue()
    entry = {"emailed_for_updated": None, "question_rounds": 0, "pending_asks": []}
    assert scan.skip_reason(issue, MARKER, entry, NOW) is None


# ── reviewed gate (update-in-place: bot is no longer the last commenter) ──

T1 = "2026-07-03T10:00:00.000+0000"
T2 = "2026-07-04T08:00:00.000+0000"


def test_skip_reviewed_when_no_new_human_comment(tmp_path, monkeypatch):
    _cfg(tmp_path, monkeypatch)
    issue = _issue(comments=[_comment(f"{MARKER} asked", created=T1),
                             _comment("submitter answer", created=T2)])
    entry = {"question_rounds": 1, "pending_asks": [], "last_human_comment": T2}
    assert scan.skip_reason(issue, MARKER, entry, NOW) == "reviewed"


def test_newer_human_comment_is_reviewable(tmp_path, monkeypatch):
    _cfg(tmp_path, monkeypatch)
    issue = _issue(comments=[_comment(f"{MARKER} assessed", created=T1),
                             _comment("dev finding", created=T2)])
    entry = {"question_rounds": 0, "pending_asks": [], "last_human_comment": T1}
    assert scan.skip_reason(issue, MARKER, entry, NOW) is None


def test_legacy_entry_unknown_sentinel_forces_review(tmp_path, monkeypatch):
    _cfg(tmp_path, monkeypatch)
    issue = _issue(comments=[_comment(f"{MARKER} assessed", created=T1),
                             _comment("dev finding", created=T2)])
    entry = {"question_rounds": 0, "pending_asks": [],
             "last_human_comment": "unknown"}
    assert scan.skip_reason(issue, MARKER, entry, NOW) is None


def test_recorded_null_skips_while_no_human_comments(tmp_path, monkeypatch):
    _cfg(tmp_path, monkeypatch)
    issue = _issue(comments=[])
    entry = {"question_rounds": 0, "pending_asks": [], "last_human_comment": None}
    assert scan.skip_reason(issue, MARKER, entry, NOW) == "reviewed"


def test_newest_human_comment_ignores_bot_comments():
    issue = _issue(comments=[
        _comment("user words", created=T1, updated=T1),
        _comment(f"{MARKER} assessment", created=T2, updated=T2),  # bot edit later
    ])
    assert scan.newest_human_comment(issue, MARKER) == T1


def test_newest_human_comment_none_without_humans():
    issue = _issue(comments=[_comment(f"{MARKER} assessment", created=T1)])
    assert scan.newest_human_comment(issue, MARKER) is None


def test_main_emits_state_fields(tmp_path, monkeypatch, capsys):
    _cfg(tmp_path, monkeypatch)
    import jira_utils
    monkeypatch.setattr(jira_utils, "require_credentials", lambda: None)
    issue = _issue(comments=[_comment("user words", created=T1)])
    monkeypatch.setattr(jira_utils, "fetch_issues", lambda jql: [issue])
    monkeypatch.setattr("sys.argv", ["defect_review_scan.py"])
    scan.main()
    rec = json.loads(capsys.readouterr().out.strip())
    assert rec["last_human_comment"] == T1
    assert rec["disposition_code"] is None
    assert rec["disposition"] is None
