"""lint_scope.py — deterministic scope resolution for the semantic lint.

The semantic lint runs in two scopes (delta, full); this module computes the
*page set* for each with no model judgment, mirroring the deterministic spirit
of lint_wiki.py. The skills call these helpers, then hand the resulting page
list to the lint subagent (prompts/lint-prompt.md).

  * changed_since_last_lint(log_text) -> slugs synthesized since the last
    deliberate lint line (the watermark), by append position.
  * one_hop_neighbors(changed, wiki_dir) -> changed plus inbound/outbound
    [[wikilink]] neighbors (the delta page set to audit).
  * shard_pages(wiki_dir, budget_lines) -> folder-aware partition of all content
    pages for a full audit, each shard within a line budget.

Pure stdlib; importable (tests) and runnable (skills) via main().
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

import config
import lint_wiki

# The watermark is the last *deliberate* lint line. `lint` and `lint --full`
# match; a hypothetical `synth-lint` starts with "synth-" so it never matches.
_LINT_LINE_RE = re.compile(r"^## \[[^\]]*\] lint\b")
# Event lines that changed the wiki carry a `pages:` field; `pages read:` (query)
# has a space before the colon, so the literal `pages:` will not match it.
_PAGES_RE = re.compile(r"\bpages:\s*([^|]+)")


def changed_since_last_lint(log_text: str) -> list[str]:
    """Page slugs from `pages:` fields appended after the last deliberate lint."""
    lines = log_text.splitlines()
    last_lint = -1
    for i, line in enumerate(lines):
        if _LINT_LINE_RE.match(line):
            last_lint = i  # keep the LAST one, by append position
    changed: list[str] = []
    seen: set[str] = set()
    for line in lines[last_lint + 1:]:
        m = _PAGES_RE.search(line)
        if not m:
            continue
        for raw in m.group(1).split(","):
            slug = raw.strip()
            if slug and slug not in seen:
                seen.add(slug)
                changed.append(slug)
    return changed


def one_hop_neighbors(changed, wiki_dir: Path) -> list[str]:
    """`changed` plus their inbound + outbound [[wikilink]] neighbors."""
    changed = set(changed)
    pages = sorted(wiki_dir.rglob("*.md"))
    text = {p: p.read_text(encoding="utf-8") for p in pages}
    real_slugs = {lint_wiki._slug(p) for p in pages}
    out = set(changed)
    for p in pages:
        slug = lint_wiki._slug(p)
        targets = lint_wiki._wikilink_targets(text[p])
        if slug in changed:
            out |= targets            # outbound: pages this changed page links to
        if targets & changed:
            out.add(slug)             # inbound: pages that link to a changed page
    return sorted(s for s in out if s in real_slugs)
