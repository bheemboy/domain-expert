from pathlib import Path

import config  # noqa: F401 (ensures scripts/ on path via conftest)
import doc_scope
import pytest


def _make_site(root: Path):
    (root / "docs").mkdir(parents=True)
    (root / "docs" / "intro.md").write_text("# intro", encoding="utf-8")
    (root / "docs" / "guide.mdx").write_text("# guide", encoding="utf-8")
    (root / "docs" / "notes.txt").write_text("notes", encoding="utf-8")


def _write_cfg(tmp_path, monkeypatch, docs_dir):
    cfg = tmp_path / "wiki.config.yaml"
    cfg.write_text(
        "project:\n  key: T\n  name: T\n  config_dir: ~/.config/t\n"
        "jira:\n  base_url: https://x\n  jql: |\n    project = T\n"
        f"docs:\n  location: {docs_dir}\n",
        encoding="utf-8",
    )
    monkeypatch.setenv("WIKI_CONFIG", str(cfg))


def test_resolve_none_returns_all_configured_docs(tmp_path, monkeypatch):
    site = tmp_path / "site"
    _make_site(site)
    _write_cfg(tmp_path, monkeypatch, site)
    names = {p.name for p in doc_scope.resolve_docs(None)}
    assert names == {"intro.md", "guide.mdx"}  # .txt excluded by default globs


def test_resolve_single_file(tmp_path, monkeypatch):
    site = tmp_path / "site"
    _make_site(site)
    _write_cfg(tmp_path, monkeypatch, site)
    f = site / "docs" / "intro.md"
    assert doc_scope.resolve_docs(str(f)) == [f.resolve()]


def test_resolve_directory_lists_md_and_mdx(tmp_path, monkeypatch):
    site = tmp_path / "site"
    _make_site(site)
    _write_cfg(tmp_path, monkeypatch, site)
    names = {p.name for p in doc_scope.resolve_docs(str(site / "docs"))}
    assert names == {"intro.md", "guide.mdx"}


def test_resolve_missing_path_raises(tmp_path, monkeypatch):
    _write_cfg(tmp_path, monkeypatch, tmp_path / "site")
    with pytest.raises(FileNotFoundError):
        doc_scope.resolve_docs(str(tmp_path / "nope"))


def test_shard_docs_partitions_in_order():
    docs = [Path(f"/d/{i}.md") for i in range(5)]
    assert doc_scope.shard_docs(docs, 2) == [docs[0:2], docs[2:4], docs[4:5]]


def test_shard_docs_rejects_bad_size():
    with pytest.raises(ValueError):
        doc_scope.shard_docs([Path("/d/a.md")], 0)
