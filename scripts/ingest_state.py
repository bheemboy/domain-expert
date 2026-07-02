#!/usr/bin/env python3
"""ingest_state.py — classify/key/import helpers for the queue-based pipeline.

Maps a source identity (a Jira KEY or a file path) to its import key, classifies it
for the synthesizer, and reports the extract action the ingest driver should take.
Queue state lives in queues.py; no manifest state is tracked here.

Usage:
    python scripts/ingest_state.py key            <path>   # print derived KEY
    python scripts/ingest_state.py import-path    <path>   # print the raw/imports path for an identity
    python scripts/ingest_state.py classify       <path>   # print kind<TAB>read_target
    python scripts/ingest_state.py extract-action <path>   # print extract action for an identity
"""

import hashlib
import os
import re
import sys
from pathlib import Path
import config
import queues
from sources import repo_root_of, repo_relative  # canonical home: sources.py

_PROJECT_KEY = config.project_key()
_KEY_RE = re.compile(rf"{re.escape(_PROJECT_KEY)}-(\d+)", re.IGNORECASE)

# Binary-doc extensions that get a converted-text digest (Spec §2/§7).
_DOC_EXTS = {".pdf", ".docx", ".doc", ".odt", ".pptx", ".ppt", ".xlsx", ".xls"}
_SLUG_RE = re.compile(r"[^a-z0-9]+")

# Raw text files synthesized directly as prose (tag (doc-stated)); everything
# else raw is treated as code (tag (code-confirmed)).
_RAW_PROSE_EXTS = {".md", ".txt", ".rst", ".markdown", ".adoc"}


def is_doc(path: str) -> bool:
    return Path(path).suffix.lower() in _DOC_EXTS


def doc_key(rel_path: str) -> str:
    """Stable, collision-free key for a binary-doc digest: doc__<slug>__<hash8>.

    `rel_path` should be the repo-relative path, so the key is stable across
    checkout moves. The readable stem may collide; the path hash guarantees
    uniqueness.
    """
    rel = Path(rel_path).as_posix().lstrip("/")
    h = hashlib.sha1(rel.encode("utf-8")).hexdigest()[:8]
    stem = _SLUG_RE.sub("-", Path(rel).stem.lower()).strip("-")[:60]
    return f"doc__{stem}__{h}"


def _imports_dir() -> Path:
    return Path(os.environ.get("IMPORTS_DIR", "raw/imports"))


def _raw_root() -> Path:
    return (config.wiki_root() / "raw").resolve()


def key_of(path: str) -> str:
    """Derive a stable identity for a source path (dispatcher).

    Jira prefix -> Jira key; binary doc -> doc__ key; text/code -> ValueError
    (those are read directly, never imported).
    """
    m = _KEY_RE.search(Path(path).name)
    if m:
        return f"{_PROJECT_KEY}-{m.group(1)}"
    if is_doc(path):
        return doc_key(repo_relative(path))
    raise ValueError(f"no key derivable from {path!r}")


def import_path(path: str) -> Path:
    """On-disk location of the imported (materialized) copy of an awkward source.

    Jira            -> raw/imports/jira/<KEY>.md
    doc under raw/  -> in-place sibling <dir>/<name>.md
    doc elsewhere   -> raw/imports/<hash8-of-parent-dir>/<name>.md
    code/prose      -> ValueError (read directly, never imported)
    """
    if _is_jira(path):
        return _imports_dir() / "jira" / f"{key_of(path)}.md"
    if is_doc(path):
        p = Path(path)
        abs_p = p.resolve()
        if abs_p.is_relative_to(_raw_root()):
            return abs_p.with_suffix(".md")
        parent_rel = repo_relative(str(p.parent))
        h = hashlib.sha1(parent_rel.encode("utf-8")).hexdigest()[:8]
        return _imports_dir() / h / f"{p.stem}.md"
    raise ValueError(f"no import path for {path!r}")


