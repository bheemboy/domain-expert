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
