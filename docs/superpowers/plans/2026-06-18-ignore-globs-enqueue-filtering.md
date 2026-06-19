# Ignore-Glob Enqueue Filtering Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Stop committing build output / vendored / asset files into the ingest queue by adding gitignore-style `ignore:` glob filtering at enqueue time, so the extract and synth phases only see genuine domain source.

**Architecture:** A new pure matcher module (`scripts/ignore.py`) translates gitignore-ish globs to regexes and partitions repo-relative paths into kept/ignored. `config.ignore_globs()` returns built-in junk defaults unioned with the consumer repo's `ignore:` list. `check_for_changes.py` runs every candidate path (backfill, incremental detection, and `--force` folder expansion) through the matcher *before* `queues.enqueue`, so junk never enters the queue. `queues.py` is untouched — it stays the sole, filtering-free writer of queue state.

**Tech Stack:** Python 3.10+ stdlib only (`re`, `pathlib`), pyyaml (already a dep), pytest. No new dependencies.

## Global Constraints

- Python 3.10+ (codebase uses `X | None` annotations); stdlib + existing deps only — do **not** add `pathspec` or any new dependency.
- Glob matching is over the **repo-relative POSIX path** of a file (e.g. `ac_portal/local_modules/@agilent/common/x.js`), never the absolute path.
- Slash-less convenience is **not** implicit: a pattern matches at any depth only if it starts with `**/`. Document this; the defaults all use `**/` where any-depth is intended.
- `config.py` does not cache — keep accessors re-reading `load()`, matching the existing no-caching contract.
- Tests set `WIKI_CONFIG` and `STATE_DIR` via `monkeypatch` (see `tests/conftest.py` and `tests/test_config.py:_write`); follow that pattern.
- Filtering applies to multi-file enqueue paths (backfill, detection, `--force` *folder* expansion). An explicitly named single file passed to `--force` is **exempt** — explicit intent overrides ignores.
- All paths below are in the source repo `/home/surehman/projects/personal/domain-expert`. The installed `0.2.0` cache is a copy; do not edit it.

---

## File Structure

- **Create** `scripts/ignore.py` — pure glob→regex translation + `partition()`. One responsibility: path matching. No config/IO.
- **Create** `tests/test_ignore.py` — unit tests for the matcher.
- **Modify** `scripts/config.py` — add `_IGNORE_DEFAULTS` + `ignore_globs()`.
- **Modify** `tests/test_config.py` — tests for `ignore_globs()` defaults + merge.
- **Modify** `scripts/check_for_changes.py` — filter in `_backfill_identities`, `scan_git_candidates`, `_expand_identities`; report ignored counts in dry-run.
- **Modify** `tests/test_change_to_queue.py` — tests that ignored paths are not enqueued and dry-run reports them.
- **Modify** `skills/wiki-init/templates/wiki.config.yaml.tmpl` — document the `ignore:` block (commented, mirroring `synth_tuning`).
- **Modify** `skills/wiki-queue/SKILL.md` — one line noting detection/backfill respect `ignore:`.
- **Modify** `.claude-plugin/plugin.json` — version 0.2.0 → 0.3.0.

---

### Task 1: Glob matcher module

**Files:**
- Create: `scripts/ignore.py`
- Test: `tests/test_ignore.py`

**Interfaces:**
- Consumes: nothing (pure stdlib).
- Produces:
  - `compile_glob(glob: str) -> re.Pattern` — full-match regex over a repo-relative POSIX path.
  - `first_match(rel_path: str, globs: Iterable[str]) -> str | None` — the first glob that matches `rel_path`, else `None`.
  - `partition(rel_paths: Iterable[str], globs: Iterable[str]) -> tuple[list[str], dict[str, int]]` — `(kept, ignored_by_rule)` where `kept` preserves input order and `ignored_by_rule` maps each matching glob to its first-match count.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_ignore.py
import ignore


def test_double_star_prefix_matches_any_depth():
    assert ignore.first_match("a/b/c.min.js", ["**/*.min.js"]) == "**/*.min.js"
    assert ignore.first_match("c.min.js", ["**/*.min.js"]) == "**/*.min.js"


