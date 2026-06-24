import lint_style_guide as lsg


def test_flags_vendor_tokens():
    out = lsg.lint_text("style-rules.md", "- **R-FMT-06:** Bold the Agilent OpenLab CID button.\n")
    joined = "\n".join(out)
    assert "Agilent" in joined and "style-rules.md:1" in joined
    # each distinct vendor token is reported
    assert any("OpenLab" in f for f in out)
    assert any("CID" in f for f in out)


def test_flags_dropped_rule_ids():
    out = lsg.lint_text("style-rules.md", "- **R-REVIEW-01:** wrap headings in <mark>.\n")
    assert any("R-REVIEW-01" in f and "dropped" in f.lower() for f in out)
    out2 = lsg.lint_text("style-rules.md", "- **R-LINK-06:** open external links in a new tab.\n")
    assert any("R-LINK-06" in f for f in out2)


def test_flags_brand_colors_and_resolution():
    out = lsg.lint_text("style-rules.md", "Use #0073B7 at 1920×1080.\n")
    assert any("#0073B7" in f for f in out)
    assert any("1920" in f for f in out)


def test_clean_text_has_no_findings():
    text = (
        "- **R-VOICE-01:** Address the reader in second person (you).\n"
        "- **R-FMT-06:** Bold the **Next** button; show the system message in plain prose.\n"
    )
    assert lsg.lint_text("style-rules.md", text) == []


def test_lint_dir_detects_duplicate_ids(tmp_path):
    (tmp_path / "a.md").write_text("- **R-VOICE-01:** first.\n", encoding="utf-8")
    (tmp_path / "b.md").write_text("- **R-VOICE-01:** duplicate id.\n", encoding="utf-8")
    out = lsg.lint_dir(tmp_path)
    assert any("R-VOICE-01" in f and "duplicate" in f.lower() for f in out)


def test_lint_dir_clean(tmp_path):
    (tmp_path / "a.md").write_text("- **R-VOICE-01:** second person.\n", encoding="utf-8")
    (tmp_path / "b.md").write_text("- **R-FMT-06:** bold the label.\n", encoding="utf-8")
    assert lsg.lint_dir(tmp_path) == []
