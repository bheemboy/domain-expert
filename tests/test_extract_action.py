import os
import subprocess
import sys
from pathlib import Path

import ingest_state

REPO = Path(__file__).resolve().parent.parent


def _jira_import(tmp_path, key, *, escalate=False):
    d = tmp_path / "jira"; d.mkdir(parents=True, exist_ok=True)
    fm = f"---\nkey: {key}\nupdated: 2026-06-16\n"
    if escalate:
        fm += "escalate: true\n"
    fm += "business_relevant: true\n---\n\nbody\n"
    (d / f"{key}.md").write_text(fm)


def test_jira_no_digest_needs_extract(tmp_path, monkeypatch):
    monkeypatch.setenv("IMPORTS_DIR", str(tmp_path))
    assert ingest_state.extract_action("CDS2ASV-1") == "extract-jira"


def test_jira_clean_digest_is_ready(tmp_path, monkeypatch):
    monkeypatch.setenv("IMPORTS_DIR", str(tmp_path))
    _jira_import(tmp_path, "CDS2ASV-1")
    assert ingest_state.extract_action("CDS2ASV-1") == "ready"


def test_jira_escalated_digest_needs_reextract(tmp_path, monkeypatch):
    monkeypatch.setenv("IMPORTS_DIR", str(tmp_path))
    _jira_import(tmp_path, "CDS2ASV-1", escalate=True)
    assert ingest_state.extract_action("CDS2ASV-1") == "reextract-jira"


def test_doc_no_digest_needs_extract(tmp_path, monkeypatch):
    monkeypatch.setenv("IMPORTS_DIR", str(tmp_path))
    assert ingest_state.extract_action("docs/spec.pdf") == "extract-doc"


def test_doc_with_digest_is_triage(tmp_path, monkeypatch):
    monkeypatch.setenv("IMPORTS_DIR", str(tmp_path))
    ip = ingest_state.import_path("docs/spec.pdf")
    ip.parent.mkdir(parents=True, exist_ok=True)
    ip.write_text("---\nkey: x\n---\nbody\n")
    assert ingest_state.extract_action("docs/spec.pdf") == "triage"


def test_code_and_prose_are_triage(tmp_path, monkeypatch):
    monkeypatch.setenv("IMPORTS_DIR", str(tmp_path))
    assert ingest_state.extract_action("src/main.py") == "triage"
    assert ingest_state.extract_action("docs/readme.md") == "triage"


def _cli(tmp_path, ident):
    env = dict(os.environ, IMPORTS_DIR=str(tmp_path))
    return subprocess.run(
        [sys.executable, "scripts/ingest_state.py", "extract-action", ident],
        capture_output=True, text=True, env=env, cwd=REPO,
    )


def test_extract_action_cli_triage(tmp_path):
    out = _cli(tmp_path, "src/main.py")
    assert out.returncode == 0
    assert out.stdout.strip() == "triage"


def test_extract_action_cli_jira_key(tmp_path):
    # primary dispatch case: a bare Jira key with no import present
    out = _cli(tmp_path, "CDS2ASV-1")
    assert out.returncode == 0
    assert out.stdout.strip() == "extract-jira"
