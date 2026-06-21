# Wiki Lint Tiers (delta + full, one engine) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the whole-wiki-sampled semantic lint with two exhaustive scopes — **delta** (changed-since-last-lint + 1-hop neighbors) and **full** (whole wiki, sharded) — sharing one engine and one prompt, with scope resolution done deterministically in Python.

**Architecture:** A new pure-stdlib module `scripts/lint_scope.py` computes the page set for each scope (parse `log.md` for the watermark, expand 1-hop `[[wikilink]]` neighbors, partition pages into line-budgeted shards). The skills (`wiki-lint`, `wiki-ingest`) call it, then hand the page list to the existing canonical lint prompt (moved to `prompts/lint-prompt.md`, gaining a `## Scope` slot). `wiki-deeplint` is folded into `/wiki-lint --full`. No new state file; the log is the watermark.

**Tech Stack:** Python 3 (stdlib only), pytest, Markdown skills/prompts, YAML config.

## Global Constraints

- Python scripts are **pure stdlib** (no new dependencies). Verbatim from spec §2/§4.
- Tests run with `pytest` from the repo root; `scripts/` is importable as top-level modules (see `tests/conftest.py`).
- The watermark keys on **append position** in `log.md` (the last line matching `^## \[…\] lint`), **never** on the date string. (spec §3.4, §5)
- Neighbor horizon is **1-hop** (inbound + outbound `[[wikilinks]]`). (spec §3.3)
- Default shard budget **3,500 lines**; default gate cadence **N=20** batches. (spec §3.3, §3.5)
- The 7 semantic passes are **not** duplicated or modified — one shared prompt, parameterized by scope. (spec §3.2)
- Entry pages excluded from sharding/neighbor-page-set are exactly `{"index", "log", "overview"}` (reuse `lint_wiki.ENTRY_PAGES`).
- Commit after every task.

---

### Task 1: Scope resolver — `changed_since_last_lint`

**Files:**
- Create: `scripts/lint_scope.py`
- Test: `tests/test_lint_scope.py`

**Interfaces:**
- Consumes: `lint_wiki` module (for `ENTRY_PAGES`, `_slug`, `_wikilink_targets` in later tasks).
- Produces: `changed_since_last_lint(log_text: str) -> list[str]` — page slugs from `pages:` fields of event lines appended *after* the last deliberate `lint` line, in first-seen order, de-duplicated.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_lint_scope.py
import lint_scope


def test_changed_unions_synth_pages_after_last_lint():
    log = "\n".join([
        "## [2026-06-01] synth | A-1 | pages: alpha, beta",
        "## [2026-06-02] lint | manual | scope: 2 pages | clean",
        "## [2026-06-03] synth | A-2 | pages: gamma, beta",
        "## [2026-06-03] synth | A-3 | pages: delta",
    ])
    assert lint_scope.changed_since_last_lint(log) == ["gamma", "beta", "delta"]


def test_changed_ignores_query_lines_and_pre_watermark():
    log = "\n".join([
        "## [2026-06-03] synth | A-2 | pages: gamma",
        '## [2026-06-03] query | "q?" | pages read: alpha, beta',
        "## [2026-06-04] lint --full | manual | scope: 59 pages | clean",
        "## [2026-06-05] synth | A-9 | pages: omega | findings: stuff",
    ])
    assert lint_scope.changed_since_last_lint(log) == ["omega"]


def test_changed_whole_log_when_no_lint_yet():
    log = "## [2026-06-01] synth | A-1 | pages: alpha, beta"
    assert lint_scope.changed_since_last_lint(log) == ["alpha", "beta"]


def test_changed_synth_prefixed_line_does_not_reset_watermark():
    log = "\n".join([
        "## [2026-06-02] lint | manual | clean",
        "## [2026-06-03] synth | A-2 | pages: gamma",
        "## [2026-06-03] synth-lint | auto | pages: gamma",
        "## [2026-06-04] synth | A-3 | pages: delta",
    ])
    assert lint_scope.changed_since_last_lint(log) == ["gamma", "delta"]
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_lint_scope.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'lint_scope'`

- [ ] **Step 3: Write minimal implementation**

```python
# scripts/lint_scope.py
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
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_lint_scope.py -v`
Expected: PASS (4 tests)

- [ ] **Step 5: Commit**

```bash
git add scripts/lint_scope.py tests/test_lint_scope.py
git commit -m "feat(lint): scope resolver — changed-since-last-lint watermark"
```

---

### Task 2: Scope resolver — `one_hop_neighbors`

**Files:**
- Modify: `scripts/lint_scope.py`
- Test: `tests/test_lint_scope.py`

**Interfaces:**
- Consumes: `lint_wiki._slug`, `lint_wiki._wikilink_targets`.
- Produces: `one_hop_neighbors(changed: list[str] | set[str], wiki_dir: Path) -> list[str]` — sorted slugs = `changed` plus every page they link to (outbound) and every page that links to them (inbound), restricted to slugs that are real pages.

- [ ] **Step 1: Write the failing test**

```python
# add to tests/test_lint_scope.py
from pathlib import Path


