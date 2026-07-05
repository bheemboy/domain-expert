"""doc_convert.py — convert one binary document (PDF/Office) to plain text.

This is the *awkward raw* step: a digest is kept only where raw must be
converted to be readable. Pure of key/digest concerns — given a file path it
returns text, or None when the file isn't a convertible binary doc or the needed
tool is missing / fails (the caller then records a media gap).

Dispatch:
  .pdf                         -> docling (markdown; optional) else pdftotext -layout
  .docx, .odt                  -> pandoc -t markdown
  .pptx, .ppt, .xlsx, .xls,    -> libreoffice --headless --convert-to pdf
  .doc                            then pdftotext

docling is preferred for PDFs because it reconstructs reading order on
multi-column pages and emits real markdown tables; pdftotext -layout interleaves
columns line-by-line. docling is a required dependency (requirements.txt); the
pdftotext fallback exists for per-file docling failures (corrupt/encrypted PDF),
and degrades the whole PDF path only where docling was never installed.
"""

import shutil
import subprocess
import tempfile
import threading
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


_docling_converter = None  # lazy singleton: model load is expensive, reuse across calls

# docling runs in-process (no subprocess timeout like _run), so a hung parse is
# bounded by an abandonable worker thread instead. ~11 s/page on CPU observed;
# 30 s/page leaves generous headroom before declaring a hang.
_DOCLING_BASE_TIMEOUT = 600
_DOCLING_PER_PAGE_TIMEOUT = 30


def _page_count(pdf: Path) -> int | None:
    if not shutil.which("pdfinfo"):
        return None
    try:
        r = _run(["pdfinfo", str(pdf)])
        for line in r.stdout.splitlines() if r.returncode == 0 else []:
            if line.startswith("Pages:"):
                return int(line.split()[1])
    except Exception:
        pass
    return None


def _timeout_for(pages: int | None) -> float:
    return max(_DOCLING_BASE_TIMEOUT, (pages or 0) * _DOCLING_PER_PAGE_TIMEOUT)


def _docling(pdf: Path, timeout: float | None = None) -> str | None:
    global _docling_converter
    try:
        if _docling_converter is None:
            from docling.document_converter import DocumentConverter
            _docling_converter = DocumentConverter()
        from docling.datamodel.base_models import ConversionStatus

        done: list[tuple] = []

        def work():
            res = _docling_converter.convert(str(pdf), raises_on_error=False)
            done.append((res.status, res.document.export_to_markdown()))

        t = threading.Thread(target=work, daemon=True)
        t.start()
        t.join(timeout if timeout is not None else _timeout_for(_page_count(pdf)))
        if t.is_alive() or not done:
            # hang (thread abandoned) or the worker raised before appending
            return None
        status, md = done[0]
        if status != ConversionStatus.SUCCESS:
            # FAILURE, and also PARTIAL_SUCCESS: silently missing pages is worse
            # than falling back to pdftotext for the whole document
            return None
        return md if md and md.strip() else None
    except Exception:
        return None


def _pdf_text(pdf: Path) -> str | None:
    text = _docling(pdf)
    if text and text.strip():
        return text
    return _pdftotext(pdf)


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
        text = _pdf_text(p)
    elif ext in PANDOC_EXTS:
        text = _pandoc(p)
    elif ext in SOFFICE_EXTS:
        text = _soffice_then_pdftotext(p)
    else:
        text = None
    return text if (text and text.strip()) else None
