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


def test_update_comment_puts_adf_to_comment_endpoint(monkeypatch):
    captured = {}

    class FakeResp:
        status_code = 200
        text = ""

    def fake_put(url, headers=None, auth=None, json=None):
        captured["url"] = url
        captured["json"] = json
        return FakeResp()

    monkeypatch.setattr(jira_utils.requests, "put", fake_put)
    jira_utils.update_comment("OLAC-1", "10042", "hello **world**")
    assert captured["url"].endswith("/rest/api/3/issue/OLAC-1/comment/10042")
    assert captured["json"]["body"]["type"] == "doc"


def test_update_comment_loud_failure(monkeypatch):
    class FakeResp:
        status_code = 400
        text = "no such comment"

    monkeypatch.setattr(jira_utils.requests, "put",
                        lambda *a, **k: FakeResp())
    import pytest
    with pytest.raises(SystemExit) as exc:
        jira_utils.update_comment("OLAC-1", "10042", "body")
    assert "400" in str(exc.value)


def test_comment_summaries_ids_authors_and_bot_flag():
    def adf(text):
        return {"type": "doc", "version": 1, "content": [
            {"type": "paragraph", "content": [{"type": "text", "text": text}]}]}
    issue = {"key": "OLAC-1", "fields": {"comment": {"comments": [
        {"id": "10001", "author": {"displayName": "Human"},
         "created": "2026-07-06T10:00:00.000+0000", "body": adf("real words")},
        {"id": "10002", "author": {"displayName": "Bot"},
         "created": "2026-07-06T11:00:00.000+0000",
         "body": adf("🤖 Automated defect review — old style verdict")},
    ]}}}
    out = jira_utils.comment_summaries(issue, "🤖 Automated defect review")
    assert [s["id"] for s in out] == ["10001", "10002"]
    assert out[0]["bot"] is False and out[1]["bot"] is True
    assert out[1]["preview"].startswith("🤖 Automated defect review")
    assert out[0]["author"] == "Human"


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
