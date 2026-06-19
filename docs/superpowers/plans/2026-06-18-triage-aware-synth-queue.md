# Triage-Aware Synth Queue Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a Haiku triage pass that drops worthless code/prose/doc before synthesis and stamps each kept item with a line count and `dense`/`routine` flag, so the synth orchestrator can form homogeneous, right-sized batches and route hard files to a stronger model.

**Architecture:** Triage runs in the existing extract phase (parallel Haiku, read-only, orchestrator writes the queue serially). Each kept item enters the synth queue as `<lines>\t<flag>\t<identity>`. The synth orchestrator reads per-kind cutoffs from `config.py` (defaults, optional `synth_tuning:` override) to size batches and pick the model. All changes degrade to current behavior when metadata/config is absent.

**Tech Stack:** Python 3 (stdlib + `pyyaml`, already a dependency), pytest. Skill prompts/orchestration are Markdown.

## Global Constraints

- **No new runtime dependencies.** `pyyaml` is the only third-party import already in use; add nothing else.
- **`config.py` does not cache.** Every accessor re-reads `wiki.config.yaml`. Match that — no module-level caching of config values.
- **`queues.py` is the only writer to queue files.** No other module or subagent writes `<source>.extract` / `<source>.synth`.
- **Identity is always the last tab-separated field of a queue line.** `identity = line.rsplit("\t", 1)[-1]`. The `.extract` queue stores bare identities; only `.synth` lines may carry a `<lines>\t<flag>` prefix.
- **Backward compatibility is mandatory.** A bare `<identity>` synth line and a config with no `synth_tuning:` block must both reproduce today's behavior (`DIGEST_BATCH=12`, Sonnet).
- **Skill script paths use `${CLAUDE_PLUGIN_ROOT}`** in `SKILL.md`, e.g. `python "${CLAUDE_PLUGIN_ROOT}/scripts/queues.py" ...`.
- **Tests use the `WIKI_CONFIG` + `STATE_DIR` env-var pattern** and `tmp_path`/`monkeypatch`, as in `tests/test_queues.py` and `tests/test_config.py`.
- **Chronological invariant:** the orchestrator marks items done in the order `next-extract`/`next-synth` returned them, never in subagent-completion order.

---

## File Structure

| File | Responsibility | Change |
|------|----------------|--------|
| `scripts/config.py` | Project identity + tuning accessors | Add `synth_tuning()` (defaults + override merge) |
| `scripts/queues.py` | Per-source work queues (single writer) | Identity-aware membership; `<lines>\t<flag>` synth metadata; `drop`; note side-car; CLI flags |
| `scripts/ingest_state.py` | Identity → action/classification | `extract_action` routes code/prose/doc to `triage` |
| `skills/wiki-ingest/triage-prompt.md` | Haiku triage subagent prompt (new) | Create |
| `skills/wiki-ingest/synth-prompt.md` | Sonnet/Opus synth subagent prompt | Read & use the optional triage note |
| `skills/wiki-ingest/SKILL.md` | Orchestration | Phase 1 triage dispatch; Phase 2 per-kind batching + model routing |
| `skills/wiki-init/templates/wiki.config.yaml.tmpl` | Scaffolded config | Commented-out `synth_tuning:` block |
| `tests/test_config.py` | config tests | Add `synth_tuning` cases |
| `tests/test_queues.py` | queue tests | Add metadata/note/drop cases; fix `next_synth` shape |
| `tests/test_extract_action.py` | action tests | Update code/prose/doc expectations to `triage` |

---

## Task 1: `config.py` — `synth_tuning()` accessor

**Files:**
- Modify: `scripts/config.py` (add after `lint_config`, end of file ~line 82)
- Test: `tests/test_config.py`

**Interfaces:**
- Produces: `config.synth_tuning() -> dict` with this exact shape:
  ```python
  {
    "jira":  {"small_lines": int, "solo_lines": int, "small_batch": int, "mid_batch": int},
    "doc":   {"small_lines": int, "solo_lines": int, "small_batch": int, "mid_batch": int},
    "code":  {"small_lines": int, "solo_lines": int, "small_batch": int, "mid_batch": int},
    "default_batch": int,
  }
  ```
  The `"code"` bucket covers both `code` and `prose` kinds. Absent `synth_tuning:` keys fall back to defaults; present keys override per-field.

- [ ] **Step 1: Write the failing tests**

Add to `tests/test_config.py` (reuse the existing `_write` helper for the default case; add a second helper for the override case):