def _wiki(tmp_path, files):
    wiki = tmp_path / "wiki"
    for rel, text in files.items():
        p = wiki / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(text, encoding="utf-8")
    return wiki


def test_neighbors_include_inbound_and_outbound(tmp_path):
    wiki = _wiki(tmp_path, {
        "concepts/alpha.md": "links to [[beta]]",   # alpha -> beta (outbound)
        "concepts/beta.md": "plain",
        "concepts/gamma.md": "see [[alpha]]",        # gamma -> alpha (inbound)
        "concepts/delta.md": "unrelated",
    })
    assert lint_scope.one_hop_neighbors(["alpha"], wiki) == ["alpha", "beta", "gamma"]


def test_neighbors_empty_when_no_changes(tmp_path):
    wiki = _wiki(tmp_path, {"concepts/alpha.md": "[[beta]]", "concepts/beta.md": "x"})
    assert lint_scope.one_hop_neighbors([], wiki) == []


def test_neighbors_drop_broken_link_targets(tmp_path):
    wiki = _wiki(tmp_path, {"concepts/alpha.md": "[[nonexistent]]"})
    assert lint_scope.one_hop_neighbors(["alpha"], wiki) == ["alpha"]
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_lint_scope.py -k neighbors -v`
Expected: FAIL with `AttributeError: module 'lint_scope' has no attribute 'one_hop_neighbors'`

- [ ] **Step 3: Write minimal implementation**

```python
# add to scripts/lint_scope.py
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
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_lint_scope.py -k neighbors -v`
Expected: PASS (3 tests)

- [ ] **Step 5: Commit**

```bash
git add scripts/lint_scope.py tests/test_lint_scope.py
git commit -m "feat(lint): scope resolver — 1-hop neighbor expansion"
```

---

### Task 3: Scope resolver — `shard_pages`

**Files:**
- Modify: `scripts/lint_scope.py`
- Test: `tests/test_lint_scope.py`

**Interfaces:**
- Consumes: `lint_wiki._slug`, `lint_wiki.ENTRY_PAGES`.
- Produces: `shard_pages(wiki_dir: Path, budget_lines: int = 3500) -> list[list[str]]` — content pages (excluding `ENTRY_PAGES`) partitioned folder-by-folder, greedily packed so each shard's total line count stays within `budget_lines` (a single oversized page becomes its own shard).

- [ ] **Step 1: Write the failing test**

```python
# add to tests/test_lint_scope.py
def test_shard_splits_oversized_folder_by_line_budget(tmp_path):
    big = ("line\n" * 100)          # 100 lines
    wiki = _wiki(tmp_path, {
        "concepts/a.md": big, "concepts/b.md": big, "concepts/c.md": big,
        "entities/x.md": "small\n",
        "index.md": "entry", "log.md": "entry", "overview.md": "entry",
    })
    shards = lint_scope.shard_pages(wiki, budget_lines=150)
    assert ["a"] in shards and ["b"] in shards and ["c"] in shards   # each alone
    assert ["x"] in shards                                            # small folder, own shard
    flat = [slug for s in shards for slug in s]
    assert "index" not in flat and "log" not in flat and "overview" not in flat


