import textwrap
from pathlib import Path

import build_index


def _page(desc=None, title="T", typ="entity"):
    fm = [f"title: {title}", f"type: {typ}", "status: current", "updated: 2026-07-02"]
    if desc is not None:
        fm.insert(1, f"description: {desc}")
    return "---\n" + "\n".join(fm) + f"\n---\n\n# {title}\n\nBody.\n"


def _wiki(tmp_path, files):
    wiki = tmp_path / "wiki"
    for rel, text in files.items():
        p = wiki / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(text, encoding="utf-8")
    return wiki


def test_render_catalog_groups_orders_and_links():
    """Fixed section order, alphabetical slugs, folder-qualified wikilinks."""
    files = {
        "overview.md": _page("Start here.", title="Overview"),
        "entities/beta.md": _page("Second entity."),
        "entities/alpha.md": _page("First entity."),
        "concepts/gamma.md": _page("A concept.", typ="concept"),
        "custom/thing.md": _page("Custom folder page.", typ="concept"),
        "index.md": "# Index\n",
        "log.md": "# Log\n",
    }
    import tempfile
    with tempfile.TemporaryDirectory() as td:
        wiki = _wiki(Path(td), files)
        cat = build_index.render_catalog(wiki)
    lines = cat.splitlines()
    assert lines[0].startswith("<!-- catalog:begin")
    assert lines[-1].startswith("<!-- catalog:end")
    # Section order: Top level, Entities, Concepts, then unknown folders.
    headings = [l for l in lines if l.startswith("## ")]
    assert headings == ["## Top level", "## Entities", "## Concepts", "## Custom"]
    # Root pages bare, foldered pages folder-qualified; alphabetical within section.
    assert "- [[overview]] — Start here." in cat
    body = cat[cat.index("## Entities"):]
    assert body.index("- [[entities/alpha]] — First entity.") < body.index(
        "- [[entities/beta]] — Second entity.")
    assert "- [[custom/thing]] — Custom folder page." in cat
    # index.md / log.md never listed.
    assert "[[index]]" not in cat and "[[log]]" not in cat


def test_render_catalog_missing_description_placeholder(tmp_path):
    wiki = _wiki(tmp_path, {"entities/a.md": _page(desc=None)})
    cat = build_index.render_catalog(wiki)
    assert "- [[entities/a]] — *(no description)*" in cat


def test_render_catalog_quoted_description_unescaped(tmp_path):
    desc = '"Says: \\"hi\\" — and `code`"'
    wiki = _wiki(tmp_path, {"entities/a.md": _page(desc)})
    cat = build_index.render_catalog(wiki)
    assert '- [[entities/a]] — Says: "hi" — and `code`' in cat


def test_apply_replaces_marker_region_and_preserves_prose(tmp_path):
    wiki = _wiki(tmp_path, {"entities/a.md": _page("New desc.")})
    index_text = textwrap.dedent("""\
        ---
        okf_version: "0.1"
        ---

        # P Wiki — Index

        Hand-written intro. Kept verbatim.

        <!-- catalog:begin — old -->
        ## Entities
        - [[entities/a]] — Stale desc.
        <!-- catalog:end -->

        Trailing prose survives too.
        """)
    out = build_index.apply(index_text, build_index.render_catalog(wiki))
    assert "Hand-written intro. Kept verbatim." in out
    assert "Trailing prose survives too." in out
    assert 'okf_version: "0.1"' in out
    assert "- [[entities/a]] — New desc." in out
    assert "Stale desc." not in out
    # Idempotent: applying the same catalog again changes nothing.
    assert build_index.apply(out, build_index.render_catalog(wiki)) == out


def test_apply_first_run_wraps_from_first_recognized_heading(tmp_path):
    """No markers yet: everything from the first category heading to EOF is the
    catalog region; prose above it (incl. bullets) is preserved untouched."""
    wiki = _wiki(tmp_path, {
        "overview.md": _page("Start here.", title="Overview"),
        "entities/a.md": _page("An entity."),
    })
    index_text = textwrap.dedent("""\
        # P Wiki — Index

        Catalog of every wiki page.

        - **Sources ingested:** 694 tickets — prose bullet, not a catalog entry.

        ## Top level
        - [[overview]] — old overview line.

        ## Entities
        - [[entities/a]] — old line.
        """)
    out = build_index.apply(index_text, build_index.render_catalog(wiki))
    assert "**Sources ingested:**" in out
    assert "old overview line." not in out and "old line." not in out
    assert "<!-- catalog:begin" in out and "- [[entities/a]] — An entity." in out
    # cid-wiki shape: root section named "Overview" is recognized too.
    index_text2 = "# X\n\nIntro.\n\n## Overview\n- [[overview]] — stale.\n"
    out2 = build_index.apply(index_text2, build_index.render_catalog(wiki))
    assert "stale." not in out2 and "Intro." in out2


def test_cli_check_and_write(tmp_path, monkeypatch):
    import subprocess, sys, os
    repo = tmp_path
    (repo / "wiki.config.yaml").write_text(textwrap.dedent("""
        project: {key: P, name: "P", config_dir: ./cfg}
        jira: {base_url: http://x, jql: "project = P"}
    """), encoding="utf-8")
    _wiki(repo, {
        "entities/a.md": _page("An entity."),
        "index.md": "# P Wiki — Index\n\nIntro.\n\n## Entities\n- [[entities/a]] — stale.\n",
        "log.md": "# Log\n",
    })
    script = Path(build_index.__file__)
    env = dict(os.environ, WIKI_CONFIG=str(repo / "wiki.config.yaml"))

    def run(*args):
        return subprocess.run([sys.executable, str(script), *args],
                              cwd=repo, env=env, capture_output=True, text=True)

    r = run("--check")
    assert r.returncode == 1 and "drift" in (r.stdout + r.stderr).lower()
    r = run("--write")
    assert r.returncode == 0
    first = (repo / "wiki/index.md").read_text(encoding="utf-8")
    assert "- [[entities/a]] — An entity." in first and "Intro." in first
    r = run("--check")
    assert r.returncode == 0
    r = run("--write")   # second write: no changes (idempotent)
    assert r.returncode == 0
    assert (repo / "wiki/index.md").read_text(encoding="utf-8") == first