def has_import(path: str) -> bool:
    try:
        return import_path(path).is_file()
    except ValueError:
        return False


def is_import(path: str) -> bool:
    """True if `path` IS an extract-owned import artifact — never a raw source:
    anything under the imports tree, or the in-place .md sibling of a binary doc
    under raw/. Enqueueing an import as a source double-ingests its document."""
    p = Path(path).resolve()
    if p.is_relative_to(_imports_dir().resolve()):
        return True
    if p.suffix.lower() == ".md" and p.is_relative_to(_raw_root()):
        return any(p.with_suffix(ext).is_file() for ext in _DOC_EXTS)
    return False


def classify(path: str) -> tuple[str, str]:
    """Map a queued identity to (kind, read_target) for the synthesizer.

      ("jira",  <import path>)   -> (ticket-only)
      ("doc",   <import path>)   -> (doc-stated)   [converted binary doc]
      ("prose", <raw file path>) -> (doc-stated)   [.md/.txt/... read directly]
      ("code",  <raw file path>) -> (code-confirmed) [source read directly]
    """
    if _is_jira(path):
        return "jira", str(import_path(path))
    if is_doc(path):
        return "doc", str(import_path(path))
    if Path(path).suffix.lower() in _RAW_PROSE_EXTS:
        return "prose", str(path)
    return "code", str(path)


_ESC_RE = re.compile(r"^escalate:\s*true\s*$", re.MULTILINE)


def is_escalated(path: str) -> bool:
    """Import exists but its frontmatter carries ``escalate: true`` (D9)."""
    try:
        dp = import_path(path)
    except ValueError:
        return False
    if not dp.is_file():
        return False
    text = dp.read_text(encoding="utf-8")
    if not text.startswith("---"):
        return False
    end = text.find("\n---", 3)
    return bool(_ESC_RE.search(text[3 : end if end != -1 else len(text)]))


def _is_jira(path: str) -> bool:
    return bool(_KEY_RE.search(Path(path).name))


def extract_action(path: str) -> str:
    """What extraction a queued identity needs, for the ingest driver to dispatch on:

      "extract-jira"   Jira key, no import yet            -> Haiku extract subagent
      "reextract-jira" Jira import flagged escalate       -> Sonnet re-extract subagent
      "ready"          Jira/doc clean import already exists -> no work; move to .synth
                       (only reached on an interrupted-run resume)
      "extract-doc"    binary doc, no import yet          -> extract_docs.py (mechanical)
      "triage"         code/prose (read directly), OR a doc whose converted import now
                       exists -> Haiku triage subagent (skip-or-keep + lines + flag)
      "triage-forced"  forced item: triage runs for guidance but may not skip
    """
    if _is_jira(path):
        if not has_import(path):
            return "extract-jira"
        return "reextract-jira" if is_escalated(path) else "ready"
    if is_doc(path):
        if not has_import(path):
            return "extract-doc"
        return "triage-forced" if queues.is_forced(path) else "triage"
    return "triage-forced" if queues.is_forced(path) else "triage"


def main() -> None:
    a = sys.argv[1:]
    if not a:
        print(__doc__)
        sys.exit(2)
    cmd = a[0]
    try:
        if cmd == "key":
            print(key_of(a[1]))
            sys.exit(0)
        if cmd == "import-path":
            print(import_path(a[1]))
            sys.exit(0)
        if cmd == "classify":
            kind, target = classify(a[1])
            print(f"{kind}\t{target}")
            sys.exit(0)
        if cmd == "extract-action":
            print(extract_action(a[1]))
            sys.exit(0)
    except IndexError:
        print(__doc__)
        sys.exit(2)
    except ValueError as e:
        print(f"ERROR: {e}", file=sys.stderr)
        sys.exit(2)
    print(f"unknown command: {cmd}", file=sys.stderr)
    sys.exit(2)


if __name__ == "__main__":
    main()
