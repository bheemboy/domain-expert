"""Guard the Documentation Domain Context override block in the CLAUDE.md schema.

The /wiki-doc-review and /wiki-doc-author skills read four override buckets from a
"Documentation Domain Context" block in the host wiki's CLAUDE.md. wiki-init
scaffolds that block INSIDE §0 (the only project-specific section) so its upgrade
mode — which preserves §0 verbatim and replaces §1+ — never clobbers it.
"""
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
TMPL = REPO / "schema" / "CLAUDE.md.tmpl"


def _section0(text: str) -> str:
    s0 = text.index("## 0. Project identity")
    s1 = text.index("## 1. Raw", s0)
    return text[s0:s1]


def test_documentation_domain_context_block_present_in_section_0():
    block = _section0(TMPL.read_text(encoding="utf-8"))
    assert "Documentation Domain Context" in block
    # the four override buckets the /wiki-doc-* skills read, by exact name
    for key in ("vendor_name", "forbidden_role_names", "identifier_patterns", "platform"):
        assert key in block, f"missing override bucket: {key}"
    # a project term-table override is documented, and the default platform is named
    assert "term" in block.lower() and "table" in block.lower()
    assert "docusaurus" in block


def test_documentation_domain_context_ships_commented():
    block = _section0(TMPL.read_text(encoding="utf-8"))
    after = block[block.index("Documentation Domain Context"):]
    # override VALUES ship inside an HTML comment, so industry-standard defaults apply
    # until the user uncomments — vendor_name/platform must sit within <!-- ... -->.
    open_c = after.index("<!--")
    close_c = after.index("-->", open_c)
    commented = after[open_c:close_c]
    assert "vendor_name" in commented and "platform: docusaurus" in commented
