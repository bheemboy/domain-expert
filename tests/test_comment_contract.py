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


def test_compliant_assessment_passes():
    text = _assessment("**Verdict:** confirmed, low. Two sentences of summary.",
                       "Check the dialog padding override.")
    assert cc.check(text, "assessment") == []


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


def test_ensure_marker_inserts_marker_and_rule():
    fixed = cc.ensure_marker("Hello Martin,\n\n1. Which version?", MARKER)
    assert fixed.startswith(f"{MARKER}\n---\n\n")
    assert cc.ensure_marker(fixed, MARKER) == fixed  # idempotent


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

def test_ensure_marker_inserts_missing_rule_line():
    text = f"{OLD_MARKER}\n\nHello Martin,\n\n1. Which version?"
    fixed = cc.ensure_marker(text, MARKER)
    assert not any(v.startswith("rule") for v in cc.check(fixed, "ask"))
    assert cc.ensure_marker(fixed, MARKER) == fixed  # idempotent


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
