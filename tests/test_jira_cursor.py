import json
import textwrap

import jira_cursor


def _cfg(tmp_path, monkeypatch, *, key="TESTPROJ"):
    """Point WIKI_CONFIG at a temp project and STATE_DIR at a temp dir.
    jira-cursor.json lives in STATE_DIR (alongside the work queues)."""
    state_dir = tmp_path / "state"
    state_dir.mkdir(parents=True, exist_ok=True)
    cfg = tmp_path / "wiki.config.yaml"
    cfg.write_text(textwrap.dedent(f"""
        project:
          key: {key}
          name: "Test Project"
          config_dir: {tmp_path / "config"}
        jira:
          base_url: https://example.atlassian.net
          jql: |
            project = {key}
        sources: []
    """))
    monkeypatch.setenv("WIKI_CONFIG", str(cfg))
    monkeypatch.setenv("STATE_DIR", str(state_dir))
    return state_dir


def test_missing_is_none(tmp_path, monkeypatch):
    _cfg(tmp_path, monkeypatch)
    assert jira_cursor.get("TESTPROJ") is None


def test_roundtrips_per_project(tmp_path, monkeypatch):
    _cfg(tmp_path, monkeypatch)
    jira_cursor.advance("PROJA", "2026-01-01")
    jira_cursor.advance("PROJB", "2026-02-02")
    assert jira_cursor.get("PROJA") == "2026-01-01"
    assert jira_cursor.get("PROJB") == "2026-02-02"


def test_lives_in_state_dir_and_is_flat(tmp_path, monkeypatch):
    sd = _cfg(tmp_path, monkeypatch)
    jira_cursor.advance("TESTPROJ", "2026-06-16")
    data = json.loads((sd / "jira-cursor.json").read_text())
    assert data == {"TESTPROJ": "2026-06-16"}    # flat project-key → date, no wrapper


def test_get_alone_does_not_write(tmp_path, monkeypatch):
    sd = _cfg(tmp_path, monkeypatch)
    assert jira_cursor.get("TESTPROJ") is None
    assert not (sd / "jira-cursor.json").is_file()   # load is pure


def test_corrupt_file_treated_as_empty(tmp_path, monkeypatch):
    sd = _cfg(tmp_path, monkeypatch)
    (sd / "jira-cursor.json").write_text("{ not json")
    assert jira_cursor.get("TESTPROJ") is None    # does not raise
