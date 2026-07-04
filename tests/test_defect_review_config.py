import textwrap

import pytest

import config


def _write(tmp_path, monkeypatch, block: str = ""):
    cfg = tmp_path / "wiki.config.yaml"
    cfg.write_text(textwrap.dedent(f"""
        project:
          key: TESTPROJ
          name: "Test Project"
          config_dir: {tmp_path}/config
        jira:
          base_url: https://example.atlassian.net
          jql: |
            project = TESTPROJ AND status = Done
    """) + textwrap.dedent(block))
    monkeypatch.setenv("WIKI_CONFIG", str(cfg))
    return cfg


def test_defaults_when_block_absent(tmp_path, monkeypatch):
    _write(tmp_path, monkeypatch)
    cfg = config.defect_review_config()
    assert cfg["enabled"] is False
    assert cfg["mode"] == "draft"
    assert cfg["notify_user"] == ""
    assert cfg["candidate_jql"] == ""
    assert cfg["max_question_rounds"] == 3
    assert cfg["marker"] == "🤖 Automated defect review —"
    assert cfg["also_notify"] is False
    assert cfg["qmd_collection_prefix"] == ""


def test_overrides_merge_over_defaults(tmp_path, monkeypatch):
    _write(tmp_path, monkeypatch, """
        defect_review:
          enabled: true
          mode: post
          notify_user: rehman@hotmail.com
          candidate_jql: 'issuetype = Bug AND status in ("New", "Open")'
          max_question_rounds: 2
          qmd_collection_prefix: cid
    """)
    cfg = config.defect_review_config()
    assert cfg["enabled"] is True
    assert cfg["mode"] == "post"
    assert cfg["notify_user"] == "rehman@hotmail.com"
    assert cfg["candidate_jql"] == 'issuetype = Bug AND status in ("New", "Open")'
    assert cfg["max_question_rounds"] == 2
    assert cfg["qmd_collection_prefix"] == "cid"
    # untouched keys keep defaults
    assert cfg["marker"] == "🤖 Automated defect review —"
    assert cfg["also_notify"] is False


def test_invalid_mode_raises(tmp_path, monkeypatch):
    _write(tmp_path, monkeypatch, """
        defect_review:
          mode: yolo
    """)
    with pytest.raises(ValueError):
        config.defect_review_config()
