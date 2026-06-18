import jira_utils

DOC = """> **Exported**: 2026-06-10
> **Source**: `https://x/browse/CDS2ASV-1`

# CDS2ASV-1 — Title

Body text here.
"""


def test_hash_is_stable_and_ignores_export_header():
    a = DOC
    b = DOC.replace("2026-06-10", "2026-06-11")  # only volatile header differs
    assert jira_utils.content_hash(a) == jira_utils.content_hash(b)


def test_hash_changes_with_body():
    changed = DOC.replace("Body text here.", "Body text CHANGED.")
    assert jira_utils.content_hash(DOC) != jira_utils.content_hash(changed)


def test_hash_is_hex_sha256():
    h = jira_utils.content_hash(DOC)
    assert len(h) == 64 and all(c in "0123456789abcdef" for c in h)
