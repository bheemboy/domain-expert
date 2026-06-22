import textwrap
from pathlib import Path

import lint_scope


def test_changed_unions_synth_pages_after_last_lint():
    log = "\n".join([
        "## [2026-06-01] synth | A-1 | pages: alpha, beta",
        "## [2026-06-02] lint | manual | scope: 2 pages | clean",
        "## [2026-06-03] synth | A-2 | pages: gamma, beta",
        "## [2026-06-03] synth | A-3 | pages: delta",
    ])
    assert lint_scope.changed_since_last_lint(log) == ["gamma", "beta", "delta"]


def test_changed_ignores_query_lines_and_pre_watermark():
    log = "\n".join([
        "## [2026-06-03] synth | A-2 | pages: gamma",
        '## [2026-06-03] query | "q?" | pages read: alpha, beta',
        "## [2026-06-04] lint --full | manual | scope: 59 pages | clean",
        "## [2026-06-05] synth | A-9 | pages: omega | findings: stuff",
    ])
    assert lint_scope.changed_since_last_lint(log) == ["omega"]


def test_changed_whole_log_when_no_lint_yet():
    log = "## [2026-06-01] synth | A-1 | pages: alpha, beta"
    assert lint_scope.changed_since_last_lint(log) == ["alpha", "beta"]


def test_changed_synth_prefixed_line_does_not_reset_watermark():
    log = "\n".join([
        "## [2026-06-02] lint | manual | clean",
        "## [2026-06-03] synth | A-2 | pages: gamma",
        "## [2026-06-03] synth-lint | auto | pages: gamma",
        "## [2026-06-04] synth | A-3 | pages: delta",
    ])
    assert lint_scope.changed_since_last_lint(log) == ["gamma", "delta"]


def _wiki(tmp_path, files):
    wiki = tmp_path / "wiki"
    for rel, text in files.items():
        p = wiki / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(text, encoding="utf-8")
    return wiki


def _wiki_repo(tmp_path, files, log=""):
    """Build a wiki repo (config + wiki/) and point $WIKI_CONFIG at it."""
    (tmp_path / "wiki.config.yaml").write_text(textwrap.dedent("""
        project: {key: CDS2ASV, name: "T", config_dir: ./config}
        jira: {base_url: http://x, jql: "project = CDS2ASV"}
        sources: []
        lint: {flaggable_nouns: [], brand_nouns: [], era_terms: []}
    """), encoding="utf-8")
    wiki = tmp_path / "wiki"
    wiki.mkdir()
    (wiki / "log.md").write_text(log, encoding="utf-8")
    for rel, text in files.items():
        p = wiki / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(text, encoding="utf-8")
    return tmp_path


def test_neighbors_include_inbound_and_outbound(tmp_path):
    wiki = _wiki(tmp_path, {
        "concepts/alpha.md": "links to [[beta]]",   # alpha -> beta (outbound)
        "concepts/beta.md": "plain",
        "concepts/gamma.md": "see [[alpha]]",        # gamma -> alpha (inbound)
        "concepts/delta.md": "unrelated",
    })
    assert lint_scope.one_hop_neighbors(["alpha"], wiki) == ["alpha", "beta", "gamma"]


def test_neighbors_empty_when_no_changes(tmp_path):
    wiki = _wiki(tmp_path, {"concepts/alpha.md": "[[beta]]", "concepts/beta.md": "x"})
    assert lint_scope.one_hop_neighbors([], wiki) == []


def test_neighbors_drop_broken_link_targets(tmp_path):
    wiki = _wiki(tmp_path, {"concepts/alpha.md": "[[nonexistent]]"})
    assert lint_scope.one_hop_neighbors(["alpha"], wiki) == ["alpha"]


def test_shard_splits_oversized_folder_by_line_budget(tmp_path):
    big = ("line\n" * 100)          # 100 lines
    wiki = _wiki(tmp_path, {
        "concepts/a.md": big, "concepts/b.md": big, "concepts/c.md": big,
        "entities/x.md": "small\n",
        "index.md": "entry", "log.md": "entry", "overview.md": "entry",
    })
    shards = lint_scope.shard_pages(wiki, budget_lines=150)
    assert ["a"] in shards and ["b"] in shards and ["c"] in shards   # each alone
    assert ["x"] in shards                                            # small folder, own shard
    flat = [slug for s in shards for slug in s]
    assert "index" not in flat and "log" not in flat and "overview" not in flat


def test_shard_packs_small_pages_together(tmp_path):
    wiki = _wiki(tmp_path, {
        "concepts/a.md": "x\n", "concepts/b.md": "y\n", "concepts/c.md": "z\n",
    })
    shards = lint_scope.shard_pages(wiki, budget_lines=150)
    assert shards == [["a", "b", "c"]]                               # all fit in one shard


def test_main_delta_prints_neighbor_expanded_set(tmp_path, monkeypatch, capsys):
    repo = _wiki_repo(
        tmp_path,
        {"concepts/alpha.md": "[[beta]]", "concepts/beta.md": "x", "concepts/gamma.md": "[[alpha]]"},
        log="## [2026-06-01] lint | manual | clean\n## [2026-06-02] synth | A | pages: alpha\n",
    )
    monkeypatch.setenv("WIKI_CONFIG", str(repo / "wiki.config.yaml"))
    assert lint_scope.main(["delta"]) == 0
    out = capsys.readouterr().out.split()
    assert out == ["alpha", "beta", "gamma"]


def test_main_full_prints_one_shard_per_line(tmp_path, monkeypatch, capsys):
    repo = _wiki_repo(tmp_path, {"concepts/a.md": "x\n", "entities/b.md": "y\n"})
    monkeypatch.setenv("WIKI_CONFIG", str(repo / "wiki.config.yaml"))
    assert lint_scope.main(["full"]) == 0
    lines = capsys.readouterr().out.splitlines()
    assert lines == ["a", "b"]            # one page per folder -> one shard per folder
