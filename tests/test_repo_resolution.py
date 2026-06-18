import textwrap
from pathlib import Path

import ingest_state


def _cfg(tmp_path, monkeypatch, sources):
    state_dir = tmp_path / "state"; state_dir.mkdir(parents=True, exist_ok=True)
    src_yaml = "".join(f"\n          - {s}" for s in sources) or " []"
    cfg = tmp_path / "wiki.config.yaml"
    cfg.write_text(textwrap.dedent(f"""
        project: {{key: TESTPROJ, name: T, config_dir: {state_dir}}}
        jira: {{base_url: https://e.example, jql: 'project = TESTPROJ'}}
        sources:{src_yaml}
    """))
    monkeypatch.setenv("WIKI_CONFIG", str(cfg))


def test_repo_relative_under_configured_source(tmp_path, monkeypatch):
    repo = tmp_path / "repoA"; (repo / "docs").mkdir(parents=True)
    f = repo / "docs" / "x.pdf"; f.write_text("x")
    _cfg(tmp_path, monkeypatch, sources=[str(repo)])
    assert ingest_state.repo_relative(str(f)) == "docs/x.pdf"
    assert ingest_state.repo_root_of(str(f)) == repo.resolve()


def test_repo_relative_relative_path_unchanged(tmp_path, monkeypatch):
    _cfg(tmp_path, monkeypatch, sources=[])
    assert ingest_state.repo_relative("docs/x.pdf") == "docs/x.pdf"


def test_repo_relative_outside_roots_is_basename(tmp_path, monkeypatch):
    _cfg(tmp_path, monkeypatch, sources=[])
    assert ingest_state.repo_relative("/somewhere/else/y.pdf") == "y.pdf"


def test_key_of_doc_resolves_to_repo_relative(tmp_path, monkeypatch):
    repo = tmp_path / "repoA"; (repo / "docs").mkdir(parents=True)
    f = repo / "docs" / "x.pdf"; f.write_text("x")
    _cfg(tmp_path, monkeypatch, sources=[str(repo)])
    assert ingest_state.key_of(str(f)) == ingest_state.doc_key("docs/x.pdf")
