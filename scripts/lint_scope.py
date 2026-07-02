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

# The watermark is the newest *deliberate* lint event. `lint` and `lint --full`
# match; a hypothetical `synth-lint` starts with "synth-" so it never matches.
# Two log formats are supported: legacy (one `## [DATE] op | …` heading per
# event, appended oldest-first) and OKF (`## YYYY-MM-DD` date headings with
# `- op | …` bullets, strictly newest-first — see CLAUDE.md §6).
_LINT_LINE_RE = re.compile(r"^## \[[^\]]*\] lint\b")
_OKF_DATE_RE = re.compile(r"^## \d{4}-\d{2}-\d{2}\s*$")
_OKF_LINT_BULLET_RE = re.compile(r"^- lint\b")
# Event lines that changed the wiki carry a `pages:` field; `pages read:` (query)
# has a space before the colon, so the literal `pages:` will not match it.
_PAGES_RE = re.compile(r"\bpages:\s*([^|]+)")


def _collect_pages(lines, seen: set[str], changed: list[str]) -> None:
    for line in lines:
        m = _PAGES_RE.search(line)
        if not m:
            continue
        for raw in m.group(1).split(","):
            slug = raw.strip()
            if slug and slug not in seen:
                seen.add(slug)
                changed.append(slug)


def changed_since_last_lint(log_text: str) -> list[str]:
    """Page slugs from `pages:` fields of events newer than the last deliberate lint."""
    lines = log_text.splitlines()
    changed: list[str] = []
    seen: set[str] = set()

    if any(_OKF_DATE_RE.match(l) for l in lines):
        # OKF newest-first log: everything ABOVE the first lint bullet is newer.
        newer: list[str] = []
        for line in lines:
            if _OKF_LINT_BULLET_RE.match(line):
                break
            newer.append(line)
        _collect_pages(newer, seen, changed)
        return changed

    # Legacy append-order log: everything AFTER the last lint heading is newer.
    last_lint = -1
    for i, line in enumerate(lines):
        if _LINT_LINE_RE.match(line):
            last_lint = i  # keep the LAST one, by append position
    _collect_pages(lines[last_lint + 1:], seen, changed)
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


def _folder(p: Path, wiki_dir: Path) -> str:
    rel = p.relative_to(wiki_dir)
    return rel.parts[0] if len(rel.parts) > 1 else "(root)"


def shard_pages(wiki_dir: Path, budget_lines: int = 3500) -> list[list[str]]:
    """Folder-aware partition of content pages, each shard within a line budget."""
    pages = sorted(p for p in wiki_dir.rglob("*.md")
                   if lint_wiki._slug(p) not in lint_wiki.ENTRY_PAGES)
    by_folder: dict[str, list[Path]] = {}
    for p in pages:
        by_folder.setdefault(_folder(p, wiki_dir), []).append(p)
    shards: list[list[str]] = []
    for folder in sorted(by_folder):
        cur: list[str] = []
        cur_lines = 0
        for p in by_folder[folder]:
            n = p.read_text(encoding="utf-8").count("\n") + 1
            if cur and cur_lines + n > budget_lines:
                shards.append(cur)
                cur, cur_lines = [], 0
            cur.append(lint_wiki._slug(p))
            cur_lines += n
        if cur:
            shards.append(cur)
    return shards


def main(argv=None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)
    if not args or args[0] not in ("delta", "full"):
        print("usage: lint_scope.py delta [--count] | full [budget_lines]", file=sys.stderr)
        return 2
    wiki = config.wiki_root() / "wiki"
    if args[0] == "delta":
        log = wiki / "log.md"
        log_text = log.read_text(encoding="utf-8") if log.is_file() else ""
        pages = one_hop_neighbors(changed_since_last_lint(log_text), wiki)
        if "--count" in args[1:]:
            print(len(pages))          # just the size, for the synth gate's threshold check
        else:
            for slug in pages:
                print(slug)
        return 0
    if len(args) > 1:
        try:
            budget = int(args[1])
        except ValueError:
            print("usage: lint_scope.py delta [--count] | full [budget_lines]", file=sys.stderr)
            return 2
    else:
        budget = 3500
    for shard in shard_pages(wiki, budget):
        print(",".join(shard))
    return 0


if __name__ == "__main__":
    sys.exit(main())
