---
name: wiki-ingest
description: Drain the wiki work queues (extract → synth) into the wiki. Use to ingest queued Jira/docs/code. Source scans and queue inspection live in wiki-queue.
---

# wiki-ingest (extract → synthesize)

## Role

Orchestrate the full ingest pipeline over the per-source queues (`scripts/queues.py`):
optional source scan → parallel extract → serialized synthesize. Schema: `CLAUDE.md`
§1, §3, §4, §5, §6, §7.

## Argument forms

- `/wiki-ingest` — drain all pending (extract ≤all, then synth ≤all).
- `/wiki-ingest <N>` — per-phase budget N (extract ≤N, then synth ≤N).
- `/wiki-ingest <path|folder> …` — one-step convenience: force-enqueue the paths
  (`python "${CLAUDE_PLUGIN_ROOT}/scripts/check_for_changes.py" --force <args…>`, folders
  expand recursively — unfiltered and undroppable by triage, same as `/wiki-queue <path>`),
  then drain all.

**Cold-start (the no-path forms only).** Before draining, run
`python "${CLAUDE_PLUGIN_ROOT}/scripts/queues.py" status`; if
`pending_extract=0 pending_synth=0`, run
`python "${CLAUDE_PLUGIN_ROOT}/scripts/check_for_changes.py"` first. If still empty,
report "nothing to do" and stop. If non-empty on entry, drain without scanning.
For force-enqueue, a scoped source scan, backfill, or status, use `/wiki-queue`.

## Phase 1 — Extract (parallel)

`FANOUT=8` (Haiku), `ESC_FANOUT=4` (Sonnet).

Loop until budget reached or `python "${CLAUDE_PLUGIN_ROOT}/scripts/queues.py" next-extract <N>` is empty.
Dispatch each `<source>\t<identity>` line on
`python "${CLAUDE_PLUGIN_ROOT}/scripts/ingest_state.py" extract-action <identity>`:

- **`ready`** → `python "${CLAUDE_PLUGIN_ROOT}/scripts/queues.py" extracted <source> <identity>`. Covers
  a Jira clean import already present from an interrupted run.
- **`extract-doc`** → batch all doc paths; run `python "${CLAUDE_PLUGIN_ROOT}/scripts/extract_docs.py"
  <paths...>` once. **Run it as a background task** (Bash `run_in_background`), never
  foreground: docling conversion is CPU-bound (~11 s/page; a large PDF batch runs for
  hours) and a foreground call dies at the Bash timeout cap. The script is resumable —
  each import is written as it completes and already-imported files are skipped — so an
  interrupted run just re-launches. Wait for the completion notification before
  continuing the loop. Do NOT call `extracted` here — leave each doc in `.extract`.
  Once its import exists, `extract-action` returns `triage`, so the same loop re-picks
  it on its next pass and triages the converted markdown like any other kept source.
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
- **`triage-forced`** → identical to `triage`, except the identity was explicitly
  force-enqueued and may NOT be dropped: prepend `forced-triage-prompt.md` to
  `triage-prompt.md` (same prepend pattern as `escalation-prompt.md` + `extract-prompt.md`)
  and handle the return lines exactly as in `triage`, with ONE exception —
  `SKIP | <reason>` is coerced to `KEEP | routine | <reason>` and takes the KEEP
  path (never call `drop`; the `extracted` call clears the forced marker).
- **`extract-jira`** → spawn one Haiku subagent per key (Agent tool,
  `subagent_type: general-purpose`, `model: haiku`) with `extract-prompt.md`
  (substitute `<KEY>`). ≤FANOUT in parallel in a single message; wait for all.
- **`reextract-jira`** → spawn one Sonnet subagent per key with
  `escalation-prompt.md` prepended to `extract-prompt.md`. ≤ESC_FANOUT in
  parallel; wait for all.

After a full wave returns:

- `EXTRACTED`/`EMPTY` → `python "${CLAUDE_PLUGIN_ROOT}/scripts/jira_utils.py" <KEY> --stamp-hash`, then
  stamp the import's length and mark extracted:
  `python "${CLAUDE_PLUGIN_ROOT}/scripts/queues.py" extracted jira <KEY> --lines "$(wc -l < "$(python "${CLAUDE_PLUGIN_ROOT}/scripts/ingest_state.py" import-path <KEY>)")" --flag routine`.
  (Jira imports default to `routine`; the density flag is a code/prose/doc signal.)