def test_shard_packs_small_pages_together(tmp_path):
    wiki = _wiki(tmp_path, {
        "concepts/a.md": "x\n", "concepts/b.md": "y\n", "concepts/c.md": "z\n",
    })
    shards = lint_scope.shard_pages(wiki, budget_lines=150)
    assert shards == [["a", "b", "c"]]                               # all fit in one shard
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_lint_scope.py -k shard -v`
Expected: FAIL with `AttributeError: module 'lint_scope' has no attribute 'shard_pages'`

- [ ] **Step 3: Write minimal implementation**

```python
# add to scripts/lint_scope.py
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
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_lint_scope.py -k shard -v`
Expected: PASS (2 tests)

- [ ] **Step 5: Commit**

```bash
git add scripts/lint_scope.py tests/test_lint_scope.py
git commit -m "feat(lint): scope resolver — folder-aware shard partition"
```

---

### Task 4: Scope resolver CLI (`main`)

**Files:**
- Modify: `scripts/lint_scope.py`
- Test: `tests/test_lint_scope.py`

**Interfaces:**
- Consumes: `config.wiki_root()`, and the three functions above.
- Produces: command-line entry the skills invoke:
  - `python scripts/lint_scope.py delta` → prints the delta page set (neighbor-expanded), one slug per line; nothing if no changes.
  - `python scripts/lint_scope.py full [budget_lines]` → prints one shard per line, slugs comma-separated.

- [ ] **Step 1: Write the failing test**

```python
# add to tests/test_lint_scope.py
import textwrap


def _wiki_repo(tmp_path, files, log=""):
    """Build a wiki repo (config + wiki/) and point $WIKI_CONFIG at it."""
    (tmp_path / "wiki.config.yaml").write_text(textwrap.dedent("""
        project: {key: CDS2ASV, name: "T", config_dir: ./config}
        jira: {base_url: http://x, jql: "project = CDS2ASV"}
        sources: []
        lint: {flaggable_nouns: [], brand_nouns: [], era_terms: []}
    """), encoding="utf-8")
    wiki = tmp_path / "wiki"
    wiki.mkdir()
    (wiki / "log.md").write_text(log, encoding="utf-8")
    for rel, text in files.items():
        p = wiki / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(text, encoding="utf-8")
    return tmp_path


def test_main_delta_prints_neighbor_expanded_set(tmp_path, monkeypatch, capsys):
    repo = _wiki_repo(
        tmp_path,
        {"concepts/alpha.md": "[[beta]]", "concepts/beta.md": "x", "concepts/gamma.md": "[[alpha]]"},
        log="## [2026-06-01] lint | manual | clean\n## [2026-06-02] synth | A | pages: alpha\n",
    )
    monkeypatch.setenv("WIKI_CONFIG", str(repo / "wiki.config.yaml"))
    assert lint_scope.main(["delta"]) == 0
    out = capsys.readouterr().out.split()
    assert out == ["alpha", "beta", "gamma"]


def test_main_full_prints_one_shard_per_line(tmp_path, monkeypatch, capsys):
    repo = _wiki_repo(tmp_path, {"concepts/a.md": "x\n", "entities/b.md": "y\n"})
    monkeypatch.setenv("WIKI_CONFIG", str(repo / "wiki.config.yaml"))
    assert lint_scope.main(["full"]) == 0
    lines = capsys.readouterr().out.splitlines()
    assert lines == ["a", "b"]            # one page per folder -> one shard per folder
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_lint_scope.py -k main -v`
Expected: FAIL with `AttributeError: module 'lint_scope' has no attribute 'main'`

- [ ] **Step 3: Write minimal implementation**

```python
# add to scripts/lint_scope.py
def main(argv=None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)
    if not args or args[0] not in ("delta", "full"):
        print("usage: lint_scope.py delta|full [budget_lines]", file=sys.stderr)
        return 2
    wiki = config.wiki_root() / "wiki"
    if args[0] == "delta":
        log = wiki / "log.md"
        log_text = log.read_text(encoding="utf-8") if log.is_file() else ""
        changed = changed_since_last_lint(log_text)
        for slug in one_hop_neighbors(changed, wiki):
            print(slug)
        return 0
    budget = int(args[1]) if len(args) > 1 else 3500
    for shard in shard_pages(wiki, budget):
        print(",".join(shard))
    return 0


if __name__ == "__main__":
    sys.exit(main())
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_lint_scope.py -v`
Expected: PASS (all `test_lint_scope.py` tests)

- [ ] **Step 5: Commit**

```bash
git add scripts/lint_scope.py tests/test_lint_scope.py
git commit -m "feat(lint): scope resolver CLI (delta|full)"
```

---

### Task 5: Move canonical prompt to `prompts/` and add the `## Scope` slot

**Files:**
- Move: `skills/wiki-lint/lint-prompt.md` → `prompts/lint-prompt.md`
- Modify: `prompts/lint-prompt.md` (add Scope slot)

