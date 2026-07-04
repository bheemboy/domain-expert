import comment_contract as cc

MARKER = "🤖 Automated defect review —"


def test_compliant_ask_comment_passes():
    text = (f"{MARKER}\n\nNeed two details before this can be routed.\n\n"
            "1. Which version: 2.7 or 2.8?\n"
            "2. Attach the acquisition log from `C:\\logs`.")
    assert cc.check(text, "ask") == []


def test_too_many_asks_flagged():
    asks = "\n".join(f"{n}. Question {n}?" for n in range(1, 5))
    violations = cc.check(f"{MARKER}\n\nStatus line.\n\n{asks}", "ask")
    assert any("asks" in v for v in violations)


def test_ask_word_budget_enforced_with_grace():
    body = "word " * 200  # 200 words >> 165 ceiling
    violations = cc.check(f"{MARKER}\n\n1. {body}?", "ask")
    assert any("word" in v.lower() for v in violations)


def test_procedure_raises_budget_and_needs_report_back():
    steps_ok = (f"{MARKER}\n\nOne check to run.\n\n"
                "1. Run the gradient check:\n"
                "   1. Open **Method Editor → Gradient Table**\n"
                "   2. Set flow to 0\n"
                "   3. Report whether an error appears; if so attach the log")
    assert cc.check(steps_ok, "ask") == []
    no_report = (f"{MARKER}\n\nOne check to run.\n\n"
                 "1. Run the gradient check:\n"
                 "   1. Open **Method Editor**\n"
                 "   2. Set flow to 0")
    assert any("report-back" in v for v in cc.check(no_report, "ask"))


def test_too_many_procedure_steps_flagged():
    steps = "\n".join(f"   {n}. Step {n}" for n in range(1, 8))
    text = f"{MARKER}\n\nStatus.\n\n1. Do the procedure:\n{steps}\n   8. Report the result"
    assert any("sub-steps" in v for v in cc.check(text, "ask"))


def test_two_procedures_flagged():
    text = (f"{MARKER}\n\nStatus.\n\n"
            "1. First procedure:\n   1. a\n   2. Report a\n"
            "2. Second procedure:\n   1. b\n   2. Report b")
    assert any("one procedure" in v for v in cc.check(text, "ask"))


def test_assessment_budget():
    ok = f"{MARKER}\n\n## Verdict\nIn scope — high confidence.\n\n" + ("word " * 300)
    assert cc.check(ok, "assessment") == []
    over = f"{MARKER}\n\n" + ("word " * 500)
    assert any("word" in v.lower() for v in cc.check(over, "assessment"))


def test_missing_marker_flagged_and_fixed():
    text = "1. Which version?"
    assert any("marker" in v for v in cc.check(text, "ask"))
    fixed = cc.ensure_marker(text, MARKER)
    assert fixed.startswith(MARKER)
    assert cc.ensure_marker(fixed, MARKER) == fixed  # idempotent