```python
def test_synth_tuning_defaults_when_absent(tmp_path, monkeypatch):
    _write(tmp_path, monkeypatch)  # config has no synth_tuning: block
    t = config.synth_tuning()
    assert t["default_batch"] == 12
    assert t["code"]["solo_lines"] == 1500
    assert t["jira"]["small_lines"] == 150
    assert t["doc"]["solo_lines"] == 700


def _write_with_tuning(tmp_path, monkeypatch):
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
        synth_tuning:
          code:
            solo_lines: 999
          default_batch: 20
    """))
    monkeypatch.setenv("WIKI_CONFIG", str(cfg))


def test_synth_tuning_override_merges_per_field(tmp_path, monkeypatch):
    _write_with_tuning(tmp_path, monkeypatch)
    t = config.synth_tuning()
    assert t["code"]["solo_lines"] == 999      # overridden
    assert t["code"]["small_lines"] == 400     # default preserved
    assert t["default_batch"] == 20            # overridden
    assert t["jira"]["solo_lines"] == 400      # untouched kind keeps defaults
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd /home/surehman/projects/personal/domain-expert && python -m pytest tests/test_config.py -k synth_tuning -v`
Expected: FAIL with `AttributeError: module 'config' has no attribute 'synth_tuning'`

- [ ] **Step 3: Implement `synth_tuning()`**

Append to `scripts/config.py`:

```python
import copy

_SYNTH_TUNING_DEFAULTS = {
    "jira": {"small_lines": 150, "solo_lines": 400, "small_batch": 15, "mid_batch": 6},
    "doc":  {"small_lines": 250, "solo_lines": 700, "small_batch": 15, "mid_batch": 4},
    "code": {"small_lines": 400, "solo_lines": 1500, "small_batch": 15, "mid_batch": 3},
    "default_batch": 12,
}


def synth_tuning() -> dict:
    """Per-kind synth batching cutoffs. Code-baked defaults, optionally overridden by
    a `synth_tuning:` block in wiki.config.yaml. Absent keys fall back to defaults, so
    a config with no block (or no key) reproduces today's behavior. The `code` bucket
    covers both `code` and `prose` kinds."""
    merged = copy.deepcopy(_SYNTH_TUNING_DEFAULTS)
    override = load().get("synth_tuning") or {}
    for kind, vals in override.items():
        if isinstance(vals, dict) and isinstance(merged.get(kind), dict):
            merged[kind].update(vals)
        else:
            merged[kind] = vals
    return merged
```

Move `import copy` to the top of the file with the other imports (`os`, `Path`, `yaml`) rather than mid-file, to match house style.

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd /home/surehman/projects/personal/domain-expert && python -m pytest tests/test_config.py -v`
Expected: PASS (all config tests, including the new ones)

- [ ] **Step 5: Commit**

```bash
git add scripts/config.py tests/test_config.py
git commit -m "feat(config): synth_tuning() per-kind cutoffs with optional override"
```

---

## Task 2: `queues.py` — metadata-aware synth queue, drop, and note side-car

**Files:**
- Modify: `scripts/queues.py`
- Test: `tests/test_queues.py`

**Interfaces:**
- Consumes: `config.state_dir()` (existing).
- Produces:
  - `queues._identity(line: str) -> str` — last tab field.
  - `queues.parse_synth_line(line: str) -> tuple[int | None, str | None, str]` — `(lines, flag, identity)`.
  - `queues.move_to_synth(source, identity, lines: int | None = None, flag: str | None = None) -> None`.
  - `queues.next_synth(n: int) -> list[tuple[str, int | None, str | None, str]]` — `(source, lines, flag, identity)` (shape change from `(source, identity)`).
  - `queues.next_extract(n: int) -> list[tuple[str, str]]` — unchanged shape `(source, identity)`.
  - `queues.drop(source, identity) -> None` — triage SKIP: remove from `.extract`, clear note, no synth.
  - `queues.write_note(identity, text) / read_note(identity) -> str / clear_note(identity)`.
  - CLI: `extracted <source> <identity> [--lines N] [--flag F]`; `next-synth` prints `<src>\t<lines>\t<flag>\t<identity>`; `drop <source> <identity>`; `write-note <identity> <text...>`; `read-note <identity>`.

- [ ] **Step 1: Write the failing tests**

Add to `tests/test_queues.py` (the `_q` helper already exists):

```python
def test_parse_synth_line_with_metadata():
    import queues
    assert queues.parse_synth_line("42\tdense\t/abs/x.py") == (42, "dense", "/abs/x.py")

def test_parse_synth_line_bare_identity_is_backward_compatible():
    import queues
    assert queues.parse_synth_line("TESTPROJ-1") == (None, None, "TESTPROJ-1")

def test_identity_is_last_tab_field():
    import queues
    assert queues._identity("42\tdense\t/abs/x.py") == "/abs/x.py"
    assert queues._identity("TESTPROJ-1") == "TESTPROJ-1"

