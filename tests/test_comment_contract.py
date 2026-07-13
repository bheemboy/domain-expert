import comment_contract as cc

MARKER = "🤖 Automated defect review"
OLD_MARKER = "🤖 Automated defect review —"
REVIEWERS = "**Notes for defect reviewers**"
DEVELOPER = "**Notes for developer**"


def _ask(body, greeting="Hello Martin,"):
    return f"{MARKER}\n---\n\n{greeting}\n\n{body}"


def _assessment(reviewers_body, developer_body=None):
    text = f"{MARKER}\n---\n\n{REVIEWERS}\n\n{reviewers_body}"
    if developer_body is not None:
        text += f"\n\n---\n\n{DEVELOPER}\n\n{developer_body}"
    return text


# ── existing rules, re-fixtured ─────────────────────────────────────────

def test_compliant_ask_comment_passes():
    text = _ask("Need two details before this can be routed.\n\n"
                "1. Which version: 2.7 or 2.8?\n"
                "2. Attach the acquisition log from `C:\\logs`.")
    assert cc.check(text, "ask") == []


def test_too_many_asks_flagged():
    asks = "\n".join(f"{n}. Question {n}?" for n in range(1, 5))
    violations = cc.check(_ask(f"Status line.\n\n{asks}"), "ask")
    assert any(v.startswith("asks") for v in violations)


def test_ask_word_budget_enforced_with_grace():
    body = "word " * 200
    violations = cc.check(_ask(f"1. {body}?"), "ask")
    assert any("word" in v.lower() for v in violations)


def test_procedure_raises_budget_and_needs_report_back():
    steps_ok = _ask("One check to run.\n\n"
                    "1. Run the gradient check:\n"
                    "   1. Open **Method Editor → Gradient Table**\n"
                    "   2. Set flow to 0\n"
                    "   3. Report whether an error appears; if so attach the log")
    assert cc.check(steps_ok, "ask") == []
    no_report = _ask("One check to run.\n\n"
                     "1. Run the gradient check:\n"
                     "   1. Open **Method Editor**\n"
                     "   2. Set flow to 0")
    assert any("report-back" in v for v in cc.check(no_report, "ask"))


def test_too_many_procedure_steps_flagged():
    steps = "\n".join(f"   {n}. Step {n}" for n in range(1, 8))
    violations = cc.check(_ask(f"One check.\n\n1. Do this:\n{steps}\n   8. Report it"),
                          "ask")
    assert any("sub-steps" in v for v in violations)


def test_assessment_word_budget():
    body = "word " * 500
    violations = cc.check(_assessment(body), "assessment")
    assert any("word" in v.lower() for v in violations)


def test_assessment_word_budget_tightened_to_250():
    # 250-word target (275 ceiling with grace): ~300 words must now fail.
    body = "word " * 300
    violations = cc.check(_assessment(body), "assessment")
    assert any("word" in v.lower() for v in violations)


def test_word_budget_excludes_code_composed_header():
    # The marker and freshness line are code-owned; the brain's budget must
    # cover only the blocks it writes. 270 block-words fit the 275 ceiling
    # even though header + freshness push the gross count past it.
    body = ("**Issue summary:** " + "word " * 258
            + "\n\n**Proposed disposition:** accept for a fix; high confidence.")
    text = (f"{MARKER} — disposition proposal\n"
            "_Reflects the ticket as of 2026-07-13 12:00 UTC_\n---\n\n"
            f"{REVIEWERS}\n\n{body}")
    assert cc.word_count(text) > cc.ASSESS_WORDS  # gross count would fail
    assert cc.check(text, "assessment") == []


def test_compliant_assessment_passes():
    text = _assessment("**Issue summary:** Two sentences of summary.\n\n"
                       "**Proposed disposition:** accept for a fix; high confidence.")
    assert cc.check(text, "assessment") == []


def test_assessment_developer_block_flagged():
    text = _assessment("**Proposed disposition:** accept for a fix.",
                       "Check the dialog padding override.")
    violations = cc.check(text, "assessment")
    assert any("developer" in v for v in violations)


def test_assessment_without_disposition_flagged():
    text = _assessment("**Issue summary:** Two sentences of summary.")
    violations = cc.check(text, "assessment")
    assert any(v.startswith("disposition") for v in violations)


def test_assessment_disposition_not_last_flagged():
    text = _assessment("**Proposed disposition:** accept for a fix.\n\n"
                       "**Issue summary:** Two sentences of summary.")
    violations = cc.check(text, "assessment")
    assert any(v.startswith("order") for v in violations)


def test_assessment_disposition_before_workaround_flagged():
    text = _assessment("**Proposed disposition:** accept for a fix.\n\n"
                       "**Potential workaround:** close from the main window.")
    violations = cc.check(text, "assessment")
    assert any(v.startswith("order") for v in violations)


def test_missing_marker_flagged():
    violations = cc.check("Hello Martin,\n\n1. Which version?", "ask")
    assert any(v.startswith("marker") for v in violations)


# ── marker + rule line ──────────────────────────────────────────────────

def test_marker_without_rule_line_flagged():
    text = f"{MARKER}\n\nHello Martin,\n\n1. Which version?"
    assert any(v.startswith("rule") for v in cc.check(text, "ask"))


def test_old_marker_comment_passes_marker_check():
    # Prefix compatibility: a draft that still opens with the old long marker
    # starts with the new marker string, so only the rule line is flagged.
    text = f"{OLD_MARKER}\n\nHello Martin,\n\n1. Which version?"
    violations = cc.check(text, "ask")
    assert not any(v.startswith("marker") for v in violations)


