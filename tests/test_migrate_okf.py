import textwrap
from pathlib import Path

import yaml

import build_index
import migrate_okf


def _repo(tmp_path, files):
    (tmp_path / "wiki.config.yaml").write_text(textwrap.dedent("""
        project: {key: P, name: "P", config_dir: ./cfg}
        jira: {base_url: http://x, jql: "project = P"}
    """), encoding="utf-8")
    for rel, text in files.items():
        p = tmp_path / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(text, encoding="utf-8")
    return tmp_path


_LEGACY_PAGE = textwrap.dedent("""\
    ---
    type: entity
    status: current
    sources: [P-1]
    code_refs: []
    updated: 2026-06-21
    ---

    # AIC (Analytical Instrument Controller)

    An **AIC** is a host machine [P-1, 2017-11] (ticket-only).

    ## Relationships
    - [[cid]]
    """)

_LEGACY_INDEX = textwrap.dedent("""\
    # P Wiki — Index

    Catalog of every wiki page.

    - **Sources ingested:** prose bullet above the catalog, preserved.

    ## Entities
    - [[entities/aic|AIC]] — The instrument controller: hosts the "CDS" VM.
    - [[entities/cid]] – Hyphenated – uses an en dash separator.

    ## Overview
    - [[overview]] — Top-level synthesis.
    """)

_LEGACY_LOG = textwrap.dedent("""\
    # P Wiki — Log

    Append-only, chronological record. One line per event.

    ## [2026-06-01] init | scaffold
    ## [2026-06-18] synth  | P-1 (defect, 2021-08) | pages: entities/aic, glossary
    ## [2026-06-18] ingest | P-2 | pages: entities/cid
    ## [2026-06-19] lint | auto | scope: 3 pages | CLEAN
    """)


def _full_repo(tmp_path):
    return _repo(tmp_path, {
        "wiki/index.md": _LEGACY_INDEX,
        "wiki/log.md": _LEGACY_LOG,
        "wiki/overview.md": "---\ntype: concept\nstatus: current\nupdated: 2026-06-01\n---\n\n# Overview\n\nP synthesized.\n",
        "wiki/entities/aic.md": _LEGACY_PAGE,
        "wiki/entities/cid.md": "---\ntype: entity\nstatus: current\nupdated: 2026-06-01\n---\n\n# CID\n\nA device.\n",
    })


def _fm(path):
    text = path.read_text(encoding="utf-8")
    return yaml.safe_load(text.split("---\n")[1])


def test_description_map_link_variants():
    m = migrate_okf.index_descriptions(_LEGACY_INDEX)
    assert m["aic"] == 'The instrument controller: hosts the "CDS" VM.'
    assert m["cid"] == "Hyphenated – uses an en dash separator."
    assert m["overview"] == "Top-level synthesis."
    # The prose bullet (no [[wikilink]]) is not a catalog entry.
    assert "Sources ingested" not in str(m)


def test_backfill_title_and_description_from_index(tmp_path):
    repo = _full_repo(tmp_path)
    migrate_okf.migrate(repo, write=True)
    fm = _fm(repo / "wiki/entities/aic.md")
    assert fm["title"] == "AIC (Analytical Instrument Controller)"
    assert fm["description"] == 'The instrument controller: hosts the "CDS" VM.'
    # existing keys untouched
    assert fm["sources"] == ["P-1"] and fm["status"] == "current"


def test_description_fallback_first_prose_line(tmp_path):
    repo = _full_repo(tmp_path)
    migrate_okf.migrate(repo, write=True)
    fm = _fm(repo / "wiki/overview.md")   # overview IS in the index map here
    assert fm["description"] == "Top-level synthesis."
    # cid page is in the index; drop it from the index to exercise the fallback
    (tmp_path / "r2").mkdir()
    repo2 = _full_repo(tmp_path / "r2")
    idx = repo2 / "wiki/index.md"
    idx.write_text(idx.read_text(encoding="utf-8").replace(
        "- [[entities/cid]] – Hyphenated – uses an en dash separator.\n", ""),
        encoding="utf-8")
    migrate_okf.migrate(repo2, write=True)
    assert _fm(repo2 / "wiki/entities/cid.md")["description"] == "A device."


