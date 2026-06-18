import jira_utils


def test_stamp_digest_hash_adds_frontmatter_line(tmp_path, monkeypatch):
    digest = tmp_path / "CDS2ASV-1.md"
    digest.write_text(
        "---\nkey: CDS2ASV-1\nupdated: 2026-06-10\n"
        "source_url: https://x/browse/CDS2ASV-1\nbusiness_relevant: true\n---\n# body\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(jira_utils, "_rendered_md_for", lambda key: "# CDS2ASV-1\n\nBody.\n")
    jira_utils.stamp_digest_hash("CDS2ASV-1", digest)
    text = digest.read_text(encoding="utf-8")
    assert "content_hash: " in text
    # idempotent: stamping again yields identical content
    before = text
    jira_utils.stamp_digest_hash("CDS2ASV-1", digest)
    assert digest.read_text(encoding="utf-8") == before


def test_stamp_replaces_existing_hash(tmp_path, monkeypatch):
    digest = tmp_path / "CDS2ASV-1.md"
    digest.write_text(
        "---\nkey: CDS2ASV-1\ncontent_hash: oldhash\nbusiness_relevant: true\n---\n# b\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(jira_utils, "_rendered_md_for", lambda key: "# new content\n")
    jira_utils.stamp_digest_hash("CDS2ASV-1", digest)
    text = digest.read_text(encoding="utf-8")
    assert "oldhash" not in text
    assert text.count("content_hash:") == 1
