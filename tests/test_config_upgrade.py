import textwrap

import config_upgrade as cu

TEMPLATE = textwrap.dedent("""\
    project:
      key: {{JIRA_KEY}}

    # Optional. Where the docs live.
    # docs:
    #   location: ../my-docs

    lint:
      flaggable_nouns: []

    # Optional. Tunes synth batching.
    # synth_tuning:
    #   default_batch: 12

    # Optional. Extra ignore globs.
    # ignore:
    #   - vendor/**

    # Optional. Defect review.
    # defect_review:
    #   enabled: true
    #   mode: draft
    """)


def test_block_present_active():
    assert cu.block_present("docs:\n  location: ../x\n", "docs")


def test_block_present_commented():
    assert cu.block_present("# defect_review:\n#   enabled: true\n", "defect_review")


def test_block_absent():
    assert not cu.block_present("lint:\n  brand_nouns: []\n", "defect_review")


def test_key_in_prose_or_nested_is_not_presence():
    text = "sources: []\n# ignore rules are described in the README\n  ignore: nested\n"
    assert not cu.block_present(text, "ignore")


def test_extract_block_is_full_contiguous_comment_run():
    block = cu.extract_block(TEMPLATE, "defect_review")
    assert block.startswith("# Optional. Defect review.")
    assert "#   mode: draft" in block
    assert "{{" not in block


def test_missing_blocks_reports_only_absent(tmp_path):
    cfg = "project:\n  key: OLAC\n\n# docs:\n#   location: ../x\n\nignore:\n  - vendor/**\n"
    missing = cu.missing_blocks(cfg, TEMPLATE)
    assert [k for k, _ in missing] == ["synth_tuning", "defect_review"]


def test_append_preserves_existing_text_and_is_idempotent(tmp_path):
    cfg_path = tmp_path / "wiki.config.yaml"
    original = "project:\n  key: OLAC\n"
    cfg_path.write_text(original, encoding="utf-8")
    appended = cu.append_missing(cfg_path, TEMPLATE)
    assert [k for k, _ in appended] == ["docs", "synth_tuning", "ignore", "defect_review"]
    new_text = cfg_path.read_text(encoding="utf-8")
    assert new_text.startswith(original)  # existing bytes untouched
    assert "# defect_review:" in new_text
    # second run: nothing to do, file unchanged
    assert cu.append_missing(cfg_path, TEMPLATE) == []
    assert cfg_path.read_text(encoding="utf-8") == new_text


def test_refuses_placeholder_leakage():
    bad_template = "# Optional. Broken.\n# defect_review:\n#   key: {{JIRA_KEY}}\n"
    try:
        cu.extract_block(bad_template, "defect_review")
        assert False, "expected SystemExit"
    except SystemExit:
        pass
