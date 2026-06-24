from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
SKILL = REPO / "skills" / "wiki-doc-review" / "SKILL.md"


def test_skill_frontmatter_present():
    text = SKILL.read_text(encoding="utf-8")
    assert text.startswith("---"), "SKILL.md must start with YAML frontmatter"
    assert "name: wiki-doc-review" in text
    # description drives skill triggering — must mention reviewing docs
    head = text.split("---", 2)[1]
    assert "description:" in head and "review" in head.lower()


def test_command_documented_in_readme():
    readme = (REPO / "README.md").read_text(encoding="utf-8")
    assert "/wiki-doc-review" in readme


def test_plugin_keywords_mention_review():
    import json
    data = json.loads((REPO / ".claude-plugin" / "plugin.json").read_text(encoding="utf-8"))
    blob = (data.get("description", "") + " " + " ".join(data.get("keywords", []))).lower()
    assert "wiki-doc-review" in blob or "doc-review" in blob
