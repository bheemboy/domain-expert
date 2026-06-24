import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SKILLS = ROOT / "skills"
REFS = SKILLS / "wiki-story" / "references"
SHARED_REF_FILES = [
    "story-format.md",
    "story-personas.md",
    "story-sizing.md",
    "story-examples.md",
    "wiki-grounding.md",
]


def _frontmatter_name(skill_md: Path) -> str:
    text = skill_md.read_text(encoding="utf-8")
    assert text.startswith("---"), f"{skill_md} missing frontmatter"
    fm = text.split("---", 2)[1]
    m = re.search(r"^name:\s*(.+)$", fm, re.MULTILINE)
    assert m, f"{skill_md} frontmatter missing name:"
    return m.group(1).strip()


def test_shared_references_exist():
    for fname in SHARED_REF_FILES:
        assert (REFS / fname).is_file(), f"missing shared reference {fname}"


def test_wiki_grounding_has_qmd_gate():
    text = (REFS / "wiki-grounding.md").read_text(encoding="utf-8")
    assert "qmd status" in text, "wiki-grounding.md must document the cheap `qmd status` gate"
    assert "grep" in text.lower(), "wiki-grounding.md must document the grep fallback"


def test_personas_default_roster():
    text = (REFS / "story-personas.md").read_text(encoding="utf-8").lower()
    for persona in ("user", "admin", "support engineer"):
        assert persona in text, f"default roster missing {persona!r}"


def test_wiki_story_skill_frontmatter():
    assert _frontmatter_name(SKILLS / "wiki-story" / "SKILL.md") == "wiki-story"


def test_wiki_epic_skill_frontmatter():
    assert _frontmatter_name(SKILLS / "wiki-epic" / "SKILL.md") == "wiki-epic"


def test_wiki_story_documents_story_boundary():
    text = (SKILLS / "wiki-story" / "SKILL.md").read_text(encoding="utf-8")
    assert "## Story:" in text, "wiki-story SKILL.md must document the `## Story:` boundary"
    assert "## Grounding" in text, "wiki-story SKILL.md must document the `## Grounding` footer"


def test_wiki_epic_references_resolve():
    base = SKILLS / "wiki-epic"
    text = (base / "SKILL.md").read_text(encoding="utf-8")
    rels = re.findall(r"\.\./wiki-story/references/[\w./-]+\.md", text)
    assert rels, "wiki-epic SKILL.md must reference the shared references dir"
    for rel in rels:
        target = (base / rel).resolve()
        assert target.is_file(), f"unresolved reference link: {rel}"


def test_existing_skills_qmd_gate():
    synth = (SKILLS / "wiki-ingest" / "synth-prompt.md").read_text(encoding="utf-8")
    assert "qmd status" in synth, "synth-prompt.md must use the cheap qmd status gate"
    assert "You may use `qmd query`/`qmd search`" not in synth, (
        "old soft 'You may use qmd' wording must be replaced"
    )
    lint = (SKILLS / "wiki-lint" / "SKILL.md").read_text(encoding="utf-8")
    assert "qmd status" in lint, "wiki-lint SKILL.md lookup must use the cheap qmd status gate"


STORY_BOUNDARY = re.compile(r"^## Story:\s+.+$", re.MULTILINE)


def test_sample_epic_boundaries_parse():
    sample = ROOT / "tests" / "fixtures" / "sample-epic.md"
    text = sample.read_text(encoding="utf-8")
    titles = STORY_BOUNDARY.findall(text)
    assert len(titles) >= 2, "sample epic must contain at least two `## Story:` boundaries"
