"""docs_enum.py — enumerate a product's customer-facing doc files.

Walks each configured `docs:` location and returns the files matching the
include globs and not matching the exclude globs (ignore.py semantics, over the
location-relative POSIX path). Pure read-only; never writes. Empty when no
`docs:` location is configured.
"""

from pathlib import Path

import config
from ignore import first_match


def enumerate_docs() -> list[Path]:
    """All customer-facing doc files across configured locations: absolute
    paths, sorted within each location, de-duplicated, in location order."""
    includes = config.docs_include_globs()
    excludes = config.docs_exclude_globs()
    out: list[Path] = []
    seen: set[Path] = set()
    for loc in config.docs_locations():
        if not loc.is_dir():
            continue
        for f in sorted(loc.rglob("*")):
            if not f.is_file():
                continue
            rel = f.relative_to(loc).as_posix()
            if first_match(rel, includes) is None:
                continue
            if excludes and first_match(rel, excludes) is not None:
                continue
            rp = f.resolve()
            if rp not in seen:
                seen.add(rp)
                out.append(rp)
    return out