def test_ensure_header_inserts_typed_header_and_rule():
    fixed = cc.ensure_header("Hello Martin,\n\n1. Which version?", MARKER, "ask")
    assert fixed.startswith(f"{MARKER} — needs more information\n---\n\n")
    assert cc.ensure_header(fixed, MARKER, "ask") == fixed  # idempotent


def test_ensure_header_replaces_freelanced_suffix():
    text = f"{MARKER} — assessment (updated)\n---\n\n{REVIEWERS}\n\nverdict"
    fixed = cc.ensure_header(text, MARKER, "assessment")
    assert fixed.split("\n")[0] == f"{MARKER} — disposition proposal"
    assert "(updated)" not in fixed


def test_ensure_header_stamps_freshness_line_for_assessment():
    text = f"{REVIEWERS}\n\nverdict"
    fixed = cc.ensure_header(text, MARKER, "assessment",
                             updated="2026-07-10T06:07:12.000+0000")
    lines = fixed.split("\n")
    assert lines[0] == f"{MARKER} — disposition proposal"
    assert lines[1] == "_Reflects the ticket as of 2026-07-10 06:07 UTC_"
    assert lines[2] == "---"


def test_ensure_header_replaces_stale_freshness_line():
    text = f"{REVIEWERS}\n\nverdict"
    first = cc.ensure_header(text, MARKER, "assessment",
                             updated="2026-07-09T10:00:00.000+0000")
    second = cc.ensure_header(first, MARKER, "assessment",
                              updated="2026-07-10T06:07:12.000+0000")
    assert "_Reflects the ticket as of 2026-07-10 06:07 UTC_" in second
    assert "2026-07-09" not in second
    assert second.count("Reflects the ticket") == 1


def test_ensure_header_converts_timestamp_to_utc():
    fixed = cc.ensure_header(f"{REVIEWERS}\n\nverdict", MARKER, "assessment",
                             updated="2026-07-10T08:07:12.000+0200")
    assert "_Reflects the ticket as of 2026-07-10 06:07 UTC_" in fixed


def test_check_accepts_typed_header_and_freshness_line():
    text = (f"{MARKER} — disposition proposal\n"
            "_Reflects the ticket as of 2026-07-10 06:07 UTC_\n---\n\n"
            f"{REVIEWERS}\n\n**Proposed disposition:** accept for a fix.")
    assert cc.check(text, "assessment") == []


def test_check_flags_header_label_mismatch():
    text = f"{MARKER} — disposition proposal\n---\n\nHello Martin,\n\n1. Which version?"
    assert any(v.startswith("header") for v in cc.check(text, "ask"))


# ── audience blocks ─────────────────────────────────────────────────────

def test_block_without_audience_header_flagged():
    text = f"{MARKER}\n---\n\nNeed two details.\n\n1. Which version?"
    assert any(v.startswith("audience") for v in cc.check(text, "ask"))


def test_ask_with_extra_block_flagged():
    text = _ask("Status.\n\n1. Which version?") + f"\n\n---\n\n{REVIEWERS}\n\nnote"
    assert any(v.startswith("kind") for v in cc.check(text, "ask"))


def test_assessment_with_hello_block_flagged():
    text = f"{MARKER}\n---\n\nHello Martin,\n\nAll good."
    assert any(v.startswith("kind") for v in cc.check(text, "assessment"))


def test_assessment_reviewers_block_must_come_first():
    text = (f"{MARKER}\n---\n\n{DEVELOPER}\n\nfix here\n\n---\n\n"
            f"{REVIEWERS}\n\nverdict")
    assert any(v.startswith("kind") for v in cc.check(text, "assessment"))


def test_plain_hello_greeting_accepted():
    # Pasted-text mode has no reporter: bare "Hello," is a valid header.
    text = f"{MARKER}\n---\n\nHello,\n\n1. Which version: 2.7 or 2.8?"
    assert cc.check(text, "ask") == []


# ── ask numbering ───────────────────────────────────────────────────────

def test_non_contiguous_ask_numbering_flagged():
    text = _ask("Status.\n\n1. First?\n\n1. Second?\n\n1. Third?")
    assert any(v.startswith("numbering") for v in cc.check(text, "ask"))


def test_contiguous_numbering_across_blank_lines_passes():
    text = _ask("Status.\n\n1. First?\n\n2. Second?\n\n3. Third?")
    assert cc.check(text, "ask") == []


# ── regression coverage ─────────────────────────────────────────────────

def test_ensure_header_inserts_missing_rule_line():
    text = f"{OLD_MARKER}\n\nHello Martin,\n\n1. Which version?"
    fixed = cc.ensure_header(text, MARKER, "ask")
    assert not any(v.startswith("rule") for v in cc.check(fixed, "ask"))
    assert cc.ensure_header(fixed, MARKER, "ask") == fixed  # idempotent


def test_empty_assessment_flagged():
    violations = cc.check(f"{MARKER}\n---\n\n   \n", "assessment")
    assert any(v.startswith("kind") for v in violations)


def test_dashes_inside_code_fence_do_not_split_blocks():
    text = (f"{MARKER}\n---\n\nHello Martin,\n\nOne thing to check.\n\n"
            "1. Run this and reply with the output:\n"
            "```\nget-info\n---\nsection two\n```")
    violations = cc.check(text, "ask")
    assert not any(v.startswith(("audience", "kind")) for v in violations)


def test_two_procedures_flagged():
    proc = ("1. First check:\n   1. Open A\n   2. Report the result\n"
            "2. Second check:\n   1. Open B\n   2. Report the result")
    violations = cc.check(_ask(f"Status.\n\n{proc}"), "ask")
    assert any(v.startswith("procedures") for v in violations)


def test_check_honors_custom_marker():
    custom = "[bot-review]"
    text = f"{custom}\n---\n\nHello Martin,\n\n1. Which version: 2.7 or 2.8?"
    assert cc.check(text, "ask", marker=custom) == []
