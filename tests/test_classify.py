import subprocess
import sys
import os
from pathlib import Path

import ingest_state

REPO = Path(__file__).resolve().parent.parent


def test_classify_jira(tmp_path, monkeypatch):
    monkeypatch.setenv("IMPORTS_DIR", str(tmp_path))
    kind, target = ingest_state.classify("jira-export-cds2asv-1-story.md")
    assert kind == "jira"
    assert target.endswith("jira/CDS2ASV-1.md")
    assert str(tmp_path) in target


def test_classify_doc(tmp_path, monkeypatch):
    monkeypatch.setenv("IMPORTS_DIR", str(tmp_path))
    kind, target = ingest_state.classify("docs/a.pdf")
    assert kind == "doc"
    assert target.endswith("/a.md")        # original stem, not the doc_key
    assert str(tmp_path) in target


def test_classify_prose_reads_file_directly(tmp_path, monkeypatch):
    monkeypatch.setenv("IMPORTS_DIR", str(tmp_path))
    assert ingest_state.classify("docs/readme.md") == ("prose", "docs/readme.md")
    assert ingest_state.classify("notes/x.txt") == ("prose", "notes/x.txt")


def test_classify_code_reads_file_directly(tmp_path, monkeypatch):
    monkeypatch.setenv("IMPORTS_DIR", str(tmp_path))
    assert ingest_state.classify("src/main.py") == ("code", "src/main.py")
    assert ingest_state.classify("a/b/Service.java") == ("code", "a/b/Service.java")


def test_classify_cli(tmp_path, monkeypatch, capsys):
    # CLI prints "<kind>\t<read_target>" (tab-separated) for one path.
    env = dict(os.environ, IMPORTS_DIR=str(tmp_path))
    out = subprocess.run(
        [sys.executable, "scripts/ingest_state.py", "classify", "src/main.py"],
        capture_output=True, text=True, env=env,
        cwd=REPO,
    )
    assert out.returncode == 0
    assert out.stdout.strip() == "code\tsrc/main.py"
