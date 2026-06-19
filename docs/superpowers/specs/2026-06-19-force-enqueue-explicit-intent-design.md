# Force-enqueue: explicit intent wins

**Date:** 2026-06-19
**Status:** Approved design — ready for implementation plan
**Plugin version:** 0.3.0 → 0.4.0

## Problem

The ingest pipeline drops files at two independent gates:

1. **Enqueue filter** — `config.ignore_globs()` (baked `_IGNORE_DEFAULTS` + the consumer
   repo's `ignore:` list) is applied during detection, `--backfill` expansion, and
   `--force` *folder* expansion. The baked defaults drop binary assets, including images
   (`**/*.png`, `**/*.jpg`, `**/*.jpeg`, `**/*.gif`, `**/*.svg`, `**/*.ico`). The user
   `ignore:` list is **add-only** — there is no un-ignore, so a `.png` can never be
   whitelisted back in via config.
2. **Haiku triage** — during extract→synth, the Haiku triage subagent may return
   `SKIP`, dropping the file before synthesis.

Consequence: a genuine, business-relevant asset — e.g. a folder of architectural
diagram PNGs — cannot be ingested. There is no escape hatch.

Two facts about the current code shape the fix:

- In `check_for_changes._expand_identities`, a **single named file** passed to `--force`
  is **already exempt** from the ignore filter (`check_for_changes.py:194-195`, "named
  file — exempt"). Only **folder expansion** still filters each file
  (`check_for_changes.py:191-193`).
- An image that does reach a subagent is read via the Read tool, which **renders
  PNG/JPG/GIF visually**. So a Haiku triage subagent and the Sonnet synth subagent can
  actually *see* a diagram and describe it — the machinery to extract a diagram's
  business value already exists; the file just never survives the two gates.

## Goal

Make `/wiki-queue <path|folder>` (the `--force` path) a deliberate **"explicit intent
wins"** override:

- **Nothing it enqueues is filtered at enqueue** — file *or* folder, any extension,
  including images and otherwise-ignored assets.
- **Nothing it enqueues can be dropped by the Haiku triage.** Haiku still *triages* each
  forced file — it reads it and produces a density flag + focus note to guide synth —
  but the keep/skip decision is removed: a forced file is always kept.

Out of scope (explicit user decisions during design):

- Detection (`--jira` / `--code` / default scan) and `--backfill` are **unchanged** —
  they still filter. Skipping junk there is desirable.
- A forced **folder is truly blind** — it skips *nothing* (no junk denylist under
  `--force`), consistent with how a single named file already behaves. The user controls
  scope by choosing which folder to point at.
- **No new `image` kind.** No vision-specific prompts, no `media_gap` route. Images flow
  through classified as `code` and are read visually by the triage and synth subagents.

## Design

### 1. Folder expansion stops filtering — `scripts/check_for_changes.py`

In `_expand_identities`, the directory branch currently filters each file through
`ignore.first_match` before appending it. Remove that filter: append **every** file
beneath the folder. The single-file branch (already exempt) is unchanged. The result:
`--force` is uniformly "explicit intent wins" — files and folders behave the same.

Update the docstring to state that `--force` does not filter (folders included), in
contrast with `--backfill` and detection.

### 2. A "forced" marker — `scripts/queues.py`

Add a hash-keyed side-car set under `state/forced/<hash>.flag`, mirroring the existing
`note` side-car (`note_file` / `read-note` / `write-note` / `clear_note`). New helpers:

- `forced_file(identity) -> Path` — `config.state_dir() / "forced" / "<hash8>.flag"`.
- `mark_forced(identity)` — create the side-car.
- `is_forced(identity) -> bool` — does it exist?
- `clear_forced(identity)` — remove it (idempotent).

Plus CLI subcommands in `queues.py main()` for the marker, matching the existing
note/queue command surface (e.g. `mark-forced <identity>`, `is-forced <identity>`),
so the enqueue path and any tooling can set/query it without importing the module.

**Lifecycle.** The marker exists only to gate the triage, so it is cleared wherever the
identity leaves `.extract`:

- `drop(...)` — add `clear_forced(identity)` beside the existing `clear_note(identity)`.
- `move_to_synth(...)` (the `extracted` CLI) — add `clear_forced(identity)`. (Note: the
  *note* side-car is deliberately **not** cleared here — it carries into synth as a hint
  — but the forced marker is, since its job is done once triage is past.)
- `enqueue(...)` — does **not** touch the forced marker. The `--force` path sets it
  explicitly after enqueue; a normal detection enqueue of the same identity simply leaves
  any existing marker, which is harmless (an explicitly-forced item that is later
  re-detected stays kept — the desired behavior).

Rationale for a side-car over a queue-line metadata prefix: `extract-action` is invoked
with only `<identity>` and is the single source of truth the markdown driver consults.
A side-car lets `extract_action` answer "forced?" without changing `next-extract`'s
output format or the driver's line parsing.

### 3. Forced-aware routing — `scripts/ingest_state.py`

`ingest_state` may safely `import queues` (verified: `queues` does not import
`ingest_state`, so no cycle).

`extract_action(identity)`: compute the base action as today, then — when the base
action is `triage` and `queues.is_forced(identity)` — return the new action
**`triage-forced`** instead of `triage`.

Key subtlety preserved by checking *after* the base action:

- A forced **binary doc** with no import yet still returns `extract-doc` first (it must
  be converted), and only becomes `triage-forced` on the next pass once its import exists.
- A forced **Jira key** is unaffected — it routes `extract-jira` / `reextract-jira` /
  `ready`, never `triage`, so `triage-forced` never triggers for it (and its forced
  marker is cleared when it is marked `extracted`).
- Forced **code / prose / image** → `triage-forced`.

Document `triage-forced` in the `extract_action` docstring.

### 4. Forced triage runs but cannot skip — `skills/wiki-ingest/`

**New driver branch in `SKILL.md`** (Phase 1, alongside `triage`):

> **`triage-forced`** → spawn one Haiku triage subagent per identity exactly like
> `triage`, but prepend `forced-triage-prompt.md` to `triage-prompt.md` (the same
> prepend pattern used for `escalation-prompt.md` + `extract-prompt.md` on re-extract).
> The subagent returns `KEEP | <flag> | <note>` — take the normal KEEP path: compute the
> line count mechanically (`wc -l` on the classify `read_target`); if the note is not
> `-`, `queues.py write-note <identity> <note>`; then
> `queues.py extracted <source> <identity> --lines <N> --flag <flag>` (which clears the
> forced marker). **Defensive:** if a forced subagent nonetheless returns
> `SKIP | <reason>`, coerce it to `KEEP | routine | <reason>` — a forced item is never
> dropped. `FAILED` is retried once, as with normal triage.

**New file `skills/wiki-ingest/forced-triage-prompt.md`** — a short preamble that
overrides rule 1 (keep-or-skip) of the triage prompt:

> This file was **explicitly force-enqueued** by the user — it is in the queue on
> purpose, and the keep/skip decision is already made. You may **NOT** skip it. Do the
> rest of your job normally: judge density (`dense` vs `routine`) from the content you
> can read, and write the one-line focus note telling the synthesizer where the business
> value is (for a diagram or image, describe what it depicts and the business meaning).
> Return `KEEP | <dense|routine> | <note>` — never `SKIP`.

So Haiku still **looks** at every forced file (a mixed folder of docs, code, images, and
junk all get read) and hands the synth orchestrator a density flag and focus note — it
simply may not discard anything.

## Data flow

```
/wiki-queue diagrams/
  → check_for_changes.py --force diagrams/
     → _expand_identities: every file beneath diagrams/, NO ignore filter
     → _enqueue_identities(forced=True): queues.enqueue(src, id) + queues.mark_forced(id)

/wiki-ingest
  → next-extract → extract-action <arch.png>  → "triage-forced"
     → Haiku triage subagent (forced-triage-prompt + triage-prompt):
          reads arch.png (rendered visually) → KEEP | dense | "auth service topology, trust boundaries"
     → wc -l; write-note; queues extracted <src> <arch.png> --lines N --flag dense   (clears forced)
  → synth: Sonnet reads arch.png via Read (rendered) + the focus note → wiki page
```

A forced folder of mixed content behaves uniformly: each file is enqueued unfiltered,
each is triaged-for-guidance, none is dropped.

## Components touched

| File | Change |
|------|--------|
| `scripts/check_for_changes.py` | `_expand_identities`: folder branch stops filtering. `_enqueue_identities`: add `forced: bool` param; `--force` passes `True` and calls `queues.mark_forced` per enqueued identity (not on dry-run); `--backfill` passes `False`. Docstring. |
| `scripts/queues.py` | `forced_file` / `mark_forced` / `is_forced` / `clear_forced`; CLI subcommands; `clear_forced` calls in `drop` and `move_to_synth`. |
| `scripts/ingest_state.py` | `import queues`; `extract_action` returns `triage-forced` for forced base-`triage` identities; docstring. |
| `skills/wiki-ingest/SKILL.md` | New `triage-forced` driver branch. |
| `skills/wiki-ingest/forced-triage-prompt.md` | **New** no-skip preamble. |
| `skills/wiki-queue/SKILL.md` | Document `/wiki-queue <path|folder>` as "explicit intent wins" — unfiltered + undroppable; contrast with detection/backfill. |
| `skills/wiki-init/templates/wiki.config.yaml.tmpl` | Comment near the `ignore:` block noting the `--force` override escape hatch. |
| `README.md` | Document the override path for genuinely valuable assets/images. |
| `.claude-plugin/plugin.json` | Version 0.3.0 → 0.4.0. |

## Testing (TDD)

- **`check_for_changes`** — `_expand_identities` on a directory containing a `.png` (and
  other normally-ignored files) yields all of them in the identity list (no filtering).
  A single named ignored file remains exempt (regression guard). `--backfill` still
  filters (regression guard).
- **`queues`** — `mark_forced` / `is_forced` / `clear_forced` roundtrip; `is_forced` is
  `False` for an unmarked identity; `drop` clears the marker; `move_to_synth` clears the
  marker; CLI subcommands behave.
- **`ingest_state`** — `extract_action` returns `triage-forced` for a forced
  code/prose/image identity; returns `extract-doc` for a forced binary doc with no
  import, then `triage-forced` once the import exists; returns the normal action for an
  unforced identity; forced Jira key still routes `extract-jira`.

Prompt/skill text changes (`SKILL.md`, `forced-triage-prompt.md`, README, template) are
documentation and are verified by review, not unit tests.

## Risks / notes

- **Foot-gun (accepted):** a forced folder pointing at a tree containing `node_modules/`
  or build output will enqueue all of it. Mitigation is user-side: scope the folder you
  pass. This is the explicit "truly blind" choice.
- **`wc -l` on a binary image** yields a meaningless but harmless count used only for
  synth batching; the forced file is kept regardless.
- **No circular import:** `ingest_state` → `queues` is safe (`queues` imports only
  `config`, `sources`).