def test_single_star_does_not_cross_slash():
    # *.js (no **/) only matches at the root, one segment
    assert ignore.first_match("x.js", ["*.js"]) == "*.js"
    assert ignore.first_match("a/x.js", ["*.js"]) is None


def test_subtree_glob_matches_everything_under_dir():
    g = "ac_portal/local_modules/**"
    assert ignore.first_match("ac_portal/local_modules/@agilent/common/x.js", [g]) == g
    assert ignore.first_match("ac_portal/src/app/main.ts", [g]) is None


def test_question_mark_matches_one_non_slash_char():
    assert ignore.first_match("ab.ts", ["a?.ts"]) == "a?.ts"
    assert ignore.first_match("a/b.ts", ["a?.ts"]) is None


def test_no_match_returns_none():
    assert ignore.first_match("ac_server/model/user.py", ["**/*.min.js", "**/*.svg"]) is None


def test_partition_keeps_order_and_tallies_by_rule():
    paths = ["a.py", "b.min.js", "c.svg", "d.py", "e.min.js"]
    globs = ["**/*.min.js", "**/*.svg"]
    kept, ignored = ignore.partition(paths, globs)
    assert kept == ["a.py", "d.py"]
    assert ignored == {"**/*.min.js": 2, "**/*.svg": 1}


def test_first_match_is_first_glob_in_order():
    # a path matching two globs is attributed to the first listed
    kept, ignored = ignore.partition(["x.css"], ["**/*.css", "**/*.css"])
    assert kept == []
    assert ignored == {"**/*.css": 1}
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_ignore.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'ignore'`

- [ ] **Step 3: Write minimal implementation**

```python
# scripts/ignore.py
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
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_ignore.py -v`
Expected: PASS (7 tests)

- [ ] **Step 5: Commit**

```bash
git add scripts/ignore.py tests/test_ignore.py
git commit -m "feat(ignore): gitignore-style glob matcher for enqueue filtering"
```

---

### Task 2: `config.ignore_globs()` with built-in defaults

**Files:**
- Modify: `scripts/config.py` (add after `synth_tuning`, ~line 106)
- Test: `tests/test_config.py` (add tests after `test_synth_tuning_override_merges_per_field`)

**Interfaces:**
- Consumes: `config.load()`.
- Produces: `config.ignore_globs() -> list[str]` — `_IGNORE_DEFAULTS` followed by the consumer's `ignore:` list (a YAML list of strings), de-duplicated, order preserved (defaults first).

- [ ] **Step 1: Write the failing test**

```python
# tests/test_config.py  (append)
def test_ignore_globs_defaults_when_absent(tmp_path, monkeypatch):
    _write(tmp_path, monkeypatch)  # config has no ignore: block
    globs = config.ignore_globs()
    assert "**/*.min.js" in globs
    assert "**/node_modules/**" in globs
    assert "**/*.svg" in globs
    # no user entries means just the baked defaults
    assert globs == config._IGNORE_DEFAULTS


def _write_with_ignore(tmp_path, monkeypatch):
    cfg = tmp_path / "wiki.config.yaml"
    cfg.write_text(textwrap.dedent("""
        project:
          key: TESTPROJ
          name: "Test Project"
          config_dir: ~/.config/testproj-wiki
        jira:
          base_url: https://example.atlassian.net
          jql: |
            project = TESTPROJ
        ignore:
          - ac_portal/local_modules/**
          - ac_ops/terraform/**
          - "**/*.min.js"
    """))
    monkeypatch.setenv("WIKI_CONFIG", str(cfg))


def test_ignore_globs_appends_user_entries_and_dedups(tmp_path, monkeypatch):
    _write_with_ignore(tmp_path, monkeypatch)
    globs = config.ignore_globs()
    # defaults still present
    assert "**/node_modules/**" in globs
    # user subtrees appended after defaults
    assert "ac_portal/local_modules/**" in globs
    assert "ac_ops/terraform/**" in globs
    # a user entry duplicating a default appears once, kept at its default position
    assert globs.count("**/*.min.js") == 1
    # defaults come before user-only entries
    assert globs.index("**/node_modules/**") < globs.index("ac_portal/local_modules/**")
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_config.py -k ignore_globs -v`
Expected: FAIL with `AttributeError: module 'config' has no attribute 'ignore_globs'`

- [ ] **Step 3: Write minimal implementation**

```python
# scripts/config.py  (append after synth_tuning)

