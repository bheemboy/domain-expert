#!/usr/bin/env python3
"""migrate_okf.py — one-shot mechanical migration of a pre-OKF wiki (CLAUDE.md §4/§6).

Brings an existing wiki up to the OKF v0.1-aligned layout without model help:

  * pages   — backfill `title:` (from the H1) and `description:` (from the page's
              index.md catalog one-liner, falling back to the first prose line
              after the H1). Pages where both fail land on the needs-description
              report — the only step that needs a model afterwards.
  * log.md  — rewrite `## [DATE] op | payload` event headings into OKF date
              groups: `## YYYY-MM-DD` headings, one `- op | payload` bullet per
              event, whole file newest-first. Op names carried verbatim; any
              unrecognized line is kept attached after its preceding event and
              reported, never dropped.
  * index.md — insert the `okf_version: "0.1"` frontmatter block and regenerate
              the catalog region via build_index (markers), preserving all
              hand-written prose above the first category heading.

Idempotent: a second run reports nothing to do and changes no files. Dry-run by
default; `--write` applies. Run from anywhere inside a wiki repo:
``python scripts/migrate_okf.py [--write]``.
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

import yaml

import build_index

_FRONTMATTER_RE = re.compile(r"^---\n(.*?\n)---", re.DOTALL)
_H1_RE = re.compile(r"^# (.+)$", re.MULTILINE)
# Catalog bullet: `- [[link]] — desc` / `- [[link|alias]] — desc`; the separator
# may be an em dash, en dash, or hyphen (live wikis carry all three).
_BULLET_RE = re.compile(r"^-\s*\[\[([^\]|#]+)(?:\|[^\]]*)?\]\]\s*[—–-]\s+(.+)$")
# Legacy log event: `## [YYYY-MM-DD] op | payload`.
_LEGACY_EVENT_RE = re.compile(r"^## \[(\d{4}-\d{2}-\d{2})\]\s*(.+)$")

_LOG_INTRO = (
    "\nReverse-chronological (newest first): one `- <op> | <payload>` bullet per\n"
    "event under its `## YYYY-MM-DD` date heading. New events are prepended under\n"
    "today's heading. Recent events: `head -30 wiki/log.md`.\n"
)


def _yaml_scalar(value: str) -> str:
    """`value` as a single-line YAML scalar: plain when safe, else JSON-quoted
    (JSON strings are valid YAML double-quoted scalars)."""
    try:
        if yaml.safe_load("k: " + value)["k"] == value and "\n" not in value:
            return value
    except Exception:
        pass
    return json.dumps(value, ensure_ascii=False)


def index_descriptions(index_text: str) -> dict[str, str]:
    """slug -> catalog one-liner, parsed from every `- [[link]] — desc` bullet."""
    out: dict[str, str] = {}
    for line in index_text.splitlines():
        m = _BULLET_RE.match(line.strip())
        if m:
            slug = Path(m.group(1).strip()).stem
            out.setdefault(slug, m.group(2).strip())
    return out


def _first_prose_line(body: str) -> str | None:
    """First non-empty, non-heading line after the H1 — the page's one-line
    business definition (schema §4 mandates it directly under the H1)."""
    h1 = _H1_RE.search(body)
    if not h1:
        return None
    for line in body[h1.end():].splitlines():
        s = line.strip()
        if s and not s.startswith("#"):
            return s
    return None


def _migrate_page(text: str, index_desc: str | None) -> tuple[str, bool, bool, bool]:
    """(new_text, added_title, added_description, needs_description)."""
    m = _FRONTMATTER_RE.match(text)
    if not m:
        return text, False, False, False
    fm = m.group(1)
    body = text[m.end():]
    insert: list[str] = []
    added_title = added_desc = needs_desc = False

    if not re.search(r"^title\s*:", fm, re.MULTILINE):
        h1 = _H1_RE.search(body)
        if h1:
            insert.append(f"title: {_yaml_scalar(h1.group(1).strip())}")
            added_title = True
    if not re.search(r"^description\s*:", fm, re.MULTILINE):
        desc = index_desc or _first_prose_line(body)
        if desc:
            insert.append(f"description: {_yaml_scalar(desc)}")
            added_desc = True
        else:
            needs_desc = True

    if insert:
        text = "---\n" + "\n".join(insert) + "\n" + fm + "---" + body
    return text, added_title, added_desc, needs_desc


def _migrate_log(text: str) -> tuple[str | None, list[str]]:
    """(new_text or None when already migrated / nothing to do, unparsed lines)."""
    lines = text.splitlines()
    if not any(_LEGACY_EVENT_RE.match(l) for l in lines):
        return None, []

    # Header = everything before the first event; keep the H1, refresh the intro.
    first_event = next(i for i, l in enumerate(lines) if _LEGACY_EVENT_RE.match(l))
    h1 = next((l for l in lines[:first_event] if l.startswith("# ")), "# Wiki — Log")

    # Events in append (oldest-first) order; stray lines stay with their event.
    events: list[tuple[str, str, list[str]]] = []   # (date, payload, trailing)
    unparsed: list[str] = []
    for line in lines[first_event:]:
        m = _LEGACY_EVENT_RE.match(line)
        if m:
            events.append((m.group(1), m.group(2), []))
        elif line.strip():
            unparsed.append(line)
            if events:
                events[-1][2].append(line)

    out = [h1, _LOG_INTRO.rstrip("\n"), ""]
    prev_date = None
    for date, payload, trailing in reversed(events):
        if date != prev_date:
            out.append(f"## {date}")
            prev_date = date
        out.append(f"- {payload}")
        out.extend(trailing)
    return "\n".join(out).rstrip("\n") + "\n", unparsed


def _migrate_index(text: str, catalog: str) -> str:
    """index.md with an okf_version frontmatter block and a regenerated catalog."""
    if not text.startswith("---\n"):
        h1 = _H1_RE.search(text)
        title = h1.group(1).strip() if h1 else "Wiki — Index"
        text = f'---\nokf_version: "0.1"\ntitle: {_yaml_scalar(title)}\n---\n\n' + text
    elif "okf_version" not in text.split("---")[1]:
        text = text.replace("---\n", '---\nokf_version: "0.1"\n', 1)
    return build_index.apply(text, catalog)


def migrate(repo_root: Path, write: bool) -> dict:
    """Run the migration over repo_root/wiki; return the report dict."""
    wiki = repo_root / "wiki"
    index_path, log_path = wiki / "index.md", wiki / "log.md"
    index_text = index_path.read_text(encoding="utf-8") if index_path.is_file() else ""
    desc_map = index_descriptions(index_text)

    report = {"pages_titled": [], "pages_described": [], "needs_description": [],
              "log_migrated": False, "index_migrated": False, "unparsed": []}
    updates: dict[Path, str] = {}

    for p in sorted(wiki.rglob("*.md")):
        if p.stem in build_index.RESERVED:
            continue
        text = p.read_text(encoding="utf-8")
        new, titled, described, needs = _migrate_page(text, desc_map.get(p.stem))
        rel = p.relative_to(repo_root).as_posix()
        if titled:
            report["pages_titled"].append(rel)
        if described:
            report["pages_described"].append(rel)
        if needs:
            report["needs_description"].append(rel)
        if new != text:
            updates[p] = new

    if log_path.is_file():
        new_log, unparsed = _migrate_log(log_path.read_text(encoding="utf-8"))
        report["unparsed"] = unparsed
        if new_log is not None:
            report["log_migrated"] = True
            updates[log_path] = new_log

    if index_path.is_file():
        catalog = build_index.render_catalog(wiki, texts=updates)
        new_index = _migrate_index(index_text, catalog)
        if new_index != index_text:
            report["index_migrated"] = True
            updates[index_path] = new_index

    if write:
        for p, text in updates.items():
            p.write_text(text, encoding="utf-8")
    return report


def main(argv=None) -> int:
    import config

    args = list(sys.argv[1:] if argv is None else argv)
    if args not in ([], ["--dry-run"], ["--write"]):
        print("usage: migrate_okf.py [--dry-run | --write]", file=sys.stderr)
        return 2
    write = args == ["--write"]
    root = config.wiki_root()
    report = migrate(root, write=write)

    mode = "WROTE" if write else "DRY-RUN"
    print(f"{mode} | +title: {len(report['pages_titled'])} pages, "
          f"+description: {len(report['pages_described'])} pages, "
          f"log: {'migrated' if report['log_migrated'] else 'ok'}, "
          f"index: {'migrated' if report['index_migrated'] else 'ok'}")
    if report["needs_description"]:
        print(f"needs-description | {len(report['needs_description'])} page(s) "
              "need a model-written one-liner:")
        for rel in report["needs_description"]:
            print(f"  {rel}")
    if report["unparsed"]:
        print(f"unparsed | {len(report['unparsed'])} log line(s) kept verbatim "
              "after their preceding event:")
        for line in report["unparsed"]:
            print(f"  {line}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
