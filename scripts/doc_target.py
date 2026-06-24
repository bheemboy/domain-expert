"""doc_target.py — compute the save path for a /wiki-doc-author page.

slug = kebab-case of the title; the page lands in the FIRST configured docs:
location (Plan 1). Pure stdlib. Read-only (callers do the writing).
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

import config


def slugify(title: str) -> str:
    """Kebab-case slug: lowercase, runs of non-alphanumerics collapse to one
    dash, leading/trailing dashes trimmed."""
    s = re.sub(r"[^a-z0-9]+", "-", title.strip().lower())
    return s.strip("-")


def default_doc_target(title: str, ext: str = ".md") -> Path:
    """First configured docs location / <slug><ext>.

    Raises ValueError if no docs: location is configured or the title yields an
    empty slug.
    """
    locs = config.docs_locations()
    if not locs:
        raise ValueError("no docs: location configured in wiki.config.yaml")
    slug = slugify(title)
    if not slug:
        raise ValueError(f"title produces an empty slug: {title!r}")
    return locs[0] / f"{slug}{ext}"


def main() -> int:
    if len(sys.argv) < 2:
        print('usage: doc_target.py "<title>"', file=sys.stderr)
        return 2
    print(default_doc_target(sys.argv[1]))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