**Interfaces:**
- Produces: `${CLAUDE_PLUGIN_ROOT}/prompts/lint-prompt.md` — the single shared prompt, referenced by both skills in Tasks 6 and 7.

- [ ] **Step 1: Move the file (preserve history)**

```bash
mkdir -p prompts
git mv skills/wiki-lint/lint-prompt.md prompts/lint-prompt.md
```

- [ ] **Step 2: Add the Scope slot**

Insert the following block in `prompts/lint-prompt.md` immediately after the
`Mechanical output:` fenced block and before the `First read …` paragraph:

```markdown
## Scope

Audit exactly the page set named here — exhaustively, not by sampling:

- **delta** — Audit ONLY these pages (changed since the last lint) and the listed
  1-hop neighbors: `<page list>`. Evaluate the global passes (summary-page
  consistency, concept-split) *as they bear on these pages* — i.e. check whether
  these changes affect `index.md` / `overview.md` / `glossary.md`, not a full
  summary-vs-everything reconciliation. Append a `lint | <auto|manual>` line to
  `wiki/log.md`.
- **full, shard `<i>` of `<n>`** — Audit ONLY these pages: `<shard list>`. Return
  your findings to the synthesis step (do not write `log.md`); a final synthesis
  agent reconciles cross-shard contradictions, checks the summary pages against
  the whole set, and appends one `lint --full | manual` line to `wiki/log.md`.
```

- [ ] **Step 3: Verify the move and slot**

Run: `test -f prompts/lint-prompt.md && ! test -f skills/wiki-lint/lint-prompt.md && grep -c "## Scope" prompts/lint-prompt.md`
Expected: prints `1`

- [ ] **Step 4: Commit**

```bash
git add -A prompts/ skills/wiki-lint/
git commit -m "refactor(lint): move canonical prompt to prompts/, add Scope slot"
```

---

### Task 6: Update `wiki-lint` SKILL — delta default, `--full`, scope resolver

**Files:**
- Modify: `skills/wiki-lint/SKILL.md`

**Interfaces:**
- Consumes: `scripts/lint_scope.py` (Task 4), `prompts/lint-prompt.md` (Task 5).

- [ ] **Step 1: Rewrite the semantic section**

Replace the body of `skills/wiki-lint/SKILL.md` section "## 2. Semantic (Opus subagent)"
so it reads (keep section 1 Mechanical unchanged except its arg note):

```markdown
## 2. Semantic (Opus subagent) — delta (default) or `--full`

First refresh the search index: `qmd update && qmd embed`. If `qmd` is missing or the
refresh fails, continue and note `qmd-unavailable`; never block the lint.

Resolve the page set deterministically, then spawn the Opus engine over it. Only run when
no synth/extract subagent is writing to `wiki/`.

**Delta (default — `/wiki-lint`).** Audit what changed since the last deliberate lint:
1. `python "${CLAUDE_PLUGIN_ROOT}/scripts/lint_scope.py" delta` → the page set (neighbor-
   expanded), one slug per line. If empty, report `CLEAN | nothing changed since last lint`
   and stop — do not spawn a subagent.
2. Spawn one Opus subagent (`subagent_type: general-purpose`, `model: opus`) with
   `${CLAUDE_PLUGIN_ROOT}/prompts/lint-prompt.md`, filling the `## Scope` **delta** option
   with that page list and the mechanical output. It appends a `lint | manual` line.

**Full (`/wiki-lint --full`).** Exhaustive whole-wiki audit:
1. `python "${CLAUDE_PLUGIN_ROOT}/scripts/lint_scope.py" full` → one shard (comma-separated
   slugs) per line.
2. Spawn one Opus subagent per shard with the prompt's `## Scope` **full, shard i of n**
   option; each returns findings (does not write `log.md`).
3. Spawn one final Opus synthesis subagent with all shard findings + `index.md`,
   `overview.md`, `glossary.md`: reconcile cross-shard contradictions, check the summary
   pages against the whole set, apply safe fixes, and append one `lint --full | manual` line.

