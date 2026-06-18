---
name: wiki-ingest
description: Drain the wiki work queues (extract → synth) into the wiki. Use to ingest queued Jira/docs/code. Detection and queue inspection live in wiki-queue.
---

# wiki-ingest (extract → synthesize)

## Role

Orchestrate the full ingest pipeline over the per-source queues (`scripts/queues.py`):
optional detection → parallel extract → serialized synthesize. Schema: `CLAUDE.md`
§1, §3, §4, §5, §6, §7.

## Argument forms

- `/wiki-ingest` — drain all pending (extract ≤all, then synth ≤all).
- `/wiki-ingest <N>` — per-phase budget N (extract ≤N, then synth ≤N).
- `/wiki-ingest <path|folder> …` — one-step convenience: enqueue the paths
  (`python "${CLAUDE_PLUGIN_ROOT}/scripts/check_for_changes.py" --force <args…>`,
  folders expand recursively), then drain all.

**Cold-start (the no-path forms only).** Before draining, run
`python "${CLAUDE_PLUGIN_ROOT}/scripts/queues.py" status`; if
`pending_extract=0 pending_synth=0`, run
`python "${CLAUDE_PLUGIN_ROOT}/scripts/check_for_changes.py"` first. If still empty,
report "nothing to do" and stop. If non-empty on entry, drain without detecting.
For explicit/forced detection, scoped detection, backfill, or status, use `/wiki-queue`.

## Phase 1 — Extract (parallel)

`FANOUT=8` (Haiku), `ESC_FANOUT=4` (Sonnet).

Loop until budget reached or `python "${CLAUDE_PLUGIN_ROOT}/scripts/queues.py" next-extract <N>` is empty.
Dispatch each `<source>\t<identity>` line on
`python "${CLAUDE_PLUGIN_ROOT}/scripts/ingest_state.py" extract-action <identity>`:

- **`ready`** → `python "${CLAUDE_PLUGIN_ROOT}/scripts/queues.py" extracted <source> <identity>`. Covers
  code/prose and already-extracted imports from an interrupted run.
- **`extract-doc`** → batch all doc paths; run `python "${CLAUDE_PLUGIN_ROOT}/scripts/extract_docs.py"
  <paths...>` once; on success run `python "${CLAUDE_PLUGIN_ROOT}/scripts/queues.py" extracted <source> <path>`
  for each (`<source>` from the `next-extract` line).
- **`extract-jira`** → spawn one Haiku subagent per key (Agent tool,
  `subagent_type: general-purpose`, `model: haiku`) with `extract-prompt.md`
  (substitute `<KEY>`). ≤FANOUT in parallel in a single message; wait for all.
- **`reextract-jira`** → spawn one Sonnet subagent per key with
  `escalation-prompt.md` prepended to `extract-prompt.md`. ≤ESC_FANOUT in
  parallel; wait for all.

After a full wave returns:

- `EXTRACTED`/`EMPTY` → `python "${CLAUDE_PLUGIN_ROOT}/scripts/jira_utils.py" <KEY> --stamp-hash`, then
  `python "${CLAUDE_PLUGIN_ROOT}/scripts/queues.py" extracted jira <KEY>`.
- `ESCALATE` → leave in `.extract` (do NOT call `extracted`); auto-swept as
  `reextract-jira` on next read.
- `FAILED` → retry once; if it fails again, leave pending and continue.

**Chronological invariant (do NOT violate).** Mark jira keys `extracted` in the
order `next-extract` returned them — never in subagent-completion order. Wait for
a whole wave, then mark in original order. This keeps `jira.synth` resolution-ordered
so newer supersedes older (CLAUDE.md §4.3).

## Phase 2 — Synthesize (serial)

`DIGEST_BATCH=12`, `LINT_EVERY=20`.

**Invariants:** STRICTLY SERIALIZED — exactly one subagent in flight, ever. Synth
and lint subagents share `wiki/`, `index.md`, `log.md`; overlap corrupts them.

**Index refresh (qmd):** `qmd update && qmd embed` at start and end of run. If
missing or failing, continue and note `qmd-unavailable` — staleness is acceptable,
a blocked ingest is not.

Chronological order is guaranteed by the extract invariant above; synth processes
the queue front-to-back (oldest → newest).

Run the start-of-run index refresh, then loop until budget reached or
`python "${CLAUDE_PLUGIN_ROOT}/scripts/queues.py" next-synth <N>` is empty:

1. Spawn ONE Sonnet subagent (`model: sonnet`) with `synth-prompt.md` and the
   batch of identities. Wait.
2. Act:
   - `SYNTHED | completed: <id> ...` → for each id run
     `python "${CLAUDE_PLUGIN_ROOT}/scripts/queues.py" synthed <source> <id>`.
   - `NEEDS-INPUT | <question>` → STOP; surface verbatim.
   - `FAILED` → retry once with a fresh subagent; else STOP (mark only confirmed ids).
3. **Lint gate** — after every `LINT_EVERY` synthesized and once at end, only when
   no synth subagent is running:
   a. `python "${CLAUDE_PLUGIN_ROOT}/scripts/lint_wiki.py"`.
   b. Spawn one Opus subagent (`model: opus`) with `lint-prompt.md` and the
      mechanical output. Wait. `CLEAN`/`FIXED` → continue; `BLOCKED` → STOP.

## Report

Print `python "${CLAUDE_PLUGIN_ROOT}/scripts/queues.py" status` and pages touched. `/ingest` resumes cleanly
because queue state is durable.

## Note on lint

Forward semantic `/lint` is run on demand, not per trickle — the per-batch lint gate
above is sufficient for ongoing ingests.
