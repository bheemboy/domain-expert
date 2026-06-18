import lint_wiki


def _page(p, target):
    p.write_text(
        "---\ntype: concept\nstatus: current\nupdated: 2026-06-16\n---\n\n"
        f"# T\n\nDef.\n\n## References\n- [x]({target})\n"
    )


def test_flags_missing_import_link(tmp_path):
    wiki = tmp_path / "wiki"
    (wiki / "concepts").mkdir(parents=True)
    _page(wiki / "concepts" / "a.md", "../../raw/imports/jira/CDS2ASV-1.md")
    issues = lint_wiki.lint(wiki)
    assert any("missing-source-link" in i and "CDS2ASV-1" in i for i in issues)


def test_flags_stale_digest_link(tmp_path):
    wiki = tmp_path / "wiki"
    (wiki / "concepts").mkdir(parents=True)
    _page(wiki / "concepts" / "b.md", "../../digests/CDS2ASV-2.md")
    issues = lint_wiki.lint(wiki)
    assert any("stale-digest-link" in i and "CDS2ASV-2" in i for i in issues)
