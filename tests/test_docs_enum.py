from pathlib import Path

import config  # noqa: F401  (ensures scripts/ on path via conftest)
import docs_enum


def _make_site(root: Path):
    (root / "docs" / "api").mkdir(parents=True)
    (root / "docs" / "intro.md").write_text("# intro", encoding="utf-8")
    (root / "docs" / "guide.mdx").write_text("# guide", encoding="utf-8")
    (root / "docs" / "notes.txt").write_text("notes", encoding="utf-8")
    (root / "docs" / "api" / "ref.md").write_text("# ref", encoding="utf-8")
    (root / "node_modules").mkdir()
    (root / "node_modules" / "junk.md").write_text("# junk", encoding="utf-8")


def _write_cfg(tmp_path, monkeypatch, body: str):
    cfg = tmp_path / "wiki.config.yaml"
    cfg.write_text(
        "project:\n  key: T\n  name: T\n  config_dir: ~/.config/t-wiki\n"
        "jira:\n  base_url: https://example.atlassian.net\n  jql: |\n    project = T\n"
        + body,
        encoding="utf-8",
    )
    monkeypatch.setenv("WIKI_CONFIG", str(cfg))


def test_enumerate_empty_without_docs_block(tmp_path, monkeypatch):
    _write_cfg(tmp_path, monkeypatch, "")
    assert docs_enum.enumerate_docs() == []


def test_enumerate_default_md_and_mdx(tmp_path, monkeypatch):
    site = tmp_path / "site"
    _make_site(site)
    _write_cfg(tmp_path, monkeypatch, f"docs:\n  location: {site}\n")
    names = {p.name for p in docs_enum.enumerate_docs()}
    # .md and .mdx in, .txt out; no exclude by default so node_modules/junk.md is in
    assert names == {"intro.md", "guide.mdx", "ref.md", "junk.md"}


def test_enumerate_respects_exclude(tmp_path, monkeypatch):
    site = tmp_path / "site"
    _make_site(site)
    _write_cfg(
        tmp_path, monkeypatch,
        f'docs:\n  location: {site}\n  exclude:\n    - "**/node_modules/**"\n',
    )
    names = {p.name for p in docs_enum.enumerate_docs()}
    assert names == {"intro.md", "guide.mdx", "ref.md"}


def test_enumerate_include_override_md_only(tmp_path, monkeypatch):
    site = tmp_path / "site"
    _make_site(site)
    _write_cfg(
        tmp_path, monkeypatch,
        f'docs:\n  location: {site}\n  include:\n    - "**/*.md"\n',
    )
    names = {p.name for p in docs_enum.enumerate_docs()}
    assert "guide.mdx" not in names
    assert "intro.md" in names


def test_enumerate_returns_absolute_sorted_paths(tmp_path, monkeypatch):
    site = tmp_path / "site"
    _make_site(site)
    _write_cfg(
        tmp_path, monkeypatch,
        f'docs:\n  location: {site}\n  exclude:\n    - "**/node_modules/**"\n',
    )
    paths = docs_enum.enumerate_docs()
    assert all(p.is_absolute() for p in paths)
    assert paths == sorted(paths)