# Built-in ignore globs: universally junk for a domain wiki — vendored trees,
# build/minified output, generated TS lib artifacts, lockfiles, binary assets,
# styling, and certs. Consumer repos extend these via an `ignore:` list (e.g. a
# committed compiled lib like `ac_portal/local_modules/**`). Matched over the
# repo-relative POSIX path; see ignore.py for semantics.
_IGNORE_DEFAULTS = [
    "**/node_modules/**",
    "**/vendor/**",
    "**/*.min.js",
    "**/*.min.css",
    "**/*.map",
    "**/*.bundle.js",
    "**/*.d.ts",
    "**/*.metadata.json",
    "**/*.lock",
    "**/package-lock.json",
    "**/yarn.lock",
    "**/pnpm-lock.yaml",
    "**/poetry.lock",
    "**/*.svg", "**/*.png", "**/*.jpg", "**/*.jpeg", "**/*.gif", "**/*.ico",
    "**/*.ttf", "**/*.otf", "**/*.woff", "**/*.woff2", "**/*.eot",
    "**/*.wav", "**/*.mp3", "**/*.mp4",
    "**/*.scss", "**/*.css", "**/*.less", "**/*.sass",
    "**/*.pem",
]


def ignore_globs() -> list[str]:
    """Enqueue-time ignore globs: baked defaults (_IGNORE_DEFAULTS) followed by the
    consumer repo's `ignore:` list, de-duplicated with defaults kept first. A config
    with no `ignore:` block reproduces just the defaults."""
    user = load().get("ignore") or []
    seen: set[str] = set()
    out: list[str] = []
    for g in [*_IGNORE_DEFAULTS, *user]:
        if g not in seen:
            seen.add(g)
            out.append(g)
    return out
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_config.py -k ignore_globs -v`
Expected: PASS (2 tests)

- [ ] **Step 5: Commit**

```bash
git add scripts/config.py tests/test_config.py
git commit -m "feat(config): ignore_globs() — built-in junk defaults + user ignore: list"
```

---

### Task 3: Filter backfill enqueue

**Files:**
- Modify: `scripts/check_for_changes.py` (`_backfill_identities`, ~lines 189-202; imports at top)
- Test: `tests/test_change_to_queue.py` (append)

**Interfaces:**
- Consumes: `config.ignore_globs()`, `ignore.partition`, `git_changes.tracked_files`.
- Produces: `_backfill_identities(args) -> tuple[list[str], dict[str, int]]` — `(kept_absolute_paths, ignored_by_rule)`. (Return type changes from `list[str]` to a tuple; Task 6 updates the caller.)

- [ ] **Step 1: Write the failing test**

```python
# tests/test_change_to_queue.py  (append; reuses the module's _cfg helper)
def test_backfill_filters_ignored_tracked_files(tmp_path, monkeypatch):
    repo = tmp_path / "asv"
    (repo / ".git").mkdir(parents=True)
    _cfg(tmp_path, monkeypatch, repos=[str(repo)])

    import importlib, check_for_changes, git_changes
    importlib.reload(check_for_changes)

    tracked = [
        "src/app/user.py",
        "local_modules/@agilent/common/bundles/x.umd.min.js",
        "assets/logo.svg",
        "src/app/billing.ts",
    ]
    monkeypatch.setattr(git_changes, "tracked_files", lambda _repo: tracked)
    monkeypatch.setattr(check_for_changes.git_changes, "tracked_files", lambda _repo: tracked)

    kept, ignored = check_for_changes._backfill_identities([str(repo)])
    kept_rel = sorted(str(Path(p).relative_to(repo)) for p in kept)
    assert kept_rel == ["src/app/billing.ts", "src/app/user.py"]
    # the min.js and svg were dropped by default rules
    assert ignored.get("**/*.min.js") == 1
    assert ignored.get("**/*.svg") == 1
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_change_to_queue.py -k backfill_filters -v`
Expected: FAIL — `_backfill_identities` returns a flat list (unpack into `kept, ignored` raises `ValueError`/`too many values`), and ignored paths are present.

- [ ] **Step 3: Write minimal implementation**

```python
# scripts/check_for_changes.py  — add to the import block (after `import queues`)
import ignore

