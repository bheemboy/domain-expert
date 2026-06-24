from pathlib import Path

import config  # noqa: F401 (ensures scripts/ on path via conftest)
import doc_target
import pytest


def _write_cfg(tmp_path, monkeypatch, docs_block: str):
    cfg = tmp_path / "wiki.config.yaml"
    cfg.write_text(
        "project:\n  key: T\n  name: T\n  config_dir: ~/.config/t\n"
        "jira:\n  base_url: https://x\n  jql: |\n    project = T\n"
        + docs_block,
        encoding="utf-8",
    )
    monkeypatch.setenv("WIKI_CONFIG", str(cfg))


def test_slugify_basic():
    assert doc_target.slugify("My New Page!") == "my-new-page"
    assert doc_target.slugify("  Spaces  and---dashes  ") == "spaces-and-dashes"
    assert doc_target.slugify("Activate & Connect (v2)") == "activate-connect-v2"


def test_default_target_uses_first_docs_location(tmp_path, monkeypatch):
    site = tmp_path / "site"
    _write_cfg(tmp_path, monkeypatch, f"docs:\n  location: {site}\n")
    assert doc_target.default_doc_target("Getting Started") == site / "getting-started.md"


def test_default_target_first_of_many(tmp_path, monkeypatch):
    a, b = tmp_path / "a", tmp_path / "b"
    _write_cfg(tmp_path, monkeypatch, f"docs:\n  location:\n    - {a}\n    - {b}\n")
    assert doc_target.default_doc_target("X").parent == a


def test_default_target_raises_without_docs(tmp_path, monkeypatch):
    _write_cfg(tmp_path, monkeypatch, "")  # no docs: block
    with pytest.raises(ValueError):
        doc_target.default_doc_target("X")


def test_default_target_raises_on_empty_slug(tmp_path, monkeypatch):
    site = tmp_path / "site"
    _write_cfg(tmp_path, monkeypatch, f"docs:\n  location: {site}\n")
    with pytest.raises(ValueError):
        doc_target.default_doc_target("!!!")