def test_move_to_synth_writes_metadata_line(tmp_path, monkeypatch):
    q = _q(tmp_path, monkeypatch)
    q.enqueue("jira", "TESTPROJ-1")
    q.move_to_synth("jira", "TESTPROJ-1", lines=42, flag="dense")
    assert q.read(q.synth_file("jira")) == ["42\tdense\tTESTPROJ-1"]

def test_move_to_synth_without_metadata_stays_bare(tmp_path, monkeypatch):
    q = _q(tmp_path, monkeypatch)
    q.enqueue("jira", "TESTPROJ-1")
    q.move_to_synth("jira", "TESTPROJ-1")
    assert q.read(q.synth_file("jira")) == ["TESTPROJ-1"]

def test_next_synth_returns_source_lines_flag_identity(tmp_path, monkeypatch):
    q = _q(tmp_path, monkeypatch)
    q._write(q.synth_file("jira"), ["42\tdense\tTESTPROJ-9", "TESTPROJ-10"])
    assert q.next_synth(10) == [
        ("jira", 42, "dense", "TESTPROJ-9"),
        ("jira", None, None, "TESTPROJ-10"),
    ]

def test_synthed_matches_on_identity_despite_metadata(tmp_path, monkeypatch):
    q = _q(tmp_path, monkeypatch)
    q._write(q.synth_file("jira"), ["42\tdense\tTESTPROJ-1", "7\troutine\tTESTPROJ-2"])
    q.synthed("jira", "TESTPROJ-1")
    assert q.read(q.synth_file("jira")) == ["7\troutine\tTESTPROJ-2"]

def test_drop_removes_from_extract(tmp_path, monkeypatch):
    q = _q(tmp_path, monkeypatch)
    q.enqueue("raw", "/abs/raw/style.css")
    q.drop("raw", "/abs/raw/style.css")
    assert q.read(q.extract_file("raw")) == []
    assert q.read(q.synth_file("raw")) == []

def test_note_roundtrip_and_clear(tmp_path, monkeypatch):
    q = _q(tmp_path, monkeypatch)
    q.write_note("/abs/x.py", "billing rules live in calc_invoice")
    assert q.read_note("/abs/x.py") == "billing rules live in calc_invoice"
    q.clear_note("/abs/x.py")
    assert q.read_note("/abs/x.py") == ""

def test_synthed_clears_note(tmp_path, monkeypatch):
    q = _q(tmp_path, monkeypatch)
    q._write(q.synth_file("raw"), ["10\troutine\t/abs/x.py"])
    q.write_note("/abs/x.py", "note")
    q.synthed("raw", "/abs/x.py")
    assert q.read_note("/abs/x.py") == ""
```

Also **update the existing** `test_next_synth_priority_order` (it asserts the old 2-tuple shape):

```python
def test_next_synth_priority_order(tmp_path, monkeypatch):
    repo = tmp_path / "asv"
    repo.mkdir()
    q = _q(tmp_path, monkeypatch, [str(repo)])
    q._write(q.synth_file("raw"), ["/abs/raw/a.md"])
    q._write(q.synth_file("jira"), ["TESTPROJ-9"])
    assert q.next_synth(10) == [
        ("jira", None, None, "TESTPROJ-9"),
        ("raw", None, None, "/abs/raw/a.md"),
    ]
```

Add CLI tests:

```python
def test_cli_extracted_with_metadata(tmp_path, monkeypatch):
    q = _q(tmp_path, monkeypatch)
    q.enqueue("jira", "TESTPROJ-1")
    r = _cli(tmp_path, "extracted", "jira", "TESTPROJ-1", "--lines", "42", "--flag", "dense")
    assert r.returncode == 0, r.stderr
    assert q.read(q.synth_file("jira")) == ["42\tdense\tTESTPROJ-1"]

def test_cli_next_synth_prints_metadata(tmp_path, monkeypatch):
    q = _q(tmp_path, monkeypatch)
    q._write(q.synth_file("jira"), ["42\tdense\tTESTPROJ-9"])
    r = _cli(tmp_path, "next-synth", "5")
    assert r.returncode == 0, r.stderr
    assert r.stdout.splitlines() == ["jira\t42\tdense\tTESTPROJ-9"]

