"""ignore.py — gitignore-style glob matching over repo-relative POSIX paths.

Pure and dependency-free. A glob is full-matched against a path like
``ac_portal/local_modules/@agilent/common/x.js`` (no leading slash, forward
slashes). Semantics:

    **      matches across path segments (including none)
    **/     optional leading directories (so ``**/*.min.js`` matches at any depth)
    *       matches within a single segment (never crosses ``/``)
    ?       matches exactly one non-``/`` character

A pattern without a leading ``**/`` is anchored at the repo root, so ``*.js``
matches ``x.js`` but not ``a/x.js``. Use ``**/*.js`` for any-depth matching.
"""

import re
from typing import Iterable


def _translate(glob: str) -> str:
    """Translate one glob into a regex body (no anchors)."""
    out: list[str] = []
    i, n = 0, len(glob)
    while i < n:
        c = glob[i]
        if c == "*":
            if i + 1 < n and glob[i + 1] == "*":
                # '**' — consume it; if followed by '/', also consume the slash and
                # make the whole '**/' optional-leading-dirs.
                i += 2
                if i < n and glob[i] == "/":
                    out.append("(?:.*/)?")
                    i += 1
                else:
                    out.append(".*")
            else:
                out.append("[^/]*")
                i += 1
        elif c == "?":
            out.append("[^/]")
            i += 1
        else:
            out.append(re.escape(c))
            i += 1
    return "".join(out)


def compile_glob(glob: str) -> re.Pattern:
    """Full-match regex for a glob over a repo-relative POSIX path."""
    return re.compile(r"\A" + _translate(glob) + r"\Z")


def first_match(rel_path: str, globs: Iterable[str]) -> str | None:
    """The first glob (in iteration order) matching ``rel_path``, else None."""
    for g in globs:
        if compile_glob(g).match(rel_path):
            return g
    return None


def partition(rel_paths: Iterable[str], globs: Iterable[str]) -> tuple[list[str], dict[str, int]]:
    """Split paths into (kept, ignored_by_rule). ``kept`` preserves input order;
    ``ignored_by_rule`` maps each matching glob to how many paths it first-matched."""
    globs = list(globs)
    kept: list[str] = []
    ignored: dict[str, int] = {}
    for p in rel_paths:
        g = first_match(p, globs)
        if g is None:
            kept.append(p)
        else:
            ignored[g] = ignored.get(g, 0) + 1
    return kept, ignored
