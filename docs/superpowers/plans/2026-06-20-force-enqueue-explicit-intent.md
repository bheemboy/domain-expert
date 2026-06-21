# Implementation Plan — Force-enqueue: explicit intent wins

> **For agentic workers:** REQUIRED SUB-SKILL: Use `superpowers:subagent-driven-development`
> (or `superpowers:executing-plans`) to execute this plan. Each task is bite-sized and TDD-first:
> write the failing test → run it to confirm it fails for the right reason → implement →
> run to confirm green → commit. Do not batch tasks. Do not skip the red step.

**Spec:** `docs/superpowers/specs/2026-06-19-force-enqueue-explicit-intent-design.md` (approved)
**Date:** 2026-06-20

## Goal

Make `/wiki-queue <path|folder>` (the `--force` path in `check_for_changes.py`) a deliberate
**"explicit intent wins"** override:

1. **Nothing it enqueues is filtered at enqueue** — file *or* folder, any extension, including
   images and otherwise-ignored assets.
2. **Nothing it enqueues can be dropped by the Haiku triage.** Haiku still *triages* each forced
   file (reads it, produces a density flag + focus note to guide synth) — but the keep/skip
   decision is removed: a forced file is always kept.

## Architecture

Two existing drop-gates are bypassed for forced items only:

- **Enqueue gate** (`check_for_changes._expand_identities`): the folder branch stops applying the
  ignore filter. The single-named-file branch is already exempt — no change there.
- **Triage gate** (Haiku SKIP during extract→synth): a hash-keyed side-car marker
  (`state/forced/<hash>.flag`, mirroring the existing `note` side-car) records "this identity was
  forced". `extract_action` returns a new action `triage-forced` instead of `triage` when the
  marker is set. The ingest driver runs the same Haiku triage but prepends a no-skip preamble and
  always takes the KEEP path. The marker is cleared when the identity leaves `.extract`
  (`drop` / `move_to_synth`).

Data flow:

```
/wiki-queue diagrams/
  → check_for_changes --force diagrams/
     → _expand_identities: every file beneath diagrams/, NO ignore filter
     → _enqueue_identities(forced=True): queues.enqueue + queues.mark_forced (skipped on dry-run)
/wiki-ingest
  → extract-action <arch.png> → "triage-forced"
     → Haiku triage (forced-triage-prompt + triage-prompt): KEEP | dense | "<focus note>"
     → write-note; queues extracted ... --lines N --flag dense   (clears forced marker)
  → synth reads arch.png visually + focus note → wiki page
```

## Tech Stack

- Python 3 (stdlib only) under `scripts/`; tests are pytest under `tests/` (modules imported as
  top-level via `tests/conftest.py` sys.path insertion; `STATE_DIR` / `WIKI_CONFIG` / `IMPORTS_DIR`
  env overrides).
- Markdown skill/prompt files under `skills/wiki-ingest/` and `skills/wiki-queue/`.

## Global Constraints

- **Version floor:** bump `.claude-plugin/plugin.json` `0.3.0` → `0.4.0` (last task).
- **No new `image` kind**, no vision-specific prompts, no `media_gap` route. Images flow through
  classified as `code` and are read visually by the triage/synth subagents.
- **Side-car marker**, never a queue-line prefix — `extract-action` stays the single source of
  truth the markdown driver consults; `next-extract` output format and driver line-parsing are
  unchanged.
- **Detection (`--jira`/`--code`/default) and `--backfill` are unchanged** — they still filter.
- `ingest_state` may `import queues` (verified: no cycle — `queues` imports only `config`,
  `sources`).
- Run the full suite (`python -m pytest -q`) green before each commit. Commit messages end with the
  `Co-Authored-By` trailer.

---

## Task 1 — `queues.py`: the forced side-car marker + CLI + lifecycle

**Test** — append to `tests/test_queues.py`:

```python
def test_forced_roundtrip_and_clear(tmp_path, monkeypatch):
    q = _q(tmp_path, monkeypatch)
    assert not q.is_forced("/abs/arch.png")
    q.mark_forced("/abs/arch.png")
    assert q.is_forced("/abs/arch.png")
    q.clear_forced("/abs/arch.png")
    assert not q.is_forced("/abs/arch.png")
    q.clear_forced("/abs/arch.png")   # idempotent

def test_drop_clears_forced(tmp_path, monkeypatch):
    q = _q(tmp_path, monkeypatch)
    q.enqueue("raw", "/abs/raw/arch.png")
    q.mark_forced("/abs/raw/arch.png")
    q.drop("raw", "/abs/raw/arch.png")
    assert not q.is_forced("/abs/raw/arch.png")

def test_move_to_synth_clears_forced(tmp_path, monkeypatch):
    q = _q(tmp_path, monkeypatch)
    q.enqueue("raw", "/abs/raw/arch.png")
    q.mark_forced("/abs/raw/arch.png")
    q.move_to_synth("raw", "/abs/raw/arch.png", lines=10, flag="dense")
    assert not q.is_forced("/abs/raw/arch.png")

def test_cli_forced_roundtrip(tmp_path, monkeypatch):
    q = _q(tmp_path, monkeypatch)
    assert _cli(tmp_path, "is-forced", "/abs/x.py").stdout.strip() == "0"
    assert _cli(tmp_path, "mark-forced", "/abs/x.py").returncode == 0
    assert _cli(tmp_path, "is-forced", "/abs/x.py").stdout.strip() == "1"
    assert _cli(tmp_path, "clear-forced", "/abs/x.py").returncode == 0
    assert _cli(tmp_path, "is-forced", "/abs/x.py").stdout.strip() == "0"
```

Run red: `python -m pytest tests/test_queues.py -q -k forced`

**Implement** — in `scripts/queues.py`, after the `clear_note` function (line 138), add:

```python
def forced_file(identity: str) -> Path:
    """State-dir side-car flag marking an identity as explicitly force-enqueued (keyed by
    a hash so a file-path identity is filesystem-safe). Its presence makes triage no-skip."""
    h = hashlib.sha1(identity.encode("utf-8")).hexdigest()[:16]
    return config.state_dir() / "forced" / f"{h}.flag"


def mark_forced(identity: str) -> None:
    p = forced_file(identity)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text("1\n", encoding="utf-8")


def is_forced(identity: str) -> bool:
    return forced_file(identity).is_file()


def clear_forced(identity: str) -> None:
    p = forced_file(identity)
    if p.is_file():
        p.unlink()
```

In `drop` (line 111-112), add `clear_forced(identity)` beside `clear_note(identity)`:

```python
    _remove(extract_file(source), identity)
    clear_note(identity)
    clear_forced(identity)
```