def test_cli_drop(tmp_path, monkeypatch):
    q = _q(tmp_path, monkeypatch)
    q.enqueue("raw", "/abs/raw/style.css")
    r = _cli(tmp_path, "drop", "raw", "/abs/raw/style.css")
    assert r.returncode == 0, r.stderr
    assert q.read(q.extract_file("raw")) == []
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd /home/surehman/projects/personal/domain-expert && python -m pytest tests/test_queues.py -v`
Expected: FAIL — new tests error on missing `parse_synth_line`/`drop`/`write_note`; `next_synth` tests fail on tuple shape.

- [ ] **Step 3: Implement the queue changes**

In `scripts/queues.py`, add `import hashlib` at the top (with `sys`, `Path`).

Add helpers (after `read`, before `in_extract`):

```python
def _identity(line: str) -> str:
    """The identity is the last tab-separated field; any metadata (lines, flag) is an
    optional prefix. A bare line with no tab is its own identity — backward compatible."""
    return line.rsplit("\t", 1)[-1]


def parse_synth_line(line: str) -> tuple[int | None, str | None, str]:
    """(lines, flag, identity) for a synth line `<lines>\\t<flag>\\t<identity>`.
    A bare identity, or partial/garbled metadata, yields None for the missing fields."""
    parts = line.split("\t")
    identity = parts[-1]
    lines = flag = None
    if len(parts) >= 3:
        try:
            lines = int(parts[-3])
        except ValueError:
            lines = None
        flag = parts[-2] or None
    return lines, flag, identity
```

Replace `in_extract`, `in_synth`, `_remove`, `_append` so they compare on identity:

```python
def in_extract(source: str, identity: str) -> bool:
    return identity in [_identity(ln) for ln in read(extract_file(source))]


def in_synth(source: str, identity: str) -> bool:
    return identity in [_identity(ln) for ln in read(synth_file(source))]


def _remove(path: Path, identity: str) -> None:
    _write(path, [ln for ln in read(path) if _identity(ln) != identity])


def _append(path: Path, line: str) -> None:
    ident = _identity(line)
    lines = read(path)
    if ident not in [_identity(ln) for ln in lines]:
        lines.append(line)
    _write(path, lines)
```

Replace `move_to_synth`:

```python
def move_to_synth(source: str, identity: str,
                  lines: int | None = None, flag: str | None = None) -> None:
    """Extract/triage succeeded: identity moves .extract -> .synth. When lines/flag are
    given, the synth line carries a `<lines>\\t<flag>\\t<identity>` metadata prefix the
    orchestrator uses for batching; otherwise it is written bare (current behavior)."""
    _remove(extract_file(source), identity)
    if lines is None and flag is None:
        synth_line = identity
    else:
        synth_line = f"{lines if lines is not None else ''}\t{flag or ''}\t{identity}"
    _append(synth_file(source), synth_line)
```

Add `drop` (after `move_to_synth`):

```python
def drop(source: str, identity: str) -> None:
    """Triage SKIP: discard an item from extraction without synthesizing it. Removes it
    from .extract and clears any note; it never reaches .synth and leaves no wiki trace."""
    _remove(extract_file(source), identity)
    clear_note(identity)
```

Add the note side-car (after `drop`):

```python
def note_file(identity: str) -> Path:
    """State-dir side-car holding the triage note for an identity (keyed by a hash so a
    file-path identity is filesystem-safe)."""
    h = hashlib.sha1(identity.encode("utf-8")).hexdigest()[:16]
    return config.state_dir() / "notes" / f"{h}.txt"


def write_note(identity: str, text: str) -> None:
    if not text or not text.strip():
        return
    p = note_file(identity)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(text.strip() + "\n", encoding="utf-8")


def read_note(identity: str) -> str:
    p = note_file(identity)
    return p.read_text(encoding="utf-8").strip() if p.is_file() else ""


def clear_note(identity: str) -> None:
    p = note_file(identity)
    if p.is_file():
        p.unlink()
```

Note: `drop` and `synthed` reference `clear_note`, which is defined below them in module order — fine, since they are only *called* at runtime (after the module is fully loaded), not at import time.

Replace `_next`, `next_extract`, `next_synth`:

```python
def _next(file_fn, n: int) -> list[tuple[str, str]]:
    out: list[tuple[str, str]] = []
    for source in sources.source_order():
        for line in read(file_fn(source)):
            out.append((source, line))
            if len(out) >= n:
                return out
    return out


def next_extract(n: int) -> list[tuple[str, str]]:
    return [(src, _identity(line)) for src, line in _next(extract_file, n)]


def next_synth(n: int) -> list[tuple[str, int | None, str | None, str]]:
    return [(src, *parse_synth_line(line)) for src, line in _next(synth_file, n)]
```

Update `synthed` to clear the note:

```python
def synthed(source: str, identity: str) -> None:
    """Synth completed an identity: remove it from the synth queue and clear its note."""
    _remove_synth(source, identity)
    clear_note(identity)
