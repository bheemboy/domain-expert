from pathlib import Path

import lint_style_guide as lsg

STYLE_GUIDE = Path(__file__).resolve().parent.parent / "style-guide"


def test_shipped_style_guide_is_clean():
    findings = lsg.lint_dir(STYLE_GUIDE)
    assert findings == [], "style-guide genericity guard found issues:\n" + "\n".join(findings)


def test_style_guide_has_expected_files():
    for name in [
        "README.md", "style-rules.md", "release-notes.md", "troubleshooting.md",
        "review-checklist.md", "terminology-conventions.md",
        "platforms/docusaurus.md", "platforms/commonmark.md",
    ]:
        assert (STYLE_GUIDE / name).is_file(), f"missing {name}"
