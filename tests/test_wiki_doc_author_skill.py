import json
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
SKILL = REPO / "skills" / "wiki-doc-author" / "SKILL.md"


def test_skill_frontmatter_present():
    text = SKILL.read_text(encoding="utf-8")
    assert text.startswith("---")
    head = text.split("---", 2)[1]
    assert "name: wiki-doc-author" in head
    assert "description:" in head and ("author" in head.lower() or "write" in head.lower())


def test_command_documented_in_readme():
    readme = (REPO / "README.md").read_text(encoding="utf-8")
    assert "/wiki-doc-author" in readme


def test_plugin_manifest_mentions_author():
    data = json.loads((REPO / ".claude-plugin" / "plugin.json").read_text(encoding="utf-8"))
    blob = (data.get("description", "") + " " + " ".join(data.get("keywords", []))).lower()
    assert "wiki-doc-author" in blob or "doc-author" in blob
