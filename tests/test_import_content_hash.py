import check_for_changes as cfc
import config


def test_reads_hash_from_imports_jira(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "wiki_root", lambda: tmp_path)
    jira_dir = tmp_path / "raw" / "imports" / "jira"
    jira_dir.mkdir(parents=True)
    (jira_dir / "CDS2ASV-9.md").write_text(
        "---\nkey: CDS2ASV-9\ncontent_hash: abc123\n---\nbody\n")
    assert cfc.import_content_hash("CDS2ASV-9") == "abc123"


def test_missing_import_returns_none(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "wiki_root", lambda: tmp_path)
    assert cfc.import_content_hash("CDS2ASV-9") is None
