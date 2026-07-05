import jira_utils


def test_build_notify_payload_shape():
    p = jira_utils.build_notify_payload("Review: OLAC-1", "body text", "abc123")
    assert p == {
        "subject": "Review: OLAC-1",
        "textBody": "body text",
        "to": {"users": [{"accountId": "abc123"}]},
    }


def test_resolve_account_id_passthrough_for_non_email():
    assert jira_utils.resolve_account_id("5b10ac8d82e05b22cc7d4ef5") == "5b10ac8d82e05b22cc7d4ef5"


def test_post_comment_body_is_adf(monkeypatch):
    captured = {}

    class FakeResp:
        status_code = 201
        text = ""

    def fake_post(url, headers=None, auth=None, json=None):
        captured["url"] = url
        captured["json"] = json
        return FakeResp()

    monkeypatch.setattr(jira_utils.requests, "post", fake_post)
    jira_utils.post_comment("OLAC-1", "hello **world**")
    assert captured["url"].endswith("/rest/api/3/issue/OLAC-1/comment")
    assert captured["json"]["body"]["type"] == "doc"


def test_notify_issue_loud_failure(monkeypatch):
    class FakeResp:
        status_code = 403
        text = "notifications disabled"

    monkeypatch.setattr(jira_utils.requests, "post",
                        lambda *a, **k: FakeResp())
    import pytest
    with pytest.raises(SystemExit) as exc:
        jira_utils.notify_issue("OLAC-1", "s", "b", "abc123")
    assert "403" in str(exc.value)
