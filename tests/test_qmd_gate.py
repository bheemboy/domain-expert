"""The qmd-first gate is single-sourced in prompts/qmd-first-gate.md; the
consumers reference it instead of restating the 12-line block (drift guard)."""
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
GATE = REPO / "prompts" / "qmd-first-gate.md"

CONSUMERS = (
    REPO / "skills" / "wiki-doc-author" / "SKILL.md",
    REPO / "skills" / "wiki-doc-review" / "SKILL.md",
    REPO / "skills" / "wiki-story" / "references" / "wiki-grounding.md",
)


def test_canonical_gate_exists_and_states_the_rule():
    text = GATE.read_text(encoding="utf-8")
    assert "qmd status" in text and "genuinely absent" in text
    assert "Do NOT default to grep" in text


def test_consumers_reference_the_canonical_gate():
    for p in CONSUMERS:
        text = p.read_text(encoding="utf-8")
        assert "qmd-first-gate.md" in text, f"{p} must reference the canonical gate"
        assert "Cheap presence gate" not in text, (
            f"{p} restates the gate block instead of referencing it")