```

- [ ] **Step 4: Update the CLI in `main()`**

Replace the `next-synth`, `extracted` branches and add `drop`, `write-note`, `read-note`:

```python
    if cmd == "next-synth":
        for src, lines, flag, ident in next_synth(int(a[1]) if len(a) > 1 else 1):
            print(f"{src}\t{lines if lines is not None else ''}\t{flag or ''}\t{ident}")
        sys.exit(0)
    if cmd == "extracted":        # extracted <source> <identity> [--lines N] [--flag F]
        rest = a[1:]
        lines = flag = None
        pos: list[str] = []
        i = 0
        while i < len(rest):
            if rest[i] == "--lines":
                lines = int(rest[i + 1]); i += 2
            elif rest[i] == "--flag":
                flag = rest[i + 1]; i += 2
            else:
                pos.append(rest[i]); i += 1
        move_to_synth(pos[0], pos[1], lines=lines, flag=flag)
        sys.exit(0)
    if cmd == "drop":             # drop <source> <identity>
        drop(a[1], a[2])
        sys.exit(0)
    if cmd == "write-note":       # write-note <identity> <text...>
        write_note(a[1], " ".join(a[2:]))
        sys.exit(0)
    if cmd == "read-note":        # read-note <identity>
        print(read_note(a[1]))
        sys.exit(0)
```

Leave the existing `next-extract`, `enqueue`, `synthed`, `status` branches as they are.

- [ ] **Step 5: Run tests to verify they pass**

Run: `cd /home/surehman/projects/personal/domain-expert && python -m pytest tests/test_queues.py -v`
Expected: PASS (all, including updated `test_next_synth_priority_order`)

- [ ] **Step 6: Commit**

```bash
git add scripts/queues.py tests/test_queues.py
git commit -m "feat(queues): synth metadata prefix, drop, and triage-note side-car"
```

---

## Task 3: `ingest_state.py` — route code/prose/doc to `triage`

**Files:**
- Modify: `scripts/ingest_state.py:141-156` (`extract_action`)
- Test: `tests/test_extract_action.py`

**Interfaces:**
- Consumes: existing `_is_jira`, `has_import`, `is_escalated`, `is_doc`.
- Produces: `extract_action(path)` now returns one of `extract-jira` | `reextract-jira` | `extract-doc` | `triage` | `ready`. `ready` is now reached **only** by a Jira identity whose clean import already exists (interrupted-run resume). Code/prose, and a doc whose import already exists, return `triage`.

- [ ] **Step 1: Update the failing tests**

In `tests/test_extract_action.py`, change the two expectations that move to `triage` and add a code/prose case:

```python
def test_doc_with_digest_is_triage(tmp_path, monkeypatch):
    monkeypatch.setenv("IMPORTS_DIR", str(tmp_path))
    ip = ingest_state.import_path("docs/spec.pdf")
    ip.parent.mkdir(parents=True, exist_ok=True)
    ip.write_text("---\nkey: x\n---\nbody\n")
    assert ingest_state.extract_action("docs/spec.pdf") == "triage"


def test_code_and_prose_are_triage(tmp_path, monkeypatch):
    monkeypatch.setenv("IMPORTS_DIR", str(tmp_path))
    assert ingest_state.extract_action("src/main.py") == "triage"
    assert ingest_state.extract_action("docs/readme.md") == "triage"
```

Delete the now-superseded `test_doc_with_digest_is_ready` and `test_code_and_prose_are_ready` (replaced above). Update the CLI test `test_extract_action_cli_ready` to assert `triage`:

```python
def test_extract_action_cli_triage(tmp_path):
    out = _cli(tmp_path, "src/main.py")
    assert out.returncode == 0
    assert out.stdout.strip() == "triage"
```

(Delete the old `test_extract_action_cli_ready`.) Leave the jira tests (`extract-jira`, `reextract-jira`, clean-import `ready`) and `test_doc_no_digest_needs_extract` unchanged.

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd /home/surehman/projects/personal/domain-expert && python -m pytest tests/test_extract_action.py -v`
Expected: FAIL — `triage` expected, `ready`/`extract-doc` returned.

- [ ] **Step 3: Implement the routing change**

Replace `extract_action` in `scripts/ingest_state.py`:

```python
def extract_action(path: str) -> str:
    """What extraction a queued identity needs, for the ingest driver to dispatch on:

      "extract-jira"   Jira key, no import yet            -> Haiku extract subagent
      "reextract-jira" Jira import flagged escalate       -> Sonnet re-extract subagent
      "ready"          Jira/doc clean import already exists -> no work; move to .synth
                       (only reached on an interrupted-run resume)
      "extract-doc"    binary doc, no import yet          -> extract_docs.py (mechanical)
      "triage"         code/prose (read directly), OR a doc whose converted import now
                       exists -> Haiku triage subagent (skip-or-keep + lines + flag)
    """
    if _is_jira(path):
        if not has_import(path):
            return "extract-jira"
        return "reextract-jira" if is_escalated(path) else "ready"
    if is_doc(path):
        return "extract-doc" if not has_import(path) else "triage"
    return "triage"
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd /home/surehman/projects/personal/domain-expert && python -m pytest tests/test_extract_action.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add scripts/ingest_state.py tests/test_extract_action.py
git commit -m "feat(ingest_state): route code/prose/doc to triage action"
```

