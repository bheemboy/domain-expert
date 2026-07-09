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
