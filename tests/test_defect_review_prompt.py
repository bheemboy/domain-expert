"""Content-drift locks for the defect-review prompt contract. These do not
test prose quality — only that load-bearing rules survive future edits."""
from pathlib import Path

PROMPT = Path(__file__).parent.parent / "prompts" / "defect-review-prompt.md"
SKILL = (Path(__file__).parent.parent / "skills" / "wiki-defect-review"
         / "SKILL.md")


def test_prompt_names_the_two_audience_headers():
    text = PROMPT.read_text(encoding="utf-8")
    assert "Hello " in text
    assert "**Notes for defect reviewers**" in text
    assert "**Notes for developer**" not in text


def test_prompt_limits_duplicates_to_one_sentence():
    text = " ".join(PROMPT.read_text(encoding="utf-8").split())
    assert "Likely related:" in text
    assert "one sentence" in text
    assert 'never write "no duplicates found"' in text.lower()
    assert "considered and rejected" in text
    assert "in the ANALYSIS" in text


def test_prompt_assessment_is_disposition_only():
    text = " ".join(PROMPT.read_text(encoding="utf-8").split())
    assert "enough to decide a disposition" in text
    assert "how to fix" in text
    assert "how to test" in text


def test_prompt_puts_disposition_last_after_split_sections():
    text = " ".join(PROMPT.read_text(encoding="utf-8").split())
    assert "**Frequency and impact**" not in text
    assert "**Frequency**" in text
    assert "**Impact**" in text
    assert "**Potential workaround**" in text
    assert text.index("**Caveats**") < text.index("**Proposed disposition**")


def test_prompt_separates_reproducibility_from_site_frequency():
    text = " ".join(PROMPT.read_text(encoding="utf-8").split()).lower()
    assert "technical reproducibility" in text
    assert "operational frequency" in text
    assert "acceptable to the customer" in text
    assert "never blur" in text


def test_prompt_makes_frequency_and_acceptability_ask_material():
    text = " ".join(PROMPT.read_text(encoding="utf-8").split())
    assert "count as consequential" in text


def test_prompt_says_each_fact_appears_once():
    text = " ".join(PROMPT.read_text(encoding="utf-8").split())
    assert "appears once" in text


def test_prompt_exempts_asks_from_no_commands_rule():
    # 2026-07-13 review: "never as commands" contradicted the mandatory
    # closed-form imperative asks; the exemption must survive edits.
    text = " ".join(PROMPT.read_text(encoding="utf-8").split())
    assert "required form, not a tone violation" in text


def test_prompt_allows_addressee_and_attribution_mentions():
    text = " ".join(PROMPT.read_text(encoding="utf-8").split())
    assert "no other mentions of people" in text
    assert "no mentions of other people" not in text


def test_prompt_tiebreaker_ask_before_assessing_unknown():
    # Unstated operational frequency / workaround acceptability: ask while
    # rounds remain; unknown-in-assessment is the cap-forced fallback only.
    text = " ".join(PROMPT.read_text(encoding="utf-8").split())
    assert "rather than assessing around them" in text
    assert "cap-forced fallback" in text


def test_prompt_disposition_example_is_bold():
    # The checker regex requires the line to start with '**Proposed
    # disposition'; the worked example must model that form.
    text = " ".join(PROMPT.read_text(encoding="utf-8").split())
    assert '"**Proposed disposition:** close as a duplicate' in text


def test_critic_told_about_code_composed_header():
    text = " ".join(CRITIC.read_text(encoding="utf-8").split())
    assert "marker line" in text
    assert "freshness" in text
    assert "never flag" in text


def test_critic_exempts_asks_from_tone_check():
    text = " ".join(CRITIC.read_text(encoding="utf-8").split())
    assert "required form" in text


def test_skill_notice_fires_only_for_assessments():
    text = " ".join(SKILL.read_text(encoding="utf-8").split())
    assert "only after a `kind: assessment` delivery" in text


