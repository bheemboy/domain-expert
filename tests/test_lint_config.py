import textwrap

import config


def _cfg(tmp_path, monkeypatch, lint_block):
    cfg = tmp_path / "wiki.config.yaml"
    cfg.write_text(textwrap.dedent(f"""
        project: {{key: TESTPROJ, name: T, config_dir: {tmp_path}}}
        jira: {{base_url: https://e.example, jql: 'project = TESTPROJ'}}
        sources: []
        {lint_block}
    """))
    monkeypatch.setenv("WIKI_CONFIG", str(cfg))


def test_lint_config_missing_is_empty(tmp_path, monkeypatch):
    _cfg(tmp_path, monkeypatch, lint_block="")
    assert config.lint_config() == {}


def test_lint_config_returns_lists(tmp_path, monkeypatch):
    _cfg(tmp_path, monkeypatch, lint_block=(
        "lint:\n"
        "          brand_nouns: [FOO, BAR]\n"
        "          era_terms: ['FOO 1\\.0']\n"
    ))
    lc = config.lint_config()
    assert lc["brand_nouns"] == ["FOO", "BAR"]
    assert lc["era_terms"] == ["FOO 1\\.0"]