Report the subagent return verbatim. On `BLOCKED`, surface and do not guess.
```

- [ ] **Step 2: Update the intro line for the new arg**

Change the opening line of the skill from the `mechanical`-only note to:

```markdown
Tiers below. Args: `mechanical` (deterministic only), `--full` (exhaustive whole-wiki
semantic), or none (delta — changed since last lint + neighbors). Mechanical always runs first.
```

- [ ] **Step 3: Verify references resolve**

Run: `grep -n "lint_scope.py\|prompts/lint-prompt.md\|--full\|lint | manual\|lint --full" skills/wiki-lint/SKILL.md`
Expected: matches for the scope-resolver call, the prompt path, `--full`, and both log-line forms.

- [ ] **Step 4: Commit**

```bash
git add skills/wiki-lint/SKILL.md
git commit -m "feat(wiki-lint): delta default + --full, deterministic scope resolution"
```

---

### Task 7: Update `wiki-ingest` SKILL — gate runs delta every N + end

**Files:**
- Modify: `skills/wiki-ingest/SKILL.md:134-138` (the "Lint gate" block)

**Interfaces:**
- Consumes: `scripts/lint_scope.py`, `prompts/lint-prompt.md`.

- [ ] **Step 1: Replace the lint-gate block**

Replace the current step 3 "Lint gate" block (lines ~134-138) with:

```markdown
3. **Lint gate (delta)** — after every `LINT_EVERY` synthesized (default 20) and once at
   end of run, only when no synth subagent is running:
   a. `python "${CLAUDE_PLUGIN_ROOT}/scripts/lint_wiki.py"`.
   b. `python "${CLAUDE_PLUGIN_ROOT}/scripts/lint_scope.py" delta` → the changed-since-last-
      lint page set (neighbor-expanded). If empty, skip the subagent.
   c. Spawn one Opus subagent (`model: opus`) with
      `${CLAUDE_PLUGIN_ROOT}/prompts/lint-prompt.md`, filling the `## Scope` **delta** option
      with that page list and the mechanical output. It appends a `lint | auto` line. Wait.
      `CLEAN`/`FIXED` → continue; `BLOCKED` → STOP.
```

- [ ] **Step 2: Verify**

Run: `grep -n "lint_scope.py\|prompts/lint-prompt.md\|lint | auto\|Lint gate (delta)" skills/wiki-ingest/SKILL.md`
Expected: matches for all four.
Run: `! grep -n "skills/wiki-lint/lint-prompt.md" skills/wiki-ingest/SKILL.md`
Expected: no match (old path gone).

- [ ] **Step 3: Commit**

```bash
git add skills/wiki-ingest/SKILL.md
git commit -m "feat(wiki-ingest): synth lint gate runs delta (every N + end)"
```

---

### Task 8: Update schema `CLAUDE.md.tmpl` — §5 policy, §6 log vocabulary

**Files:**
- Modify: `schema/CLAUDE.md.tmpl` (§5 Lint bullet ~line 204-208; §6 log section ~line 230-231)

**Interfaces:** none (documentation/schema).

- [ ] **Step 1: Replace the §5 Lint bullet**

Replace the existing `- **Lint — `/lint`**:` bullet with:

```markdown
- **Lint — `/lint`**: *mechanical* (`scripts/lint_wiki.py`, deterministic) plus *semantic*
  (an Opus engine over the canonical `prompts/lint-prompt.md`) in two scopes, each audited
  **exhaustively** over a deterministically-resolved page set (`scripts/lint_scope.py`):
  - **delta** (default; also the synth gate): pages changed since the last lint + their
    1-hop `[[neighbors]]`. The watermark is the last `lint` line in `log.md` (append
    position, not date). Logs `lint | auto` (gate) or `lint | manual`.
  - **full** (`/lint --full`): the whole wiki, sharded so every page is read, with a
    cross-shard synthesis pass. Rare/on-demand. Logs `lint --full | manual`.
  Surface, do not auto-fix, issues needing human judgment.
```

- [ ] **Step 2: Update the §6 log-format example**

Replace the example `## [2026-06-09] lint   | 2 orphans, 1 stale claim flagged` line with:

```markdown
## [2026-06-09] lint | auto   | scope: 14 pages since last lint + neighbors | FIXED 1 broken link
## [2026-06-09] lint --full | manual | scope: 59 pages, 5 shards | CLEAN
```

Add one sentence after the example block:

```markdown
`lint | auto` is a synth-gate delta; `lint | manual` a hand-run delta; `lint --full` a full
audit. All three are the lint watermark (the `auto|manual` field is traceability only).
```

- [ ] **Step 3: Verify**

Run: `grep -n "lint_scope.py\|lint --full\|lint | auto\|1-hop" schema/CLAUDE.md.tmpl`
Expected: matches present.

- [ ] **Step 4: Commit**

