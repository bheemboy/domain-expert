"""OKF-alignment checks in lint_wiki: title/description frontmatter, okf_version,
title↔H1 consistency, exact (builder-based) index drift, description warnings."""
from pathlib import Path

import build_index
import lint_wiki


def _page(desc="One-liner.", title="Alpha", h1=None, typ="entity"):
    return (
        f"---\ntitle: {title}\ndescription: {desc}\ntype: {typ}\n"
        f"status: current\nupdated: 2026-07-02\n---\n\n# {h1 or title}\n\nBody.\n"
    )


def _wiki(tmp_path, files, with_index=True):
    wiki = tmp_path / "wiki"
    for rel, text in files.items():
        p = wiki / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(text, encoding="utf-8")
    if with_index and not (wiki / "index.md").exists():
        catalog = build_index.render_catalog(wiki)
        (wiki / "index.md").write_text(
            '---\nokf_version: "0.1"\n---\n\n# Index\n\n' + catalog + "\n",
            encoding="utf-8")
    return wiki


def _linked(files):
    """Give every content page an inbound link so orphan checks stay quiet."""
    hub = "---\ntitle: Hub\ndescription: Hub.\ntype: concept\nstatus: current\nupdated: 2026-07-02\n---\n\n# Hub\n\n"
    for rel in list(files):
        slug = Path(rel).stem
        if slug not in ("index", "log", "overview"):
            hub += f"[[{slug}]] "
    files["concepts/hub.md"] = hub + "\n"
    return files


def test_title_and_description_required(tmp_path):
    page = "---\ntype: entity\nstatus: current\nupdated: 2026-07-02\n---\n\n# A\n\nBody.\n"
    wiki = _wiki(tmp_path, _linked({"entities/a.md": page}))
    issues = lint_wiki.lint(wiki)
    assert any("frontmatter-key-missing" in i and "(title)" in i for i in issues)
    assert any("frontmatter-key-missing" in i and "(description)" in i for i in issues)


def test_overview_frontmatter_now_checked_index_log_exempt(tmp_path):
    wiki = _wiki(tmp_path, {
        "overview.md": "# Overview\n\nNo frontmatter at all.\n",
        "log.md": "# Log\n",
    })
    issues = lint_wiki.lint(wiki)
    assert any("frontmatter-missing" in i and "overview" in i for i in issues)
    assert not any(("index" in i or "log.md" in i) and "frontmatter" in i for i in issues)


def test_okf_version_missing_flagged(tmp_path):
    files = _linked({"entities/a.md": _page()})
    wiki = _wiki(tmp_path, files, with_index=False)
    catalog = build_index.render_catalog(wiki)
    (wiki / "index.md").write_text("# Index\n\n" + catalog + "\n", encoding="utf-8")
    issues = lint_wiki.lint(wiki)
    assert any("okf-version-missing" in i for i in issues)
    # And silent when present (the default _wiki index carries it).
    wiki2 = _wiki(tmp_path / "w2", _linked({"entities/a.md": _page()}))
    assert not any("okf-version-missing" in i for i in lint_wiki.lint(wiki2))


def test_title_h1_mismatch_flagged(tmp_path):
    wiki = _wiki(tmp_path, _linked({"entities/a.md": _page(title="Alpha", h1="Alpha Prime")}))
    issues = lint_wiki.lint(wiki)
    assert any("title-h1-mismatch" in i and "entities/a.md" in i for i in issues)


def test_description_empty_flagged(tmp_path):
    wiki = _wiki(tmp_path, _linked({"entities/a.md": _page(desc='""')}))
    issues = lint_wiki.lint(wiki)
    assert any("description-empty" in i and "entities/a.md" in i for i in issues)


def test_index_drift_exact_via_builder(tmp_path):
    wiki = _wiki(tmp_path, _linked({"entities/a.md": _page()}))
    assert not any("index-drift" in i for i in lint_wiki.lint(wiki))
    # Hand-edit inside the marker region -> drift.
    index = wiki / "index.md"
    index.write_text(index.read_text(encoding="utf-8").replace(
        "One-liner.", "Hand-edited stale line."), encoding="utf-8")
    issues = lint_wiki.lint(wiki)
    assert any("index-drift" in i and "build_index.py" in i for i in issues)


def test_index_drift_when_page_missing_from_catalog(tmp_path):
    """A page absent from the catalog is drift even if its slug appears in prose."""
    files = _linked({"entities/a.md": _page(), "entities/b.md": _page(title="Beta")})
    wiki = _wiki(tmp_path, files)
    # Regenerate index for all, then delete b's bullet but mention it in prose.
    index = wiki / "index.md"
    text = index.read_text(encoding="utf-8")
    text = "\n".join(l for l in text.splitlines() if "[[entities/b]]" not in l)
    index.write_text(text + "\nProse mentions b though.\n", encoding="utf-8")
    assert any("index-drift" in i for i in lint_wiki.lint(wiki))


def test_description_long_is_warning_not_issue(tmp_path):
    wiki = _wiki(tmp_path, _linked({"entities/a.md": _page(desc="x" * 400)}))
    issues = lint_wiki.lint(wiki)
    assert not any("description-long" in i for i in issues)
    pages = sorted(wiki.rglob("*.md"))
    text = {p: p.read_text(encoding="utf-8") for p in pages}
    warns = lint_wiki._description_length_warns(pages, text)
    assert any("description-long" in w and "entities/a.md" in w for w in warns)
