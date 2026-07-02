import hashlib
from pathlib import Path

import pytest

import config
import ingest_state
from sources import repo_relative


def test_jira_import_path(tmp_path, monkeypatch):
    monkeypatch.setenv("IMPORTS_DIR", str(tmp_path))
    p = ingest_state.import_path("jira-export-cds2asv-846-story.md")
    assert p == tmp_path / "jira" / "CDS2ASV-846.md"


def test_doc_outside_raw_goes_to_hash_folder(tmp_path, monkeypatch):
    monkeypatch.setenv("IMPORTS_DIR", str(tmp_path))
    p = ingest_state.import_path("teamA/report.pdf")
    h = hashlib.sha1(repo_relative("teamA").encode()).hexdigest()[:8]
    assert p == tmp_path / h / "report.md"


def test_docs_in_same_dir_share_hash_folder(tmp_path, monkeypatch):
    monkeypatch.setenv("IMPORTS_DIR", str(tmp_path))
    a = ingest_state.import_path("teamA/report.pdf")
    b = ingest_state.import_path("teamA/summary.docx")
    assert a.parent == b.parent
    assert a.name == "report.md" and b.name == "summary.md"


def test_doc_under_raw_is_in_place(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "wiki_root", lambda: tmp_path)
    monkeypatch.setenv("IMPORTS_DIR", str(tmp_path / "raw" / "imports"))
    src = tmp_path / "raw" / "userdocs" / "guide.docx"
    src.parent.mkdir(parents=True)
    src.write_bytes(b"x")
    assert ingest_state.import_path(str(src)) == tmp_path / "raw" / "userdocs" / "guide.md"


def test_code_has_no_import_path():
    with pytest.raises(ValueError):
        ingest_state.import_path("src/main.py")


def test_has_import_true_false(tmp_path, monkeypatch):
    monkeypatch.setenv("IMPORTS_DIR", str(tmp_path))
    assert ingest_state.has_import("CDS2ASV-1") is False
    (tmp_path / "jira").mkdir()
    (tmp_path / "jira" / "CDS2ASV-1.md").write_text("---\nkey: CDS2ASV-1\n---\n")
    assert ingest_state.has_import("CDS2ASV-1") is True
    assert ingest_state.has_import("src/main.py") is False  # ValueError -> False


def test_is_import_detection(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "wiki_root", lambda: tmp_path)
    monkeypatch.setenv("IMPORTS_DIR", str(tmp_path / "raw" / "imports"))
    pdfs = tmp_path / "raw" / "pdfs"
    pdfs.mkdir(parents=True)
    (pdfs / "guide.pdf").write_bytes(b"x")
    (pdfs / "guide.md").write_text("in-place import of guide.pdf")
    (pdfs / "notes.md").write_text("hand-written prose, no binary sibling")
    jira_imports = tmp_path / "raw" / "imports" / "jira"
    jira_imports.mkdir(parents=True)
    (jira_imports / "PROJ-1.md").write_text("ticket import")

    assert ingest_state.is_import(str(pdfs / "guide.md")) is True      # in-place import
    assert ingest_state.is_import(str(pdfs / "guide.pdf")) is False    # the source itself
    assert ingest_state.is_import(str(pdfs / "notes.md")) is False     # legit prose
    assert ingest_state.is_import(str(jira_imports / "PROJ-1.md")) is True
