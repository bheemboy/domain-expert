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


def test_synth_tuning_defaults_when_absent(tmp_path, monkeypatch):
    _write(tmp_path, monkeypatch)  # config has no synth_tuning: block
    t = config.synth_tuning()
    assert t["default_batch"] == 12
    assert t["code"]["solo_lines"] == 1500
    assert t["jira"]["small_lines"] == 150
    assert t["doc"]["solo_lines"] == 700


def _write_with_tuning(tmp_path, monkeypatch):
    cfg = tmp_path / "wiki.config.yaml"
    cfg.write_text(textwrap.dedent("""
        project:
          key: TESTPROJ
          name: "Test Project"
          config_dir: ~/.config/testproj-wiki
        jira:
          base_url: https://example.atlassian.net
          jql: |
            project = TESTPROJ
        synth_tuning:
          code:
            solo_lines: 999
          default_batch: 20
    """))
    monkeypatch.setenv("WIKI_CONFIG", str(cfg))


def test_synth_tuning_override_merges_per_field(tmp_path, monkeypatch):
    _write_with_tuning(tmp_path, monkeypatch)
    t = config.synth_tuning()
    assert t["code"]["solo_lines"] == 999      # overridden
    assert t["code"]["small_lines"] == 400     # default preserved
    assert t["default_batch"] == 20            # overridden
    assert t["jira"]["solo_lines"] == 400      # untouched kind keeps defaults


def test_ignore_globs_defaults_when_absent(tmp_path, monkeypatch):
    _write(tmp_path, monkeypatch)  # config has no ignore: block
    globs = config.ignore_globs()
    assert "**/*.min.js" in globs
    assert "**/node_modules/**" in globs
    assert "**/*.svg" in globs
    # no user entries means just the baked defaults
    assert globs == config._IGNORE_DEFAULTS


def _write_with_ignore(tmp_path, monkeypatch):
    cfg = tmp_path / "wiki.config.yaml"
    cfg.write_text(textwrap.dedent("""
        project:
          key: TESTPROJ
          name: "Test Project"
          config_dir: ~/.config/testproj-wiki
        jira:
          base_url: https://example.atlassian.net
          jql: |
            project = TESTPROJ
        ignore:
          - ac_portal/local_modules/**
          - ac_ops/terraform/**
          - "**/*.min.js"
    """))
    monkeypatch.setenv("WIKI_CONFIG", str(cfg))


def test_ignore_globs_appends_user_entries_and_dedups(tmp_path, monkeypatch):
    _write_with_ignore(tmp_path, monkeypatch)
    globs = config.ignore_globs()
    # defaults still present
    assert "**/node_modules/**" in globs
    # user subtrees appended after defaults
    assert "ac_portal/local_modules/**" in globs
    assert "ac_ops/terraform/**" in globs
    # a user entry duplicating a default appears once, kept at its default position
    assert globs.count("**/*.min.js") == 1
    # defaults come before user-only entries
    assert globs.index("**/node_modules/**") < globs.index("ac_portal/local_modules/**")


def _write_docs_cfg(tmp_path, monkeypatch, docs_yaml: str):
    cfg = tmp_path / "wiki.config.yaml"
    cfg.write_text(
        "project:\n  key: T\n  name: T\n  config_dir: ~/.config/t-wiki\n"
        "jira:\n  base_url: https://example.atlassian.net\n  jql: |\n    project = T\n"
        + docs_yaml,
        encoding="utf-8",
    )
    monkeypatch.setenv("WIKI_CONFIG", str(cfg))


def test_docs_locations_empty_when_absent(tmp_path, monkeypatch):
    _write_docs_cfg(tmp_path, monkeypatch, "")  # no docs: block
    assert config.docs_locations() == []
    assert config.docs_config() == {}


def test_docs_locations_relative_resolves_to_wiki_root(tmp_path, monkeypatch):
    _write_docs_cfg(tmp_path, monkeypatch, "docs:\n  location: ../cid-docs\n")
    assert config.docs_locations() == [(tmp_path / "../cid-docs").resolve()]


def test_docs_locations_absolute_and_home_kept(tmp_path, monkeypatch):
    _write_docs_cfg(
        tmp_path, monkeypatch,
        "docs:\n  location:\n    - /opt/site-docs\n    - ~/work/help\n",
    )
    assert config.docs_locations() == [
        Path("/opt/site-docs"),
        Path("~/work/help").expanduser(),
    ]


def test_docs_include_exclude_defaults(tmp_path, monkeypatch):
    _write_docs_cfg(tmp_path, monkeypatch, "docs:\n  location: ./site\n")
    assert config.docs_include_globs() == ["**/*.md", "**/*.mdx"]
    assert config.docs_exclude_globs() == []


def test_docs_include_exclude_override(tmp_path, monkeypatch):
    _write_docs_cfg(
        tmp_path, monkeypatch,
        'docs:\n  location: ./site\n  include:\n    - "docs/**/*.md"\n'
        '  exclude:\n    - "**/node_modules/**"\n',
    )
    assert config.docs_include_globs() == ["docs/**/*.md"]
    assert config.docs_exclude_globs() == ["**/node_modules/**"]
