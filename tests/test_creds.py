import jira_utils


def test_load_credentials_from_file(tmp_path, monkeypatch):
    f = tmp_path / "jira.token"
    f.write_text("JIRA_EMAIL=a@b.com\nJIRA_TOKEN=secret123\n", encoding="utf-8")
    monkeypatch.delenv("JIRA_EMAIL", raising=False)
    monkeypatch.delenv("JIRA_TOKEN", raising=False)
    email, token = jira_utils.load_credentials(path=f)
    assert email == "a@b.com"
    assert token == "secret123"


def test_env_overrides_when_file_missing(tmp_path, monkeypatch):
    monkeypatch.setenv("JIRA_EMAIL", "env@b.com")
    monkeypatch.setenv("JIRA_TOKEN", "envtoken")
    email, token = jira_utils.load_credentials(path=tmp_path / "nope.token")
    assert (email, token) == ("env@b.com", "envtoken")