# scripts/check_for_changes.py  — replace _backfill_identities
def _backfill_identities(args: list[str]) -> tuple[list[str], dict[str, int]]:
    """Expand --backfill repo args into every tracked file (absolute path), with
    ignore-glob filtering applied to the repo-relative path. Each arg is a configured
    source name (e.g. 'asv') or a path to a git repo. Returns (kept_abs_paths,
    ignored_by_rule). Uses git ls-files, so it lists tracked files only and never
    recurses into .git/ or build artifacts."""
    by_name = {name: path for path, name in sources.detect_repos()}
    globs = config.ignore_globs()
    kept_abs: list[str] = []
    ignored_total: dict[str, int] = {}
    for a in args:
        repo = by_name.get(a) or Path(a).resolve()
        if not (repo / ".git").is_dir():
            raise ValueError(
                f"--backfill: {a!r} is not a configured source name or a git repo")
        rels = list(git_changes.tracked_files(repo))
        kept, ignored = ignore.partition(rels, globs)
        kept_abs.extend(str((repo / f).resolve()) for f in kept)
        for g, c in ignored.items():
            ignored_total[g] = ignored_total.get(g, 0) + c
    return kept_abs, ignored_total
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_change_to_queue.py -k backfill_filters -v`
Expected: PASS

(The `--backfill` branch in `main()` still calls the old single-return form; it is fixed in Task 6. Running the full suite now may fail that one call site — that is expected and resolved in Task 6.)

- [ ] **Step 5: Commit**

```bash
git add scripts/check_for_changes.py tests/test_change_to_queue.py
git commit -m "feat(check-for-changes): apply ignore globs to --backfill expansion"
```

---

### Task 4: Filter incremental detection

**Files:**
- Modify: `scripts/check_for_changes.py` (`scan_git_candidates`, ~lines 115-139)
- Test: `tests/test_change_to_queue.py` (append)

**Interfaces:**
- Consumes: `config.ignore_globs()`, `ignore.partition`, `git_changes.changed_files`.
- Produces: `scan_git_candidates() -> list[tuple[str, list[str]]]` — unchanged signature; ignored files are silently dropped from each source's path list (and a one-line `ignored N` note printed per source).

- [ ] **Step 1: Write the failing test**

```python
# tests/test_change_to_queue.py  (append)
def test_detection_filters_ignored_changed_files(tmp_path, monkeypatch):
    repo = tmp_path / "asv"
    (repo / ".git").mkdir(parents=True)
    (repo / "src").mkdir(parents=True)
    (repo / "src" / "user.py").write_text("x = 1\n")
    (repo / "logo.svg").write_text("<svg/>\n")
    _cfg(tmp_path, monkeypatch, repos=[str(repo)])

    import importlib, check_for_changes, sources, git_changes
    importlib.reload(check_for_changes)

    monkeypatch.setattr(check_for_changes.sources, "detect_repos",
                        lambda: [(repo, "asv")])
    monkeypatch.setattr(check_for_changes.git_changes, "head_sha", lambda _r: "old")
    monkeypatch.setattr(check_for_changes.git_changes, "fetch", lambda _r: None)
    monkeypatch.setattr(check_for_changes.git_changes, "pull_ff", lambda _r: None)
    monkeypatch.setattr(check_for_changes.git_changes, "changed_files",
                        lambda _r, _b: ["src/user.py", "logo.svg"])

    out = check_for_changes.scan_git_candidates()
    assert len(out) == 1
    name, paths = out[0]
    assert name == "asv"
    assert [Path(p).name for p in paths] == ["user.py"]  # svg filtered out
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_change_to_queue.py -k detection_filters -v`
Expected: FAIL — `logo.svg` is still present in the returned paths.

- [ ] **Step 3: Write minimal implementation**

```python
# scripts/check_for_changes.py  — in scan_git_candidates, replace the body of the
# for-loop AFTER `files = git_changes.changed_files(repo_path, before)` and the
# except-clause, i.e. the abs_paths construction block:
        globs = config.ignore_globs()
        kept, ignored = ignore.partition(files, globs)
        abs_paths = [str(repo_path / f) for f in kept if (repo_path / f).exists()]
        if ignored:
            print(f"  {name}: ignored {sum(ignored.values())} file(s) by rule")
        if not abs_paths:
            print(f"  {name}: up to date.")
            continue
        print(f"  {name}: {len(abs_paths)} file(s)")
        out.append((name, abs_paths))
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_change_to_queue.py -k detection_filters -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add scripts/check_for_changes.py tests/test_change_to_queue.py
git commit -m "feat(check-for-changes): apply ignore globs to incremental detection"
```

---

### Task 5: Filter `--force` folder expansion (named files exempt)

**Files:**
- Modify: `scripts/check_for_changes.py` (`_expand_identities`, ~lines 170-186)
- Test: `tests/test_change_to_queue.py` (append)

**Interfaces:**
- Consumes: `config.ignore_globs()`, `ignore.first_match`, `sources.repo_relative`.
- Produces: `_expand_identities(args) -> list[str]` — unchanged signature. A directory arg expands recursively with ignore filtering applied (repo-relative); a Jira KEY or an explicitly named single file path passes through unfiltered.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_change_to_queue.py  (append)
def test_force_folder_expansion_filters_but_named_file_is_exempt(tmp_path, monkeypatch):
    repo = tmp_path / "asv"
    (repo / "src").mkdir(parents=True)
    (repo / "src" / "user.py").write_text("x=1\n")
    (repo / "src" / "x.min.js").write_text("//min\n")
    _cfg(tmp_path, monkeypatch, repos=[str(repo)])

    import importlib, check_for_changes
    importlib.reload(check_for_changes)

    # folder expansion: the .min.js is filtered out
    expanded = check_for_changes._expand_identities([str(repo / "src")])
    names = sorted(Path(p).name for p in expanded)
    assert names == ["user.py"]

    # explicitly named ignored file: exempt (explicit intent wins)
    named = check_for_changes._expand_identities([str(repo / "src" / "x.min.js")])
    assert [Path(p).name for p in named] == ["x.min.js"]
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_change_to_queue.py -k force_folder_expansion -v`
Expected: FAIL — `x.min.js` appears in the folder-expansion result.

