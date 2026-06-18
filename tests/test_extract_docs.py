import shutil
import subprocess
import textwrap

import pytest

import ingest_state


def _cfg(tmp_path, monkeypatch, sources):
    state_dir = tmp_path / "state"; state_dir.mkdir(parents=True, exist_ok=True)
    src_yaml = "".join(f"\n          - {s}" for s in sources) or " []"
    cfg = tmp_path / "wiki.config.yaml"
    cfg.write_text(textwrap.dedent(f"""
        project: {{key: TESTPROJ, name: T, config_dir: {state_dir}}}
        jira: {{base_url: https://e.example, jql: 'project = TESTPROJ'}}
        sources:{src_yaml}
    """))
    monkeypatch.setenv("WIKI_CONFIG", str(cfg))


@pytest.mark.skipif(not shutil.which("pandoc"), reason="pandoc not installed")
def test_run_converts_only_docs_and_skips_raw(tmp_path, monkeypatch):
    repo = tmp_path / "repoA"; (repo / "docs").mkdir(parents=True)
    md = repo / "docs" / "d.md"; md.write_text("# D\n\nWidget calibration steps.\n")
    docx = repo / "docs" / "d.docx"
    subprocess.run(["pandoc", str(md), "-o", str(docx)], check=True, capture_output=True)

    imports = tmp_path / "imports"
    _cfg(tmp_path, monkeypatch, sources=[str(repo)])
    monkeypatch.setenv("IMPORTS_DIR", str(imports))

    import extract_docs
    raw = repo / "src" / "main.py"
    written = extract_docs.run([str(docx), str(raw)])

    assert len(written) == 1                                  # only the docx
    assert written[0].name == "d.md"
    assert str(imports) in str(written[0])
    assert "Widget calibration" in written[0].read_text()
    assert ingest_state.has_import(str(docx)) is True
    assert ingest_state.has_import(str(raw)) is False


@pytest.mark.skipif(not shutil.which("pandoc"), reason="pandoc not installed")
def test_run_is_idempotent_skips_existing_import(tmp_path, monkeypatch):
    repo = tmp_path / "repoA"; (repo / "docs").mkdir(parents=True)
    md = repo / "docs" / "d.md"; md.write_text("# D\n\nx\n")
    docx = repo / "docs" / "d.docx"
    subprocess.run(["pandoc", str(md), "-o", str(docx)], check=True, capture_output=True)
    imports = tmp_path / "imports"
    _cfg(tmp_path, monkeypatch, sources=[str(repo)])
    monkeypatch.setenv("IMPORTS_DIR", str(imports))

    import extract_docs
    assert len(extract_docs.run([str(docx)])) == 1
    assert extract_docs.run([str(docx)]) == []   # import exists