In `move_to_synth`, after the `_append(synth_file(source), synth_line)` line (105), add
`clear_forced(identity)` (the *note* is deliberately NOT cleared here — it carries into synth — but
the forced marker's job is done once triage is past):

```python
    _append(synth_file(source), synth_line)
    clear_forced(identity)
```

In `main()`, add three subcommands beside the note commands (after the `read-note` block, ~line 232):

```python
    if cmd == "mark-forced":      # mark-forced <identity>
        mark_forced(a[1])
        sys.exit(0)
    if cmd == "is-forced":        # is-forced <identity>  -> prints 1/0
        print("1" if is_forced(a[1]) else "0")
        sys.exit(0)
    if cmd == "clear-forced":     # clear-forced <identity>
        clear_forced(a[1])
        sys.exit(0)
```

Run green: `python -m pytest tests/test_queues.py -q` then full suite.

**Commit:** `feat(queues): forced side-car marker + mark/is/clear-forced CLI and lifecycle`

---

## Task 2 — `ingest_state.py`: `triage-forced` routing

**Test** — append to `tests/test_extract_action.py` (note: must set `STATE_DIR` so the forced
side-car lands in the tmp tree; `mark_forced` is reached via the `queues` module):

```python
def test_forced_code_is_triage_forced(tmp_path, monkeypatch):
    monkeypatch.setenv("IMPORTS_DIR", str(tmp_path))
    monkeypatch.setenv("WIKI_CONFIG", str(tmp_path / "wiki.config.yaml"))
    monkeypatch.setenv("STATE_DIR", str(tmp_path / "state"))
    import queues
    queues.mark_forced("src/main.py")
    assert ingest_state.extract_action("src/main.py") == "triage-forced"

def test_unforced_code_is_triage(tmp_path, monkeypatch):
    monkeypatch.setenv("IMPORTS_DIR", str(tmp_path))
    monkeypatch.setenv("WIKI_CONFIG", str(tmp_path / "wiki.config.yaml"))
    monkeypatch.setenv("STATE_DIR", str(tmp_path / "state"))
    assert ingest_state.extract_action("src/main.py") == "triage"

def test_forced_doc_no_import_still_extract_doc_then_triage_forced(tmp_path, monkeypatch):
    monkeypatch.setenv("IMPORTS_DIR", str(tmp_path))
    monkeypatch.setenv("WIKI_CONFIG", str(tmp_path / "wiki.config.yaml"))
    monkeypatch.setenv("STATE_DIR", str(tmp_path / "state"))
    import queues
    queues.mark_forced("docs/spec.pdf")
    assert ingest_state.extract_action("docs/spec.pdf") == "extract-doc"
    ip = ingest_state.import_path("docs/spec.pdf")
    ip.parent.mkdir(parents=True, exist_ok=True)
    ip.write_text("---\nkey: x\n---\nbody\n")
    assert ingest_state.extract_action("docs/spec.pdf") == "triage-forced"

def test_forced_jira_key_unaffected(tmp_path, monkeypatch):
    monkeypatch.setenv("IMPORTS_DIR", str(tmp_path))
    monkeypatch.setenv("WIKI_CONFIG", str(tmp_path / "wiki.config.yaml"))
    monkeypatch.setenv("STATE_DIR", str(tmp_path / "state"))
    import queues
    queues.mark_forced("CDS2ASV-1")
    assert ingest_state.extract_action("CDS2ASV-1") == "extract-jira"
```

> Note: `_cfg`-style wiki.config is not strictly needed because `config.state_dir()` honors
> `$STATE_DIR` directly. If `import queues` / `mark_forced` raises for want of config, the
> `WIKI_CONFIG` setenv lines above can point at the conftest fallback instead — adjust only if red
> for that reason.

Run red: `python -m pytest tests/test_extract_action.py -q -k forced`

**Implement** — in `scripts/ingest_state.py`:

Add `import queues` to the imports block at the top of the file.

Rewrite the tail of `extract_action` (lines 156-158) so the forced check happens *after* the base
action is computed (preserving `extract-doc`-first for a forced binary doc, and never touching the
Jira branch):

```python
    if is_doc(path):
        if not has_import(path):
            return "extract-doc"
        return "triage-forced" if queues.is_forced(path) else "triage"
    return "triage-forced" if queues.is_forced(path) else "triage"
```

Add a `"triage-forced"` line to the `extract_action` docstring describing it as "forced item:
triage runs for guidance but may not skip".

Run green: `python -m pytest tests/test_extract_action.py -q` then full suite.

**Commit:** `feat(ingest_state): route forced identities to triage-forced`

---

## Task 3 — `check_for_changes.py`: unfiltered folder expansion + forced marking

**Test** — replace the existing `test_force_folder_expansion_filters_but_named_file_is_exempt`
(lines 203-220 of `tests/test_change_to_queue.py`) with an unfiltered version, and add a
forced-marking test. Add a `diagram.png` to prove image extensions also pass:

```python
def test_force_folder_expansion_is_unfiltered(tmp_path, monkeypatch):
    repo = tmp_path / "asv"
    (repo / "src").mkdir(parents=True)
    (repo / "src" / "user.py").write_text("x=1\n")
    (repo / "src" / "x.min.js").write_text("//min\n")
    (repo / "src" / "diagram.png").write_text("png\n")
    _cfg(tmp_path, monkeypatch, repos=[str(repo)])

    import importlib, check_for_changes
    importlib.reload(check_for_changes)

    # folder expansion under --force keeps EVERYTHING (explicit intent wins)
    expanded = check_for_changes._expand_identities([str(repo / "src")])
    names = sorted(Path(p).name for p in expanded)
    assert names == ["diagram.png", "user.py", "x.min.js"]

    # a single named ignored file remains exempt (regression guard)
    named = check_for_changes._expand_identities([str(repo / "src" / "x.min.js")])
    assert [Path(p).name for p in named] == ["x.min.js"]


def test_enqueue_identities_forced_marks_each(tmp_path, monkeypatch):
    repo = tmp_path / "asv"
    (repo / ".git").mkdir(parents=True)
    f = repo / "src" / "diagram.png"
    f.parent.mkdir(parents=True)
    f.write_text("png\n")
    _cfg(tmp_path, monkeypatch, repos=[str(repo)])
    monkeypatch.setenv("STATE_DIR", str(tmp_path / "state"))
    import importlib, check_for_changes, queues
    importlib.reload(check_for_changes)

    ident = str(f.resolve())
    check_for_changes._enqueue_identities([ident], dry_run=False, verb="force-enqueue", forced=True)
    assert queues.is_forced(ident)


def test_enqueue_identities_forced_dry_run_does_not_mark(tmp_path, monkeypatch):
    repo = tmp_path / "asv"
    (repo / ".git").mkdir(parents=True)
    f = repo / "src" / "diagram.png"
    f.parent.mkdir(parents=True)
    f.write_text("png\n")
    _cfg(tmp_path, monkeypatch, repos=[str(repo)])
    monkeypatch.setenv("STATE_DIR", str(tmp_path / "state"))
    import importlib, check_for_changes, queues
    importlib.reload(check_for_changes)

    ident = str(f.resolve())
    check_for_changes._enqueue_identities([ident], dry_run=True, verb="force-enqueue", forced=True)
    assert not queues.is_forced(ident)
```

> If `repo_relative`/`source_of` require the folder to be under a configured source for these
> tests, mirror whatever the existing replaced test relied on — the original used the same `_cfg`
> repo, so this should resolve identically.

Run red: `python -m pytest tests/test_change_to_queue.py -q -k "force or forced"`

**Implement** — in `scripts/check_for_changes.py`:

In `_expand_identities`, drop the ignore filter from the directory branch (lines 188-193) and remove
the now-unused `globs = config.ignore_globs()` (line 180). Update the docstring:

```python
def _expand_identities(args: list[str]) -> list[str]:
    """Expand --force args into concrete identities: a Jira KEY stays as-is; a
    directory expands to every file beneath it (recursive), UNFILTERED; an explicitly
    named single file stays as-is. --force is "explicit intent wins": unlike detection
    and --backfill, it applies NO ignore-glob filtering — files and folders behave the
    same. Paths are resolved to absolute."""
    out: list[str] = []
    for a in args:
        if sources.is_jira_key(a):
            out.append(a)
            continue
        p = Path(a)
        if p.is_dir():
            for f in sorted(p.rglob("*")):
                if f.is_file():
                    out.append(str(f.resolve()))
        elif p.exists():
            out.append(str(p.resolve()))   # named file
        else:
            out.append(a)   # not on disk — let source_of raise a clear error
    return out
```

In `_enqueue_identities`, add a `forced` param and mark each identity after enqueue (not on
dry-run):

```python
def _enqueue_identities(identities: list[str], dry_run: bool, verb: str,
                        ignored: dict[str, int] | None = None,
                        forced: bool = False) -> None:
    ...
        if not dry_run:
            queues.enqueue(source, identity)
            if forced:
                queues.mark_forced(identity)
        n += 1
    ...
```

At the `--force` call site (line 268), pass `forced=True`:

```python
        _enqueue_identities(_expand_identities(args), dry_run, "force-enqueue", forced=True)
```

(`--backfill` keeps the default `forced=False`; `test_enqueue_identities_reports_ignored_summary`
still passes because `forced` defaults to `False`.)

Run green: `python -m pytest tests/test_change_to_queue.py -q` then full suite.

**Commit:** `feat(check_for_changes): --force folder expansion is unfiltered and marks forced`

---

## Task 4 — driver branch + `forced-triage-prompt.md` (docs, review-verified)

No unit tests — skill/prompt text is verified by review per the spec.

**Create** `skills/wiki-ingest/forced-triage-prompt.md`:

```markdown
# FORCED-TRIAGE PREAMBLE (prepended to triage-prompt.md)

This file was **explicitly force-enqueued** by the user. It is in the queue on purpose
and the keep/skip decision is **already made** — you may **NOT** skip it.

Override rule 1 (keep-or-skip) of the triage prompt below: do not return `SKIP`. Do the
rest of your job normally — judge density (`dense` vs `routine`) from what you can read,
and write the one-line focus note pointing the synthesizer at the business value. For a
diagram or image (the Read tool renders PNG/JPG/GIF visually), describe what it depicts
and its business meaning.

Return `KEEP | <dense|routine> | <note>` — never `SKIP`.
```

**Edit** `skills/wiki-ingest/SKILL.md` — add a `triage-forced` bullet immediately after the
`triage` bullet (after line 53), mirroring it but no-skip:

```markdown
- **`triage-forced`** → identical to `triage`, but the identity was explicitly force-enqueued and
  may NOT be dropped. Spawn one Haiku subagent per identity with `forced-triage-prompt.md`
  prepended to `triage-prompt.md` (same prepend pattern as `escalation-prompt.md` + `extract-prompt.md`).
  Act on the return line in `next-extract` order:
  - `KEEP | <flag> | <note>` → exactly as `triage`: `wc -l` the classify `read_target`; if the note
    is not `-`, `write-note`; then `queues.py extracted <source> <identity> --lines <N> --flag <flag>`
    (which clears the forced marker).
  - `SKIP | <reason>` (a forced item must never be dropped) → coerce to `KEEP | routine | <reason>`
    and take the KEEP path above. Do NOT call `drop`.
  - `FAILED` → retry once; if it fails again, leave pending and continue.
```

Review checklist (manual): preamble forbids SKIP; driver coerces stray SKIP; KEEP path identical to
`triage`; `extracted` clears the marker (Task 1); no `drop` reachable on a forced item.

**Commit:** `feat(wiki-ingest): triage-forced driver branch + forced-triage-prompt`

---

## Task 5 — docs + version bump (review-verified)

No unit tests.

- **`skills/wiki-queue/SKILL.md`** — on the `/wiki-queue <path|folder>` bullet (lines 25-27), note
  that `--force` is "explicit intent wins": it enqueues every file unfiltered (folders included) and
  marks them undroppable by triage, in contrast with detection/backfill which filter.
- **`skills/wiki-init/templates/wiki.config.yaml.tmpl`** — near the `ignore:` block comment, add a
  line noting the escape hatch: a genuinely valuable ignored asset (e.g. an architecture PNG) can be
  forced in via `/wiki-queue <path>` or `/wiki-queue <folder>`, which bypasses these globs.
- **`README.md`** — in the "Ignore filtering" note (lines 117-123), add that `/wiki-queue <path|folder>`
  (`--force`) is the override for genuinely valuable assets/images: it skips the ignore filter
  entirely (folders included) and the forced items are triaged-for-guidance but never dropped.
- **`.claude-plugin/plugin.json`** — bump `version` `0.3.0` → `0.4.0`.

Review checklist (manual): all four files updated; version is `0.4.0`; wording consistent with the
spec's "explicit intent wins" framing.

**Commit:** `docs: document force-enqueue override; bump plugin to 0.4.0`

---

## Done criteria

- `python -m pytest -q` green.
- A forced folder containing a `.png`/`.min.js` enqueues all files and marks each forced.
- `extract-action` returns `triage-forced` for a forced code/prose/image (and for a forced doc once
  its import exists); `extract-doc`-first and the Jira branch are preserved.
- The forced marker is cleared on `extracted`/`drop`; the note still carries into synth.
- Detection and `--backfill` behavior unchanged (regression guards green).
- Plugin version `0.4.0`.
