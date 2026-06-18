#!/usr/bin/env python3
"""extract_docs.py — mechanically convert binary-doc paths into raw/imports.

The doc counterpart to the Jira extract, but mechanical (no LLM). For each given
path that is a binary doc whose import isn't present yet, resolve its repo root
from config, convert the file to text, and cache it at its raw/imports location
(raw/imports/<hash8>/<name>.md, or in place under raw/). Non-doc paths (raw
code/text) are skipped — they have no import; synthesis reads them directly.
Jira keys are handled by the Jira extract phase.

Business-relevance is decided later at synthesis, so business_relevant is always
written true here. If conversion is impossible (tool missing / failure), the
import is still written with media_gap: true — a business-relevant doc is never
silently dropped (CLAUDE.md §5 attachment policy).

CLI:
    python scripts/extract_docs.py <path> [<path> ...]
"""

import argparse
import hashlib
from datetime import date
from pathlib import Path

import doc_convert
import ingest_state


def _frontmatter(key: str, rel: str, content_hash: str, media_gap: bool) -> str:
    return (
        "---\n"
        f"key: {key}\n"
        f"updated: {date.today().isoformat()}\n"
        f"source: {rel}\n"
        f"content_hash: {content_hash}\n"
        "kind: doc\n"
        "business_relevant: true\n"
        f"media_gap: {'true' if media_gap else 'false'}\n"
        "---\n"
    )


def extract(path, repo_root) -> Path:
    """Convert one binary doc to its raw/imports location and return the path."""
    path = Path(path)
    repo_root = Path(repo_root)

    rel = path.resolve().relative_to(repo_root.resolve()).as_posix()
    key = ingest_state.doc_key(rel)
    content_hash = hashlib.sha1(path.read_bytes()).hexdigest()

    text = doc_convert.convert(path)
    media_gap = text is None
    body = text if text is not None else (
        f"_Conversion unavailable for `{rel}` — flagged as a media gap; "
        f"install the needed tool or convert by hand._\n"
    )

    out = ingest_state.import_path(str(path))
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(_frontmatter(key, rel, content_hash, media_gap) + "\n" + body,
                   encoding="utf-8")
    return out


def run(paths) -> list[Path]:
    """Convert each given path that is a binary doc still lacking an import."""
    written: list[Path] = []
    for p in paths:
        p = str(p)
        if ingest_state.is_doc(p) and not ingest_state.has_import(p):
            root = ingest_state.repo_root_of(p)
            written.append(extract(p, repo_root=root))
    return written


def main() -> None:
    ap = argparse.ArgumentParser(description="Convert binary-doc paths to raw/imports.")
    ap.add_argument("paths", nargs="+")
    args = ap.parse_args()
    for out in run(args.paths):
        print(out)


if __name__ == "__main__":
    main()