---

## Task 4: Triage prompt (Haiku subagent)

**Files:**
- Create: `skills/wiki-ingest/triage-prompt.md`

No automated test — this is a prompt. Verification is a read-through against the return contract that `SKILL.md` (Task 6) parses: `KEEP | <flag> | <note>`, `SKIP | <reason>`, `FAILED | <reason>`.

- [ ] **Step 1: Create the prompt**

Write `skills/wiki-ingest/triage-prompt.md`:

```markdown
# TRIAGE PROMPT (Haiku triage subagent)

You triage **one** source file for the wiki pipeline. You do NOT touch the wiki,
the queues, any import, or any other file. You read one file and return one status
line. The orchestrator — not you — writes the queue.

**Input.** You are given one `<identity>` (a file path, or a converted-doc import
path). Run `python "${CLAUDE_PLUGIN_ROOT}/scripts/ingest_state.py" classify <identity>`
→ `<kind>\t<read_target>`. Read `<read_target>`. That file is all you judge.

**Decide two things.**

1. **Keep or skip?** SKIP a file with **no business-relevant knowledge** (CLAUDE.md
   §2): pure styling (CSS/SCSS), generated/minified output, lock files, vendored
   third-party code, boilerplate scaffolding, build config, fixtures, a doc page that
   is only navigation/screenshots/legal boilerplate. KEEP anything that states or
   encodes terminology, entities, concepts, business processes, or rules — even
   partially. When genuinely unsure, KEEP (synthesis can still discard it cheaply;
   a wrong SKIP loses knowledge silently).

2. **For a KEEP, how dense?** `dense` = rich in distinct business rules/concepts, or
   it introduces/renames a domain term that will ripple across pages — the hard,
   high-value case. `routine` = some business content, but straightforward. Base this
   on **content**, not file size.

**Return EXACTLY ONE line:**

- `KEEP | <dense|routine> | <one-line note>` — the note tells the synthesizer where
  the business value is (e.g. "invoice rounding rules in `calc_total`"). Keep it to
  one line; it is a focus hint, never a substitute for reading the file. If you have
  nothing useful to add, write `KEEP | routine | -`.
- `SKIP | <short reason>` — e.g. `SKIP | pure CSS, no business content`.
- `FAILED | <reason>` — could not read/classify the file.

Do not compute or report a line count — the orchestrator stamps that mechanically.
```

- [ ] **Step 2: Verify the contract by re-reading**

Confirm the three return forms exactly match what Task 6's Phase 1 parses (`KEEP`/`SKIP`/`FAILED`, `dense`/`routine`). No command to run.

- [ ] **Step 3: Commit**

```bash
git add skills/wiki-ingest/triage-prompt.md
git commit -m "feat(wiki-ingest): Haiku triage prompt (skip/keep + density flag + note)"
```

---

## Task 5: `synth-prompt.md` — read and use the triage note

**Files:**
- Modify: `skills/wiki-ingest/synth-prompt.md:15-16` (step 2 preamble)

No automated test — prompt edit. Verification is a read-through.

- [ ] **Step 1: Insert the note-usage instruction**

In `skills/wiki-ingest/synth-prompt.md`, step 2 currently begins:

```
2. For each path **in order**, run `python "${CLAUDE_PLUGIN_ROOT}/scripts/ingest_state.py" classify <path>`
   → `<kind>\t<read_target>`, then read `<read_target>` and tag/cite by kind:
```

Replace that opening with:

```
2. For each path **in order**, run `python "${CLAUDE_PLUGIN_ROOT}/scripts/ingest_state.py" classify <path>`
   → `<kind>\t<read_target>`, then read `<read_target>` and tag/cite by kind. First run
   `python "${CLAUDE_PLUGIN_ROOT}/scripts/queues.py" read-note <path>`; if it prints a
   non-empty triage note, treat it as a **focus hint** for where the business value sits
   — but ALWAYS read `<read_target>` in full regardless; the note never replaces the read:
```

Leave the rest of step 2 (the per-kind tag/cite bullets) unchanged.

- [ ] **Step 2: Verify**

Re-read the edited step 2 to confirm the citation/tag bullets still follow and the `read-note` call uses `<path>` (the identity), matching `queues.py read-note`.

