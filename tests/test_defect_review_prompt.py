"""Content-drift locks for the defect-review prompt contract. These do not
test prose quality — only that load-bearing rules survive future edits."""
from pathlib import Path

PROMPT = Path(__file__).parent.parent / "prompts" / "defect-review-prompt.md"


def test_prompt_names_the_three_audience_headers():
    text = PROMPT.read_text(encoding="utf-8")
    assert "Hello " in text
    assert "**Notes for defect reviewers**" in text
    assert "**Notes for developer**" in text


def test_prompt_gates_duplicates_on_relevance():
    text = PROMPT.read_text(encoding="utf-8")
    assert "changes the outcome" in text
    assert 'Never write "no duplicates found"' in text
    assert "considered and rejected in the ANALYSIS" in text


def test_prompt_requires_plain_english():
    text = PROMPT.read_text(encoding="utf-8").lower()
    assert "idiom" in text
    assert "plain" in text


def test_prompt_derives_greeting_from_reporter():
    text = PROMPT.read_text(encoding="utf-8")
    assert "Reporter" in text
    assert "Liliana" in text  # the worked example


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