```bash
git add schema/CLAUDE.md.tmpl
git commit -m "docs(schema): lint policy delta/full + log vocabulary"
```

---

### Task 9: Update README command table

**Files:**
- Modify: `README.md:81-82` (lint rows) and the ingest/lint refresh note (~line 67)

**Interfaces:** none (documentation).

- [ ] **Step 1: Replace the `/wiki-lint` rows**

Replace the existing `/wiki-lint` and `/wiki-lint mechanical` rows with:

```markdown
| `/wiki-lint` | Delta health check: deterministic checks plus a semantic review of the pages **changed since the last lint** and their direct neighbors. Fast; run it any time. After an ingest run it usually reports nothing new — the signal the wiki is current. |
| `/wiki-lint --full` | Exhaustive whole-wiki audit: shards the wiki so every page is reviewed, with a cross-shard reconciliation pass. Slower; run it rarely — before relying on the wiki for something important, before a release, or periodically. |
| `/wiki-lint mechanical` | Runs only the fast deterministic checks: broken `[[wikilinks]]`, orphan pages, duplicate slugs, index drift, and frontmatter gaps. Use it for a quick structural check, or in a pre-commit or CI step. |
```

- [ ] **Step 2: Adjust the qmd refresh note**

Change the sentence at ~line 67 to:

```markdown
   `/wiki-ingest` refreshes it at the start and end of a run; `/wiki-lint` refreshes it at
   the start of a run.
```

- [ ] **Step 3: Verify**

Run: `grep -n "wiki-lint --full\|changed since the last lint\|cross-shard" README.md`
Expected: matches present.

- [ ] **Step 4: Commit**

```bash
git add README.md
git commit -m "docs(readme): document /wiki-lint delta vs --full"
```

---

### Task 10: Version bump + full verification

**Files:**
- Modify: `.claude-plugin/plugin.json`, `.claude-plugin/marketplace.json`

**Interfaces:** none.

- [ ] **Step 1: Bump both versions in sync**

Set `"version"` from `0.6.0` to `0.7.0` in both `.claude-plugin/plugin.json` and
`.claude-plugin/marketplace.json`.

- [ ] **Step 2: Verify versions and JSON validity**

Run: `grep -h '"version"' .claude-plugin/*.json && python -c "import json; [json.load(open(f)) for f in ['.claude-plugin/plugin.json','.claude-plugin/marketplace.json']]; print('ok')"`
Expected: two `"version": "0.7.0",` lines and `ok`.

- [ ] **Step 3: Run the full test suite**

Run: `python -m pytest tests/ -q`
Expected: all tests pass (previous 149 + the new `test_lint_scope.py` tests).

- [ ] **Step 4: Final reference sanity check**

Run: `grep -rn "skills/wiki-lint/lint-prompt.md" skills/ ; echo "exit $?"`
Expected: no matches (every reference now points at `prompts/lint-prompt.md`).

- [ ] **Step 5: Commit**

```bash
git add .claude-plugin/plugin.json .claude-plugin/marketplace.json
git commit -m "chore: bump to 0.7.0 (wiki lint tiers: delta + full)"
```

---

## Self-Review

**1. Spec coverage:**
- §3.1 one engine / two scopes → Tasks 4, 6 (CLI + skill modes). ✓
- §3.2 single parameterized prompt + neutral location → Task 5. ✓
- §3.3 deterministic scope resolution (log parse, 1-hop neighbors, shard partition) → Tasks 1–3. ✓
- §3.4 watermark + log vocabulary (`lint | auto/manual`, `lint --full`) → Tasks 1, 6, 7, 8. ✓
- §3.5 cadence (every N + end) → Task 7. ✓
- §4 file changes: prompt (5), lint_scope (1–4), wiki-lint (6), wiki-ingest (7), schema (8), README (9), version (10). ✓
- §5 risk "key on append position not date" → Task 1 test `test_changed_synth_prefixed_line_does_not_reset_watermark` + watermark loop keeps last by position. ✓

**2. Placeholder scan:** No TBD/TODO; every code step shows complete code; every doc step shows the exact replacement text. ✓

**3. Type consistency:** `changed_since_last_lint(str) -> list[str]`, `one_hop_neighbors(list|set, Path) -> list[str]`, `shard_pages(Path, int) -> list[list[str]]`, `main(argv) -> int` are used consistently across Tasks 1–4 and referenced by Tasks 6–7 by the same CLI surface (`lint_scope.py delta|full`). ✓