- [ ] **Step 3: Commit**

```bash
git add skills/wiki-ingest/synth-prompt.md
git commit -m "feat(wiki-ingest): synth reads the optional triage note as a focus hint"
```

---

## Task 6: `SKILL.md` — Phase 1 triage dispatch + Phase 2 per-kind batching

**Files:**
- Modify: `skills/wiki-ingest/SKILL.md:29-64` (Phase 1) and `:62-90` (Phase 2)

No automated test — orchestration doc. Verification is a read-through against the CLIs built in Tasks 1–2.

- [ ] **Step 1: Add the `triage` branch to Phase 1**

In the Phase 1 dispatch list (after the `extract-doc` bullet, before `extract-jira`), add:

```markdown
- **`triage`** → spawn one Haiku subagent per identity (Agent tool,
  `subagent_type: general-purpose`, `model: haiku`) with `triage-prompt.md`
  (substitute `<identity>`). ≤FANOUT in parallel in one message; wait for all. The
  subagents are read-only and write nothing — you act on their return lines after the
  whole wave returns, in the original `next-extract` order:
  - `KEEP | <flag> | <note>` → compute the line count mechanically:
    `wc -l < "$(python "${CLAUDE_PLUGIN_ROOT}/scripts/ingest_state.py" classify <identity> | cut -f2)"`;
    if the note is not `-`, `python "${CLAUDE_PLUGIN_ROOT}/scripts/queues.py" write-note <identity> <note>`;
    then `python "${CLAUDE_PLUGIN_ROOT}/scripts/queues.py" extracted <source> <identity> --lines <N> --flag <flag>`.
  - `SKIP | <reason>` → `python "${CLAUDE_PLUGIN_ROOT}/scripts/queues.py" drop <source> <identity>` (discarded, never synthesized).
  - `FAILED` → retry once; if it fails again, leave pending and continue.
```

Then amend the existing `extract-doc` bullet so it no longer moves docs straight to synth — converted docs must still be triaged:

```markdown
- **`extract-doc`** → batch all doc paths; run `python "${CLAUDE_PLUGIN_ROOT}/scripts/extract_docs.py"
  <paths...>` once. Do NOT call `extracted` here — leave each doc in `.extract`. Once its
  import exists, `extract-action` returns `triage`, so the same loop re-picks it on its
  next pass and triages the converted markdown like any other kept source.
```

And amend the jira post-wave handling so jira items are stamped with a line count too (so per-kind batching works for jira):

```markdown
- `EXTRACTED`/`EMPTY` → `python "${CLAUDE_PLUGIN_ROOT}/scripts/jira_utils.py" <KEY> --stamp-hash`, then
  stamp the import's length and mark extracted:
  `python "${CLAUDE_PLUGIN_ROOT}/scripts/queues.py" extracted jira <KEY> --lines "$(wc -l < "$(python "${CLAUDE_PLUGIN_ROOT}/scripts/ingest_state.py" import-path <KEY>)")" --flag routine`.
  (Jira imports default to `routine`; the density flag is a code/prose/doc signal.)
```

- [ ] **Step 2: Replace Phase 2 batching logic**

Replace the Phase 2 constant line and the synth loop preamble. Change:

```
`DIGEST_BATCH=12`, `LINT_EVERY=20`.
```

to:

```
`LINT_EVERY=20`. Batch sizes and model routing come from
`python "${CLAUDE_PLUGIN_ROOT}/scripts/config.py"`-backed tuning
(`config.synth_tuning()`); a queue line with no metadata falls back to a batch of
`default_batch` (12) on Sonnet — today's behavior.
```

Then replace synth loop step 1 ("Spawn ONE Sonnet subagent … with the batch of identities") with:

```markdown
1. Read the next slice: `python "${CLAUDE_PLUGIN_ROOT}/scripts/queues.py" next-synth <N>`
   → lines of `<source>\t<lines>\t<flag>\t<identity>`. Form ONE batch from the FRONT of
   this slice under these rules, then spawn exactly one subagent for it:

   - **Homogeneous by kind.** Determine each item's kind via
     `python "${CLAUDE_PLUGIN_ROOT}/scripts/ingest_state.py" classify <identity>` (first field;
     `jira`/`doc`/`code`/`prose`). Map `prose`→the `code` bucket. A batch never crosses a
     kind boundary — stop the batch at the first item of a different kind.
   - **Per-kind size cutoffs** from `synth_tuning()[<bucket>]` (`small_lines`,
     `solo_lines`, `small_batch`, `mid_batch`):
     - any item with `<lines>` empty (no metadata) → batch up to `default_batch`, Sonnet.
     - `lines < small_lines` → batch up to `small_batch`.
     - `small_lines ≤ lines < solo_lines` → batch up to `mid_batch`.
     - `lines ≥ solo_lines` → solo (batch of 1).
     A batch is the longest run of same-kind items, in queue order, whose largest member's
     tier allows it, capped at that tier's batch count.
   - **Model by flag, not size.** If ANY item in the formed batch is flagged `dense`,
     make it a solo batch (1 item) and use `model: opus`. Otherwise `model: sonnet`.

   Spawn ONE subagent (`synth-prompt.md` + the batch identities) at the chosen model. Wait.
```

