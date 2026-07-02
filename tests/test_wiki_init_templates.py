from pathlib import Path

import build_index
import lint_wiki

REPO = Path(__file__).resolve().parent.parent
TEMPLATES = REPO / "skills" / "wiki-init" / "templates"
TMPL = TEMPLATES / "wiki.config.yaml.tmpl"


def _scaffold(tmp_path):
    """A fresh wiki as /wiki-init would scaffold it (placeholders substituted)."""
    subs = {"{{PRODUCT_NAME}}": "Prod", "{{INTERNAL_NAME}}": "prod", "{{TODAY}}": "2026-07-02"}
    wiki = tmp_path / "wiki"
    wiki.mkdir()
    for src in (TEMPLATES / "wiki").glob("*.md"):
        text = src.read_text(encoding="utf-8")
        for k, v in subs.items():
            text = text.replace(k, v)
        (wiki / src.name).write_text(text, encoding="utf-8")
    for folder in ("entities", "concepts", "processes", "rules", "terminology"):
        (wiki / folder).mkdir()
    return wiki


def test_fresh_scaffold_lints_clean(tmp_path):
    """The scaffolded wiki must satisfy every mechanical check out of the box:
    OKF frontmatter on overview, okf_version + a catalog region that exactly
    matches what build_index renders."""
    wiki = _scaffold(tmp_path)
    assert lint_wiki.lint(wiki) == []


def test_index_template_markers_match_builder(tmp_path):
    wiki = _scaffold(tmp_path)
    index_text = (wiki / "index.md").read_text(encoding="utf-8")
    assert build_index.MARKER_BEGIN in index_text
    assert build_index.MARKER_END in index_text
    assert 'okf_version: "0.1"' in index_text


def test_log_template_describes_okf_prepend_convention():
    text = (TEMPLATES / "wiki" / "log.md").read_text(encoding="utf-8")
    assert "newest first" in text and "## YYYY-MM-DD" in text
    assert "head -30" in text and "prepended" in text


def test_config_template_has_docs_block():
    text = TMPL.read_text(encoding="utf-8")
    # A commented docs: block documents how to point at customer-facing help.
    assert "docs:" in text
    assert "location:" in text
    # It must be commented so a fresh config doesn't enable an empty docs lens.
    docs_line = next(ln for ln in text.splitlines() if "docs:" in ln)
    assert docs_line.lstrip().startswith("#"), "docs: block should ship commented out"
