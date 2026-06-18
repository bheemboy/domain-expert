import textwrap
import os
import importlib
from pathlib import Path

import config


def _write(tmp_path, monkeypatch):
    cfg = tmp_path / "wiki.config.yaml"
    cfg.write_text(textwrap.dedent("""
        project:
          key: TESTPROJ
          name: "Test Project"
          config_dir: ~/.config/testproj-wiki
        jira:
          base_url: https://example.atlassian.net
          jql: |
            project = TESTPROJ AND status = Done
        sources:
          - ~/projects/work/repoA
          - ~/projects/work/repoB
    """))
    monkeypatch.setenv("WIKI_CONFIG", str(cfg))
    return cfg


def test_project_identity(tmp_path, monkeypatch):
    _write(tmp_path, monkeypatch)
    assert config.project_key() == "TESTPROJ"
    assert config.project_name() == "Test Project"
    assert config.config_dir() == Path("~/.config/testproj-wiki").expanduser()


def test_jira_values(tmp_path, monkeypatch):
    _write(tmp_path, monkeypatch)
    assert config.jira_base_url() == "https://example.atlassian.net"
    assert config.jira_jql() == "project = TESTPROJ AND status = Done"


def test_source_repos_expanded(tmp_path, monkeypatch):
    _write(tmp_path, monkeypatch)
    repos = config.source_repos()
    assert repos == [
        Path("~/projects/work/repoA").expanduser(),
        Path("~/projects/work/repoB").expanduser(),
    ]


def test_missing_config_raises(tmp_path, monkeypatch):
    monkeypatch.setenv("WIKI_CONFIG", str(tmp_path / "nope.yaml"))
    try:
        config.project_key()
        assert False, "expected FileNotFoundError"
    except FileNotFoundError:
        pass


def _write_cfg(d: Path) -> Path:
    (d / "wiki.config.yaml").write_text(
        "project:\n  key: DEMO\n  name: Demo\n  config_dir: ~/.config/demo-wiki\n",
        encoding="utf-8",
    )
    return d


def test_wiki_root_walks_up_from_cwd(tmp_path, monkeypatch):
    root = _write_cfg(tmp_path)
    sub = root / "wiki" / "concepts"
    sub.mkdir(parents=True)
    monkeypatch.delenv("WIKI_CONFIG", raising=False)
    monkeypatch.chdir(sub)
    assert config.wiki_root() == root
    assert config.config_path() == root / "wiki.config.yaml"


def test_wiki_config_env_overrides_discovery(tmp_path, monkeypatch):
    cfg = _write_cfg(tmp_path) / "wiki.config.yaml"
    monkeypatch.setenv("WIKI_CONFIG", str(cfg))
    # cwd is irrelevant when WIKI_CONFIG is set
    monkeypatch.chdir(tmp_path.parent)
    assert config.config_path() == cfg
    assert config.wiki_root() == tmp_path


def test_wiki_root_raises_outside_a_wiki_repo(tmp_path, monkeypatch):
    monkeypatch.delenv("WIKI_CONFIG", raising=False)
    monkeypatch.chdir(tmp_path)  # empty dir, no wiki.config.yaml anywhere up to /
    import pytest
    with pytest.raises(FileNotFoundError) as e:
        config.wiki_root()
    assert "wiki.config.yaml" in str(e.value)


def test_key_of_uses_configured_prefix(tmp_path, monkeypatch):
    # ingest_state derives its Jira key regex from config.project_key().
    import os
    import importlib
    original_wiki_config = os.environ.get("WIKI_CONFIG")
    _write(tmp_path, monkeypatch)
    import ingest_state
    importlib.reload(ingest_state)  # pick up the TESTPROJ prefix from the temp config
    try:
        assert ingest_state.key_of("foo-testproj-123-story.md") == "TESTPROJ-123"
    finally:
        # Restore ingest_state to the original config (pytest_configure sets WIKI_CONFIG
        # to a CDS2ASV stub, so subsequent tests see the CDS2ASV prefix, not TESTPROJ).
        # monkeypatch auto-restores WIKI_CONFIG env var on teardown, but that happens
        # after this function returns; we restore manually here so the reload picks up
        # the correct config.
        if original_wiki_config is not None:
            os.environ["WIKI_CONFIG"] = original_wiki_config
        else:
            os.environ.pop("WIKI_CONFIG", None)
        importlib.reload(ingest_state)
