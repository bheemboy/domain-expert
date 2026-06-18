import shutil
import subprocess
from pathlib import Path

import pytest

import doc_convert


def test_needs_conversion_by_extension():
    assert doc_convert.needs_conversion("a/b/report.pdf") is True
    assert doc_convert.needs_conversion("DECK.PPTX") is True
    assert doc_convert.needs_conversion("notes.docx") is True
    assert doc_convert.needs_conversion("readme.md") is False
    assert doc_convert.needs_conversion("main.py") is False
    assert doc_convert.needs_conversion("data.txt") is False


@pytest.mark.skipif(not shutil.which("pandoc"), reason="pandoc not installed")
def test_convert_docx_roundtrip(tmp_path):
    md = tmp_path / "src.md"
    md.write_text("# Title\n\nThe quick brown fox.\n")
    docx = tmp_path / "src.docx"
    subprocess.run(["pandoc", str(md), "-o", str(docx)], check=True,
                   capture_output=True)
    text = doc_convert.convert(docx)
    assert text is not None
    assert "quick brown fox" in text


@pytest.mark.skipif(not shutil.which("pdftotext") or not shutil.which("soffice"),
                    reason="pdftotext/soffice not installed")
def test_convert_pdf(tmp_path):
    txt = tmp_path / "src.txt"
    txt.write_text("Hello from a pdf document.\n")
    subprocess.run(["soffice", "--headless", "--convert-to", "pdf",
                    "--outdir", str(tmp_path), str(txt)], check=True,
                   capture_output=True)
    pdf = tmp_path / "src.pdf"
    assert pdf.is_file()
    text = doc_convert.convert(pdf)
    assert text is not None
    assert "Hello from a pdf" in text


def test_convert_unsupported_returns_none(tmp_path):
    f = tmp_path / "note.md"
    f.write_text("not a binary doc")
    assert doc_convert.convert(f) is None


def test_convert_whitespace_only_is_none(monkeypatch, tmp_path):
    # A valid PDF that yields only whitespace/form-feed (e.g. a scanned image)
    # must be treated as "no text" -> None, so the caller records a media gap.
    f = tmp_path / "scan.pdf"
    f.write_bytes(b"%PDF-1.4 dummy")
    monkeypatch.setattr(doc_convert, "_pdftotext", lambda p: "\x0c\n   \n")
    assert doc_convert.convert(f) is None
