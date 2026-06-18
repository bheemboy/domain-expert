# tests/test_sources.py
import textwrap
from pathlib import Path

import pytest
import config
import sources


def _cfg(tmp_path, monkeypatch, repos):
    cfg = tmp_path / "wiki.config.yaml"
    repo_lines = "".join(f"\n        - {r}" for r in repos)
    cfg.write_text(textwrap.dedent(f"""
        project:
          key: TESTPROJ
          name: "T"
          config_dir: {tmp_path}/state
        jira:
          base_url: https://example.atlassian.net
          jql: |
            project = TESTPROJ
        sources:{repo_lines}
    """))
    monkeypatch.setenv("WIKI_CONFIG", str(cfg))
    return cfg


def test_clean_name_plain(tmp_path, monkeypatch):
    _cfg(tmp_path, monkeypatch, [])
    assert sources.clean_name(Path("/home/u/projects/work/asv")) == "asv"


def test_clean_name_nested_under_work(tmp_path, monkeypatch):
    _cfg(tmp_path, monkeypatch, [])
    assert sources.clean_name(Path("/home/u/projects/work/DEV/ac_docs")) == "DEV-ac_docs"


def test_source_order(tmp_path, monkeypatch):
    _cfg(tmp_path, monkeypatch, ["/home/u/projects/work/asv", "/home/u/projects/work/docs"])
    assert sources.source_order() == ["jira", "raw", "asv", "docs"]


def test_is_jira_key(tmp_path, monkeypatch):
    _cfg(tmp_path, monkeypatch, [])
    assert sources.is_jira_key("TESTPROJ-123") is True
    assert sources.is_jira_key("/abs/path/file.py") is False


def test_source_of_jira(tmp_path, monkeypatch):
    _cfg(tmp_path, monkeypatch, [])
    assert sources.source_of("TESTPROJ-42") == "jira"


def test_source_of_repo(tmp_path, monkeypatch):
    repo = tmp_path / "myrepo"
    (repo / "src").mkdir(parents=True)
    f = repo / "src" / "a.py"
    f.write_text("x")
    _cfg(tmp_path, monkeypatch, [str(repo)])
    assert sources.source_of(str(f)) == sources.clean_name(repo)


def test_source_of_raw(tmp_path, monkeypatch):
    _cfg(tmp_path, monkeypatch, [])
    monkeypatch.setattr(config, "wiki_root", lambda: tmp_path)
    raw_file = tmp_path / "raw" / "probe-source-of.txt"
    raw_file.parent.mkdir(parents=True, exist_ok=True)
    raw_file.write_text("x", encoding="utf-8")
    assert sources.source_of(str(raw_file)) == "raw"


def test_source_of_unknown_raises(tmp_path, monkeypatch):
    _cfg(tmp_path, monkeypatch, [])
    with pytest.raises(ValueError):
        sources.source_of("/nowhere/at/all/x.py")


def test_detect_repos_excludes_raw(tmp_path, monkeypatch):
    repo = tmp_path / "myrepo"
    repo.mkdir()
    _cfg(tmp_path, monkeypatch, [str(repo)])
    # detection covers external repos only — never raw/ (the wiki repo).
    assert sources.detect_repos() == [(repo, sources.clean_name(repo))]


def test_repo_relative_under_repo(tmp_path, monkeypatch):
    repo = tmp_path / "r"
    (repo / "a").mkdir(parents=True)
    f = repo / "a" / "b.md"
    f.write_text("x")
    _cfg(tmp_path, monkeypatch, [str(repo)])
    assert sources.repo_relative(str(f)) == "a/b.md"


def test_repo_relative_unknown_degrades_to_basename(tmp_path, monkeypatch):
    _cfg(tmp_path, monkeypatch, [])
    assert sources.repo_relative("/nowhere/x/y.md") == "y.md"