Leave step 2 (`SYNTHED`/`NEEDS-INPUT`/`FAILED`) and step 3 (lint gate) unchanged — `synthed <source> <id>` already matches on identity (Task 2).

- [ ] **Step 3: Verify the CLIs referenced exist**

Confirm each command used above exists from Tasks 1–2:
- `queues.py next-synth` prints 4 tab fields ✓ (Task 2)
- `queues.py extracted ... --lines --flag` ✓ (Task 2)
- `queues.py drop` / `write-note` / `read-note` ✓ (Task 2)
- `ingest_state.py classify` / `import-path` ✓ (existing)
- `config.synth_tuning()` ✓ (Task 1)

- [ ] **Step 4: Commit**

```bash
git add skills/wiki-ingest/SKILL.md
git commit -m "feat(wiki-ingest): triage dispatch + per-kind synth batching and model routing"
```

---

## Task 7: `wiki-init` config template — commented `synth_tuning:` block

**Files:**
- Modify: `skills/wiki-init/templates/wiki.config.yaml.tmpl`

- [ ] **Step 1: Append the commented block**

Add to the end of `skills/wiki-init/templates/wiki.config.yaml.tmpl` (after the `lint:` block):

```yaml

# Optional. Tunes how the synth phase batches and routes work. Everything here is
# commented out: the pipeline ships with these exact defaults baked in, so you only
# need a key if you want to override it after watching real ingests. Lines are raw
# line counts; cutoffs differ per kind because the unit isn't equivalent across them.
# synth_tuning:
#   default_batch: 12       # items per batch when an item has no triage metadata
#   jira:
#     small_lines: 150      # below this: batch up to small_batch
#     solo_lines: 400       # at/above this: one item per agent
#     small_batch: 15
#     mid_batch: 6          # batch size between small_lines and solo_lines
#   doc:
#     small_lines: 250
#     solo_lines: 700
#     small_batch: 15
#     mid_batch: 4
#   code:                   # also covers prose
#     small_lines: 400
#     solo_lines: 1500
#     small_batch: 15
#     mid_batch: 3
```

- [ ] **Step 2: Verify the template still parses as YAML**

Run:
```bash
cd /home/surehman/projects/personal/domain-expert && python -c "import yaml; d=yaml.safe_load(open('skills/wiki-init/templates/wiki.config.yaml.tmpl').read().replace('{{JIRA_KEY}}','K').replace('{{PRODUCT_NAME}}','N').replace('{{CONFIG_DIR}}','~/c').replace('{{JIRA_BASE_URL}}','http://x').replace('{{JIRA_JQL}}','project = K').replace('{{SOURCE_REPOS_YAML_LIST}}','[]').replace('{{BRAND_TERMS_YAML_LIST}}','[]')); assert 'synth_tuning' not in d, 'block must stay commented'; print('parses; synth_tuning absent (commented) OK')"
```
Expected: `parses; synth_tuning absent (commented) OK`

- [ ] **Step 3: Commit**

```bash
git add skills/wiki-init/templates/wiki.config.yaml.tmpl
git commit -m "docs(wiki-init): document synth_tuning knobs as a commented-out block"
```

---

## Final verification

- [ ] **Run the full suite**

Run: `cd /home/surehman/projects/personal/domain-expert && python -m pytest -v`
Expected: PASS (all tests green)

- [ ] **Confirm backward compatibility manually**

A pre-existing repo with no `synth_tuning:` and bare synth-queue lines must behave as before:
- `config.synth_tuning()["default_batch"]` → `12`
- `queues.parse_synth_line("TESTPROJ-1")` → `(None, None, "TESTPROJ-1")`
- A no-metadata synth item batches at `default_batch` on Sonnet (Phase 2 first bullet).

---

## Out of scope (v1)

- **Per-`dense` flag for Jira.** Jira imports are stamped `routine`; deriving a density flag from Jira content would require changing `extract-prompt.md`'s return contract. Deferred — Jira items still get correct per-kind line-count batching.
- **Re-scaffolding existing repos.** The commented `synth_tuning:` block only lands in newly `wiki-init`-ed configs. Existing repos need nothing (absence = defaults).