- [ ] **Step 3: Write minimal implementation**

```python
# scripts/check_for_changes.py  — replace _expand_identities
def _expand_identities(args: list[str]) -> list[str]:
    """Expand --force args into concrete identities: a Jira KEY stays as-is; a
    directory expands to every file beneath it (recursive), with ignore-glob filtering
    applied to each repo-relative path; an explicitly named single file stays as-is
    (explicit intent overrides ignores). Paths are resolved to absolute."""
    globs = config.ignore_globs()
    out: list[str] = []
    for a in args:
        if sources.is_jira_key(a):
            out.append(a)
            continue
        p = Path(a)
        if p.is_dir():
            for f in sorted(p.rglob("*")):
                if not f.is_file():
                    continue
                rel = sources.repo_relative(str(f))
                if ignore.first_match(rel, globs) is None:
                    out.append(str(f.resolve()))
        elif p.exists():
            out.append(str(p.resolve()))   # named file — exempt
        else:
            out.append(a)   # not on disk — let source_of raise a clear error
    return out
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_change_to_queue.py -k force_folder_expansion -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add scripts/check_for_changes.py tests/test_change_to_queue.py
git commit -m "feat(check-for-changes): filter --force folder expansion; exempt named files"
```

---

### Task 6: Wire kept/ignored into callers + dry-run reporting

**Files:**
- Modify: `scripts/check_for_changes.py` (`_enqueue_identities` ~205-219; `--backfill` branch in `main()` ~249-260; dry-run backfill path)
- Test: `tests/test_change_to_queue.py` (append)

