#!/usr/bin/env python3
"""lint_wiki.py — mechanical (non-LLM) health checks for the wiki.

This is the cheap, deterministic half of lint (CLAUDE.md §5). It catches the
structural problems that are *computable* — no model judgment required:

  * broken [[wikilinks]]   — a link whose target page does not exist
  * orphan pages           — a content page with no inbound [[wikilink]]
  * duplicate slugs        — the same page slug under two folders
  * index drift            — content pages missing from index.md (or vice versa)
  * frontmatter gaps       — pages missing required frontmatter keys
  * missing source link    — a References link to raw/imports/jira/<KEY>.md that doesn't exist
  * stale digest link      — a References link still pointing at digests/ (retired path)
  * stale export link      — a wiki link to a raw jira-exports/ file (old convention;
                             References must link raw/imports/jira/ + live Jira, never raw)

It also runs ONE advisory (warning-only) check that does NOT affect the exit code:

  * supersession-leak      — a *retired* renamed noun (a project/instrument/result/
                             report/path name that some page's name-history shows
                             was renamed to a newer term) still asserted as CURRENT on
                             a SUMMARY surface (index.md / glossary.md) without its
                             successor term on the line. Scope is the catalog/glossary
                             only — the high-risk drift surfaces; detail/history pages
                             narrate each era in that era's vocabulary, so scanning
                             them is too noisy. Deterministic backstop for the
                             rename-cascade gap (CLAUDE.md §5 lint pass 3); heuristic,
                             so reported as WARN and never flips the exit code.

Semantic checks (contradictions, missed supersessions, concept-splits) are NOT
done here — those need the Opus semantic-lint subagent.

Exit code is non-zero if any hard *issue* is found (warnings excluded), so the
synth gate / CI can branch on it. Pure stdlib; run from the repo root:
``python scripts/lint_wiki.py`` (add ``--no-rename-check`` to skip the advisory).
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

import config

_KEY_PREFIX = config.project_key() + "-"

WIKI = Path("wiki")
# Catalog/entry pages: never treated as orphans, never required to be self-listed.
ENTRY_PAGES = {"index", "log", "overview"}
REQUIRED_FRONTMATTER = ("type", "status", "updated")

_WIKILINK_RE = re.compile(r"\[\[([^\]]+)\]\]")
_FRONTMATTER_RE = re.compile(r"^---\n(.*?)\n---", re.DOTALL)
# Markdown links [text](target) — used to validate References targets.
_MDLINK_RE = re.compile(r"\]\(([^)]+)\)")

# --- Rename-leakage (advisory) -------------------------------------------------
# A rename chain is written on a single line as dated, quoted/bolded/coded names
# joined by "→", e.g.  **"Old Product Name"** (2018-04) → **"New Product Name"** (…).
# We harvest those chains to learn which renamed *nouns* are retired (every name
# but the last in a chain) and what each one's later names are.
_TERM_RES = (
    re.compile(r'\*\*"([^"]+)"\*\*'),   # **"Bold Quoted"**
    re.compile(r'\*\*`([^`]+)`\*\*'),   # **`bold code`**
    re.compile(r"\*\*([^*]+)\*\*"),     # **Bold**
    re.compile(r"`([^`]+)`"),           # `code`
    re.compile(r'"([^"]+)"'),           # "quoted"
)
# Only these renamed nouns are specific enough to flag with low false-positive
# risk; bare brand words (the configured `lint.brand_nouns`) legitimately appear in
# era descriptions and are deliberately NOT flagged.
# Brand/era terms are project-specific (wiki.config.yaml `lint:`); the generic
# English era words stay built-in.
_LINT_CFG = config.lint_config()
_FLAGGABLE_NOUNS = _LINT_CFG.get("flaggable_nouns") or []
_BRAND_NOUNS = _LINT_CFG.get("brand_nouns") or []
_ERA_TERMS = _LINT_CFG.get("era_terms") or []
_GENERIC_ERA = ["historical", "formerly", "originally", "rename", "legacy", "superseded"]

_noun_part = ("(" + "|".join(_FLAGGABLE_NOUNS) + r")\b") if _FLAGGABLE_NOUNS else r"(?!x)x"
_brand_part = ("|-(" + "|".join(re.escape(b) for b in _BRAND_NOUNS) + ")-Instrument") if _BRAND_NOUNS else ""
_FLAGGABLE_NOUN_RE = re.compile(_noun_part + _brand_part, re.IGNORECASE)
# A line carrying any of these is treated as history/era-scoped → never a leak.
_ERA_QUALIFIER_RE = re.compile("|".join(_ERA_TERMS + _GENERIC_ERA), re.IGNORECASE)


def _name_like(t: str) -> bool:
    """A chain element must look like a product noun/path, not a prose phrase."""
    if len(t) < 4 or _KEY_PREFIX in t or "→" in t:
        return False
    if re.search(r"\d{4}-\d{2}", t):                      # carries a date → a cite
        return False
    if re.search(r"\b(renamed|replaced|corrected|what|the)\b", t, re.IGNORECASE):
        return False
    # Title-case / path / placeholder shape, e.g. "Renamed Project", "/Some Project",
    # "<Hostname>-<Brand>-Instrument".
    return bool(re.match(r"[A-Z<`/]", t))


def _first_term(segment: str) -> str | None:
    for rx in _TERM_RES:
        m = rx.search(segment)
        if m:
            t = m.group(1).strip().strip(".").strip()
            if _name_like(t):
                return t
    return None


def _rename_chains(text: str) -> list[list[str]]:
    """Ordered name chains (≥2 names) found on single lines joined by '→'."""
    chains: list[list[str]] = []
    for line in text.splitlines():
        if "→" not in line:
            continue
        terms = [t for t in (_first_term(seg) for seg in line.split("→")) if t]
        if len(terms) >= 2:
            chains.append(terms)
    return chains


def _supersession_leaks(pages, page_text) -> list[str]:
    """WARN-level: a retired renamed noun still asserted as current on a SUMMARY
    surface (index.md / glossary.md) without its successor term on the same line.

    Scope is deliberately narrow — the catalog and glossary are the high-risk drift
    surfaces (their one-liners are hand-copied terminal facts), whereas detail/history
    pages legitimately narrate each era in that era's vocabulary, so scanning them
    floods the report with false positives. A correctly-maintained summary carries
    the full ``A → B → C`` chain (skipped here), so only a *stale* one fires."""
    # Learn the rename graph from every chain in the wiki: adjacency over ALL names
    # (so successors are transitive across chains), plus the set of *flaggable*
    # retired nouns we actually scan for.
    adj: dict[str, set[str]] = {}
    retired: set[str] = set()
    for p in pages:
        for chain in _rename_chains(page_text[p]):
            for i in range(len(chain) - 1):
                adj.setdefault(chain[i], set()).add(chain[i + 1])
                if _FLAGGABLE_NOUN_RE.search(chain[i]):
                    retired.add(chain[i])
    if not retired:
        return []

    def _successors(term: str) -> set[str]:
        """All names transitively reachable from a retired term across chains."""
        seen, stack = set(), list(adj.get(term, ()))
        while stack:
            n = stack.pop()
            if n not in seen:
                seen.add(n)
                stack.extend(adj.get(n, ()))
        return seen

    # term -> (all successors, newest=longest sink). A line mentioning the term
    # alongside ANY successor is documented context; the sink is the current name.
    later_names = {t: _successors(t) for t in retired}

    warns: list[str] = []
    for p in pages:
        if _slug(p) not in ("index", "glossary"):
            continue
        in_superseded = False
        for ln, line in enumerate(page_text[p].splitlines(), 1):
            if line.startswith("## "):
                in_superseded = line.strip().lower() == "## superseded"
            if in_superseded or "→" in line or _ERA_QUALIFIER_RE.search(line):
                continue
            for old_term, laters in later_names.items():
                if old_term in line and not any(nm in line for nm in laters):
                    sinks = [n for n in laters if not adj.get(n)]
                    newest = max(sinks or laters, key=len) if laters else "?"
                    warns.append(
                        f'supersession-leak: {p}:{ln} uses retired "{old_term}" '
                        f'as current (renamed to "{newest}")')
    return warns


def _content_pages() -> list[Path]:
    return sorted(p for p in WIKI.rglob("*.md"))


def _slug(p: Path) -> str:
    return p.stem


def _wikilink_targets(text: str) -> set[str]:
    """Slugs referenced by [[link]] / [[link|alias]] / [[link#heading]]."""
    out = set()
    for raw in _WIKILINK_RE.findall(text):
        target = raw.split("|")[0].split("#")[0].strip()
        if target:
            out.add(Path(target).stem)
    return out


def lint(wiki_dir: Path) -> list[str]:
    """Run all mechanical checks against wiki_dir; return the list of issue strings."""
    pages = sorted(p for p in wiki_dir.rglob("*.md"))
    issues: list[str] = []

    # slug -> list of paths (to detect duplicates)
    slug_paths: dict[str, list[Path]] = {}
    inbound: dict[str, int] = {}
    page_text: dict[Path, str] = {}

    for p in pages:
        slug = _slug(p)
        slug_paths.setdefault(slug, []).append(p)
        inbound.setdefault(slug, 0)
        page_text[p] = p.read_text(encoding="utf-8")

    all_slugs = set(slug_paths)

    # Pass 2: links, inbound counts, frontmatter.
    for p in pages:
        slug = _slug(p)
        text = page_text[p]
        for target in _wikilink_targets(text):
            if target == slug:
                continue  # self-link doesn't save a page from orphanhood
            if target in inbound:
                inbound[target] += 1
            if target not in all_slugs:
                issues.append(f"broken-link: {p} -> [[{target}]] (no such page)")

        # References / body markdown links: enforce the raw/imports + live-Jira convention.
        for target in _MDLINK_RE.findall(text):
            target = target.split()[0].split("#")[0].strip()  # drop title/anchor
            if target.startswith(("http://", "https://", "mailto:")):
                continue  # external (e.g. live Jira) — not checkable here
            if "jira-exports/" in target:
                issues.append(f"stale-export-link: {p} -> {target} (link raw/imports/jira/, not the raw export)")
            elif "raw/imports/" in target and target.endswith(".md"):
                if not (p.parent / target).resolve().is_file():
                    issues.append(f"missing-source-link: {p} -> {target} (no such import)")
            elif "digests/" in target and target.endswith(".md"):
                issues.append(f"stale-digest-link: {p} -> {target} (digests/ retired; link raw/imports/jira/)")

        if slug not in ENTRY_PAGES:
            m = _FRONTMATTER_RE.match(text)
            if not m:
                issues.append(f"frontmatter-missing: {p}")
            else:
                fm = m.group(1)
                for key in REQUIRED_FRONTMATTER:
                    if not re.search(rf"^{key}\s*:", fm, re.MULTILINE):
                        issues.append(f"frontmatter-key-missing: {p} ({key})")

    # Duplicate slugs.
    for slug, paths in sorted(slug_paths.items()):
        if len(paths) > 1:
            joined = ", ".join(str(x) for x in paths)
            issues.append(f"duplicate-slug: {slug} -> {joined}")

    # Orphans (content pages with no inbound wikilink).
    for slug, paths in sorted(slug_paths.items()):
        if slug in ENTRY_PAGES:
            continue
        if inbound.get(slug, 0) == 0:
            issues.append(f"orphan: {paths[0]} (no inbound [[links]])")

    # index.md drift.
    index = wiki_dir / "index.md"
    if not index.is_file():
        issues.append("index-missing: wiki/index.md not found")
    else:
        index_text = page_text.get(index, index.read_text(encoding="utf-8"))
        for slug, paths in sorted(slug_paths.items()):
            if slug in ENTRY_PAGES:
                continue
            # Listed if referenced by slug anywhere in index.md (link or wikilink).
            if not re.search(rf"\b{re.escape(slug)}\b", index_text):
                issues.append(f"index-drift: {paths[0]} not referenced in index.md")

    return issues


def main() -> int:
    if not WIKI.is_dir():
        print("ERROR: wiki/ not found (run from repo root)", file=sys.stderr)
        return 2

    issues = lint(WIKI)

    # Advisory (warning-only) rename-leakage check — never affects exit code.
    pages = _content_pages()
    page_text = {p: p.read_text(encoding="utf-8") for p in pages}
    warns: list[str] = []
    if "--no-rename-check" not in sys.argv:
        warns = _supersession_leaks(pages, page_text)

    # Report.
    if not issues:
        print(f"CLEAN | {len(pages)} pages, no mechanical issues")
    else:
        by_kind: dict[str, int] = {}
        for line in issues:
            by_kind[line.split(":", 1)[0]] = by_kind.get(line.split(":", 1)[0], 0) + 1
        print(f"ISSUES | {len(issues)} across {len(pages)} pages: " +
              ", ".join(f"{k}={v}" for k, v in sorted(by_kind.items())))
        for line in issues:
            print(f"  {line}")

    if warns:
        print(f"WARN | {len(warns)} rename-leak warning(s) (advisory, exit unaffected):")
        for line in warns:
            print(f"  {line}")

    return 1 if issues else 0


if __name__ == "__main__":
    sys.exit(main())
