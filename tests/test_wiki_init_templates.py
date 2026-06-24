from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
TMPL = REPO / "skills" / "wiki-init" / "templates" / "wiki.config.yaml.tmpl"


def test_config_template_has_docs_block():
    text = TMPL.read_text(encoding="utf-8")
    # A commented docs: block documents how to point at customer-facing help.
    assert "docs:" in text
    assert "location:" in text
    # It must be commented so a fresh config doesn't enable an empty docs lens.
    docs_line = next(ln for ln in text.splitlines() if "docs:" in ln)
    assert docs_line.lstrip().startswith("#"), "docs: block should ship commented out"