**Interfaces:**
- Consumes: `_backfill_identities` (now `(kept, ignored)`), `_expand_identities`.
- Produces: `_enqueue_identities(identities: list[str], dry_run: bool, verb: str, ignored: dict[str, int] | None = None) -> None` — enqueues kept identities and prints a kept count plus, when `ignored` is non-empty, an `ignored M (by rule: …)` summary.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_change_to_queue.py  (append)
def test_enqueue_identities_reports_ignored_summary(tmp_path, monkeypatch, capsys):
    repo = tmp_path / "asv"
    (repo / ".git").mkdir(parents=True)
    _cfg(tmp_path, monkeypatch, repos=[str(repo)])
    import importlib, check_for_changes
    importlib.reload(check_for_changes)

    ids = [str((repo / "src" / "user.py"))]
    check_for_changes._enqueue_identities(
        ids, dry_run=True, verb="enqueue",
        ignored={"**/*.min.js": 3, "**/*.svg": 1})
    out = capsys.readouterr().out
    assert "would enqueue 1" in out
    assert "ignored 4" in out
    assert "**/*.min.js" in out  # by-rule breakdown present
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_change_to_queue.py -k reports_ignored_summary -v`
Expected: FAIL — `_enqueue_identities()` has no `ignored` parameter (`TypeError: unexpected keyword argument`).

- [ ] **Step 3: Write minimal implementation**

```python
# scripts/check_for_changes.py  — replace _enqueue_identities
def _enqueue_identities(identities: list[str], dry_run: bool, verb: str,
                        ignored: dict[str, int] | None = None) -> None:
    """Map each identity to its source and enqueue it (unless dry-run); print a kept
    count and, when ignore rules dropped anything, an `ignored M (by rule …)` summary.
    Shared by --force and --backfill."""
    n = 0
    for identity in identities:
        try:
            source = sources.source_of(identity)
        except ValueError as e:
            print(f"ERROR: {e}", file=sys.stderr)
            sys.exit(2)
        if not dry_run:
            queues.enqueue(source, identity)
        n += 1
    done = f"would {verb}" if dry_run else f"{verb}d"
    print(f"{done} {n} identit{'y' if n == 1 else 'ies'}")
    if ignored:
        by_rule = ", ".join(f"{g}={c}" for g, c in sorted(ignored.items()))
        print(f"ignored {sum(ignored.values())} file(s) by rule: {by_rule}")


# scripts/check_for_changes.py  — in main(), replace the --backfill branch body
# (the try/except around _backfill_identities and the _enqueue_identities call):
        try:
            identities, ignored = _backfill_identities(args)
        except (ValueError, RuntimeError) as e:
            print(f"ERROR: {e}", file=sys.stderr)
            sys.exit(2)
        _enqueue_identities(identities, dry_run, "enqueue", ignored)
        return
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_change_to_queue.py -k reports_ignored_summary -v`
Expected: PASS

- [ ] **Step 5: Run the full suite (guards the changed call sites)**

Run: `pytest -q`
Expected: PASS (all tests, including the previously-noted `--backfill` call site now fixed)

- [ ] **Step 6: Commit**

```bash
git add scripts/check_for_changes.py tests/test_change_to_queue.py
git commit -m "feat(check-for-changes): report kept vs ignored (by rule) incl. dry-run"
```

---

### Task 7: Document the `ignore:` block + wiki-queue note

**Files:**
- Modify: `skills/wiki-init/templates/wiki.config.yaml.tmpl` (after the `synth_tuning` commented block, ~line 39)
- Modify: `skills/wiki-queue/SKILL.md` (one line where detection/backfill is described)

- [ ] **Step 1: Append the `ignore:` documentation to the template**

Add to the end of `skills/wiki-init/templates/wiki.config.yaml.tmpl`:

```yaml

