"""doc_convert.py — convert one binary document (PDF/Office) to plain text.

This is the *awkward raw* step: the spec keeps a digest only where raw must be
converted to be readable. Pure of key/digest concerns — given a file path it
returns text, or None when the file isn't a convertible binary doc or the needed
tool is missing / fails (the caller then records a media gap).

Dispatch:
  .pdf                         -> pdftotext -layout
  .docx, .odt                  -> pandoc -t markdown
  .pptx, .ppt, .xlsx, .xls,    -> libreoffice --headless --convert-to pdf
  .doc                            then pdftotext
"""

import shutil
import subprocess
import tempfile
from pathlib import Path

PDF_EXTS = {".pdf"}
PANDOC_EXTS = {".docx", ".odt"}
SOFFICE_EXTS = {".pptx", ".ppt", ".xlsx", ".xls", ".doc"}
CONVERTIBLE = PDF_EXTS | PANDOC_EXTS | SOFFICE_EXTS


def needs_conversion(path) -> bool:
    return Path(path).suffix.lower() in CONVERTIBLE


def _run(cmd: list[str]) -> subprocess.CompletedProcess:
    return subprocess.run(cmd, capture_output=True, text=True, timeout=300)


def _pdftotext(pdf: Path) -> str | None:
    if not shutil.which("pdftotext"):
        return None
    r = _run(["pdftotext", "-layout", str(pdf), "-"])
    return r.stdout if r.returncode == 0 else None


def _pandoc(doc: Path) -> str | None:
    if not shutil.which("pandoc"):
        return None
    r = _run(["pandoc", str(doc), "-t", "markdown"])
    return r.stdout if r.returncode == 0 else None


def _soffice_then_pdftotext(doc: Path) -> str | None:
    soffice = shutil.which("soffice") or shutil.which("libreoffice")
    if not soffice or not shutil.which("pdftotext"):
        return None
    with tempfile.TemporaryDirectory() as td:
        r = _run([soffice, "--headless", "--convert-to", "pdf",
                  "--outdir", td, str(doc)])
        if r.returncode != 0:
            return None
        pdf = Path(td) / (doc.stem + ".pdf")
        if not pdf.is_file():
            return None
        return _pdftotext(pdf)


def convert(path) -> str | None:
    """Convert a binary doc to text, or None if not convertible / tool missing /
    the document has no extractable text (whitespace-only output)."""
    p = Path(path)
    ext = p.suffix.lower()
    if ext in PDF_EXTS:
        text = _pdftotext(p)
    elif ext in PANDOC_EXTS:
        text = _pandoc(p)
    elif ext in SOFFICE_EXTS:
        text = _soffice_then_pdftotext(p)
    else:
        text = None
    return text if (text and text.strip()) else None
