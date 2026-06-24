"""doc_scope.py — resolve and shard the document set for /wiki-doc-review.

Read-only. Resolves the skill's optional <doc-path|folder> argument to a concrete
list of doc files (or all configured docs when no arg), and shards a doc list for
workflow fan-out. Mirrors lint_scope.py's deterministic-scope role. Pure stdlib.
"""
from __future__ import annotations

import sys
from pathlib import Path

import config  # noqa: F401  (kept for symmetry / future use)
import docs_enum
from ignore import first_match

_DOC_GLOBS = ["**/*.md", "**/*.mdx"]


def resolve_docs(arg: str | None) -> list[Path]:
    """Resolve the review scope to absolute doc paths.

    None        -> all configured docs (docs_enum.enumerate_docs()).
    a file       -> [that file].
    a directory  -> md/mdx files under it (sorted, absolute, de-duplicated).
    Raises FileNotFoundError if arg names a path that does not exist.
    """
    if arg is None:
        return docs_enum.enumerate_docs()
    p = Path(arg).expanduser()
    if not p.exists():
        raise FileNotFoundError(f"no such doc path: {arg}")
    p = p.resolve()
    if p.is_file():
        return [p]
    out: list[Path] = []
    for f in sorted(p.rglob("*")):
        if f.is_file() and first_match(f.relative_to(p).as_posix(), _DOC_GLOBS) is not None:
            out.append(f.resolve())
    return out


def shard_docs(docs: list[Path], max_per_shard: int = 8) -> list[list[Path]]:
    """Order-preserving partition of docs into shards of at most max_per_shard."""
    if max_per_shard < 1:
        raise ValueError("max_per_shard must be >= 1")
    return [docs[i:i + max_per_shard] for i in range(0, len(docs), max_per_shard)]


def main() -> int:
    arg = sys.argv[1] if len(sys.argv) > 1 else None
    for p in resolve_docs(arg):
        print(p)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