def test_skill_partial_delivery_records_state():
    # Post-mode multi-write: once the primary comment lands, state must be
    # recorded even if the notice/email fails, else bot-spoke-last hides
    # the ticket with no retry and state drifts from the ticket.
    text = " ".join(SKILL.read_text(encoding="utf-8").split())
    assert "Primary delivery" in text
    assert "still record state" in text


def test_prompt_analysis_focuses_on_issue_and_root_cause():
    text = " ".join(PROMPT.read_text(encoding="utf-8").split())
    assert "focused on the issue itself" in text
    assert "likely root cause" in text
    assert "one line per rejected candidate" in text


def test_prompt_requires_plain_english():
    text = PROMPT.read_text(encoding="utf-8").lower()
    assert "idiom" in text
    assert "plain" in text


def test_prompt_derives_greeting_from_reporter():
    text = PROMPT.read_text(encoding="utf-8")
    assert "Reporter" in text
    assert "Liliana" in text  # the worked example


def test_prompt_allows_asks_to_any_thread_participant():
    text = PROMPT.read_text(encoding="utf-8")
    assert "whoever can best answer" in text
    assert "any thread participant" in text
    assert "never to assign work" in text


def test_prompt_requires_consequential_asks():
    text = PROMPT.read_text(encoding="utf-8")
    assert "could change the disposition" in text
    assert "never nitpick" in text


def test_prompt_scopes_round_cap_to_pre_assessment():
    text = PROMPT.read_text(encoding="utf-8")
    assert "prior_disposition_code" in text
    assert "cap no longer applies" in text


def test_prompt_says_skill_owns_the_header():
    text = PROMPT.read_text(encoding="utf-8")
    assert "skill composes the header" in text


def test_prompt_revision_replaces_prior_assessment():
    text = PROMPT.read_text(encoding="utf-8")
    assert "replaces" in text
    assert "not a delta" in text


def test_prompt_state_carries_disposition_code_enum():
    text = PROMPT.read_text(encoding="utf-8")
    assert "disposition_code" in text
    for code in ("accept-for-fix", "duplicate", "out-of-scope",
                 "not-a-defect", "as-designed", "needs-info"):
        assert code in text


CRITIC = Path(__file__).parent.parent / "prompts" / "defect-review-critic-prompt.md"


def test_critic_prompt_exists_with_verdict_contract():
    text = CRITIC.read_text(encoding="utf-8")
    assert "VERDICT: pass" in text
    assert "VERDICT: revise" in text


def test_critic_prompt_judges_value_not_justification():
    text = CRITIC.read_text(encoding="utf-8").lower()
    assert "not a duplicate" in text      # the named anti-pattern
    assert "differently" in text          # the value test
    assert "idiom" in text                # plain-English re-check


def test_critic_prompt_knows_the_ask_contract():
    text = CRITIC.read_text(encoding="utf-8")
    assert "at most 3" in text
    assert "counts as ONE ask" in text
    assert "report-back" in text


def test_critic_prompt_has_pass_calibration():
    text = CRITIC.read_text(encoding="utf-8")
    assert "cosmetic" in text
    assert "does not need to be perfect" in text


def test_prompt_requires_polite_nonconfrontational_tone():
    text = PROMPT.read_text(encoding="utf-8")
    assert "non-confrontational" in text
    assert "Thank the reporter" in text
    assert "Proposed disposition" in text
    assert "Never state a disposition" in text


def test_critic_checks_tone():
    text = CRITIC.read_text(encoding="utf-8")
    assert "**Tone.**" in text
    assert "non-confrontational" in text


def test_critic_knows_assessment_is_disposition_only():
    text = CRITIC.read_text(encoding="utf-8")
    assert "**Notes for developer**" not in text
    assert "how to fix" in text
    assert "Likely related:" in text


def test_critic_checks_site_frequency_and_workaround_acceptability():
    text = " ".join(CRITIC.read_text(encoding="utf-8").split())
    assert "reproducibility" in text
    assert "acceptable" in text