- `ESCALATE` → leave in `.extract` (do NOT call `extracted`); auto-swept as
  `reextract-jira` on next read.
- `FAILED` → retry once; if it fails again, leave pending and continue.

**Chronological invariant (do NOT violate).** Mark jira keys `extracted` in the
order `next-extract` returned them — never in subagent-completion order. Wait for
a whole wave, then mark in original order. This keeps `jira.synth` resolution-ordered
so newer supersedes older (CLAUDE.md §4.3).

## Phase 2 — Synthesize (serial)

`LINT_DELTA_PAGES=25` (the delta lint gate fires when the pending changed-page set
reaches this size — see step 3; tunable). Batch sizes and model routing come from
`python "${CLAUDE_PLUGIN_ROOT}/scripts/config.py"`-backed tuning
(`config.synth_tuning()`); a queue line with no metadata falls back to a batch of
`default_batch` (12) on Sonnet.

**Invariants:** STRICTLY SERIALIZED — exactly one subagent in flight, ever. Synth
and lint subagents share `wiki/`, `index.md`, `log.md`; overlap corrupts them.

**Index refresh (qmd):** `qmd update && qmd embed --max-batch-mb 1` at start and end of
run. If missing or failing, continue and note `qmd-unavailable` — staleness is
acceptable, a blocked ingest is not.

Chronological order is guaranteed by the extract invariant above; synth processes
the queue front-to-back (oldest → newest).

Run the start-of-run index refresh, then loop until budget reached or
`python "${CLAUDE_PLUGIN_ROOT}/scripts/queues.py" next-synth <N>` is empty:

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
2. Act:
   - `SYNTHED | completed: <id> ...` → for each id run
     `python "${CLAUDE_PLUGIN_ROOT}/scripts/queues.py" synthed <source> <id>`.
   - `NEEDS-INPUT | <question>` → STOP; surface verbatim.
   - `FAILED` → retry once with a fresh subagent; else STOP (mark only confirmed ids).
3. **Lint gate (delta, size-gated)** — only when no synth subagent is running. After each
   batch, size the pending delta and lint when it is big enough (not on a fixed source
   count):
   a. `D=$(python "${CLAUDE_PLUGIN_ROOT}/scripts/lint_scope.py" delta --count)` → the size of
      the pending changed-since-last-lint page set (neighbor-expanded), as an integer.
   b. Run the gate when **`D ≥ LINT_DELTA_PAGES` (default 25)**, or this is the **end of the
      run** and `D > 0`. Otherwise skip and keep synthesizing — the delta carries forward and
      is re-sized after the next batch. (`D` self-bounds: each lint writes a `lint | auto`
      line, resetting the watermark, so the next delta starts fresh. On a small wiki `D`
      rarely reaches the threshold mid-run, so the gate effectively runs once at end; on a
      large wiki it fires periodically as real volume accumulates.)
   c. `python "${CLAUDE_PLUGIN_ROOT}/scripts/lint_wiki.py"`.
   d. `python "${CLAUDE_PLUGIN_ROOT}/scripts/lint_scope.py" delta` → the page list itself (one
      slug per line). Spawn one Opus subagent (`model: opus`) with
      `${CLAUDE_PLUGIN_ROOT}/prompts/lint-prompt.md`, filling the `## Scope` **delta** option
      with that page list (from step d) and the mechanical output. It records a
      `- lint | auto` bullet in `log.md` (prepended under today's date heading,
      newest first). Wait. `CLEAN`/`FIXED` → continue; `BLOCKED` → STOP.

## Report

Print `python "${CLAUDE_PLUGIN_ROOT}/scripts/queues.py" status` and pages touched. `/wiki-ingest` resumes
cleanly because queue state is durable.

## Note on lint

Forward semantic `/lint` is run on demand, not per trickle — the per-batch lint gate
above is sufficient for ongoing ingests.