# Optional. Extra paths to exclude from ingest, matched (gitignore-style) over each
# file's repo-relative path BEFORE it enters the queue — so junk never reaches extract
# or synth. The pipeline already ignores a built-in set for free: node_modules/ and
# vendor/ trees, minified/map/bundle output, *.d.ts and *.metadata.json, lockfiles,
# binary assets (images/fonts/media), styling (*.css/*.scss/…), and *.pem. List here
# only repo-specific trees the defaults miss — most commonly a compiled library that is
# committed into the source tree. Semantics: `**/` = any depth, `*` = within one path
# segment, `?` = one char; a pattern without a leading `**/` is anchored at the repo root.
# ignore:
#   - ac_portal/local_modules/**     # committed compiled Angular lib (vendored)
#   - ac_ops/terraform/**            # infra-as-code, not product-domain behavior
#   - "**/database_migrations/versions/**"   # autogenerated, redundant with model/
#   - "**/test_*/**"                 # test scaffolding
```

- [ ] **Step 2: Add the wiki-queue note**

In `skills/wiki-queue/SKILL.md`, locate the sentence describing what detection/backfill enqueues and add (adapt wording to the surrounding prose):

> Detection and `--backfill` skip paths matching the `ignore:` globs (built-in junk defaults + the consumer repo's `ignore:` list); see `wiki.config.yaml`.

- [ ] **Step 3: Verify the template still parses as YAML**

Run: `python -c "import yaml,sys; yaml.safe_load(open('skills/wiki-init/templates/wiki.config.yaml.tmpl').read().replace('{{','').replace('}}','')); print('ok')"`
Expected: `ok`

- [ ] **Step 4: Commit**

```bash
git add skills/wiki-init/templates/wiki.config.yaml.tmpl skills/wiki-queue/SKILL.md
git commit -m "docs: document ignore: block in config template and wiki-queue"
```

---

### Task 8: Version bump

**Files:**
- Modify: `.claude-plugin/plugin.json` (`version`)

- [ ] **Step 1: Bump the version**

Change `"version": "0.2.0"` to `"version": "0.3.0"` in `.claude-plugin/plugin.json` (new feature → minor bump).

- [ ] **Step 2: Run the full suite one last time**

Run: `pytest -q`
Expected: PASS

- [ ] **Step 3: Commit**

```bash
git add .claude-plugin/plugin.json
git commit -m "chore: bump plugin version to 0.3.0 (ignore-glob enqueue filtering)"
```

---

## Manual verification (after all tasks)

Against the real repo, confirm the cut matches the census (2204 → ~743 confident, ~442 with judgment subtrees). With an `ignore:` block containing `ac_portal/local_modules/**` (and optionally `ac_ops/terraform/**`, `ac_server/database_migrations/versions/**`, `ac_server/test_ac_server/**`, `.github/**`):

```bash
# from inside the wiki repo (or with WIKI_CONFIG set):
python <plugin>/scripts/check_for_changes.py --backfill ac_aws --dry-run
# Expect: "would enqueue ~743 (or ~442)" + "ignored ~1461 (or ~1762) file(s) by rule: …"
```

No queue writes happen under `--dry-run`; tune the globs, then re-run without `--dry-run` to enqueue for real.

---

## Self-Review

- **Spec coverage:** ignore matcher (T1) · config defaults+merge (T2) · backfill filter (T3) · detection filter (T4) · `--force` folder filter w/ named-file exemption (T5) · kept/ignored wiring + dry-run by-rule report (T6) · docs (T7) · version bump (T8). The user's explicit asks — filtering at enqueue, `local_modules/**` as the headline rule, and a `--dry-run` "would enqueue N, ignored M (by rule)" — are covered by T2/T3/T6 and the manual-verification section.
- **Open decision deferred to config, not code:** the four judgment subtrees (migrations, terraform, tests, `.github/`) are *not* baked into `_IGNORE_DEFAULTS`; they live in the consumer's `ignore:` list (documented in T7). This keeps the policy call with the user and out of the plugin defaults.
- **Type consistency:** `_backfill_identities` returns `(list[str], dict[str,int])` (T3) and is unpacked that way in `main()` (T6). `partition` returns `(kept, ignored_by_rule)` (T1) and is used with that shape in T3/T4. `_enqueue_identities` gains `ignored: dict | None` (T6) consistent with the dict produced upstream.
- **Placeholder scan:** none — every code/test step is complete.