def test_needs_description_reported(tmp_path):
    repo = _repo(tmp_path, {
        "wiki/index.md": "# X\n\n## Entities\n",
        "wiki/log.md": "# L\n",
        "wiki/entities/bare.md": "---\ntype: entity\nstatus: current\nupdated: 2026-01-01\n---\n\n# Bare\n",
    })
    report = migrate_okf.migrate(repo, write=True)
    assert "wiki/entities/bare.md" in report["needs_description"]
    fm = _fm(repo / "wiki/entities/bare.md")
    assert fm["title"] == "Bare" and "description" not in fm


def test_log_rewrite_date_grouped_newest_first(tmp_path):
    repo = _full_repo(tmp_path)
    migrate_okf.migrate(repo, write=True)
    log = (repo / "wiki/log.md").read_text(encoding="utf-8")
    assert "## [" not in log
    # Newest date first; within a date the later-appended event comes first.
    i19 = log.index("## 2026-06-19")
    i18 = log.index("## 2026-06-18")
    i01 = log.index("## 2026-06-01")
    assert i19 < i18 < i01
    assert log.index("- ingest | P-2") < log.index("- synth  | P-1")
    assert "- lint | auto | scope: 3 pages | CLEAN" in log
    assert "- init | scaffold" in log


def test_log_unparsed_lines_kept_and_reported(tmp_path):
    repo = _full_repo(tmp_path)
    log = repo / "wiki/log.md"
    log.write_text(log.read_text(encoding="utf-8")
                   + "stray continuation line\n", encoding="utf-8")
    report = migrate_okf.migrate(repo, write=True)
    assert "stray continuation line" in log.read_text(encoding="utf-8")
    assert any("stray continuation" in u for u in report["unparsed"])


def test_index_gets_okf_version_and_generated_catalog(tmp_path):
    repo = _full_repo(tmp_path)
    migrate_okf.migrate(repo, write=True)
    text = (repo / "wiki/index.md").read_text(encoding="utf-8")
    assert text.startswith("---\n")
    fm = yaml.safe_load(text.split("---\n")[1])
    assert fm["okf_version"] == "0.1"
    assert "<!-- catalog:begin" in text
    assert "- **Sources ingested:** prose bullet above the catalog, preserved." in text
    # Catalog regenerated from the (just-backfilled) page descriptions.
    assert '- [[entities/aic]] — The instrument controller: hosts the "CDS" VM.' in text


def test_dry_run_changes_nothing(tmp_path):
    repo = _full_repo(tmp_path)
    before = {p: p.read_text(encoding="utf-8") for p in repo.rglob("*.md")}
    report = migrate_okf.migrate(repo, write=False)
    assert {p: p.read_text(encoding="utf-8") for p in repo.rglob("*.md")} == before
    assert report["pages_described"] and report["log_migrated"]


def test_idempotent_second_run_no_changes(tmp_path):
    repo = _full_repo(tmp_path)
    migrate_okf.migrate(repo, write=True)
    after_first = {p: p.read_text(encoding="utf-8") for p in repo.rglob("*.md")}
    report = migrate_okf.migrate(repo, write=True)
    assert {p: p.read_text(encoding="utf-8") for p in repo.rglob("*.md")} == after_first
    assert not report["pages_described"] and not report["log_migrated"]


def test_yaml_quoting_round_trip(tmp_path):
    desc = 'Says: "hi" — uses `code`, [P-1, 2017-11] (ticket-only) & #hash'
    repo = _repo(tmp_path, {
        "wiki/index.md": f"# X\n\n## Entities\n- [[entities/a]] — {desc}\n",
        "wiki/log.md": "# L\n",
        "wiki/entities/a.md": "---\ntype: entity\nstatus: current\nupdated: 2026-01-01\n---\n\n# A\n\nBody.\n",
    })
    migrate_okf.migrate(repo, write=True)
    assert _fm(repo / "wiki/entities/a.md")["description"] == desc
    assert build_index.page_description(
        (repo / "wiki/entities/a.md").read_text(encoding="utf-8")) == desc
