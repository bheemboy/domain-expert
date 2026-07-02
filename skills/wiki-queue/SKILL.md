---
name: wiki-queue
description: Scan product sources for new/changed items and enqueue them, or inspect the work queue — without draining. Use to run a source scan (Jira/repos), backfill a repo or raw/ folder the first time, or check pending counts. Draining (extract→synth) is wiki-ingest.
---

# Wiki Queue (scan / enqueue / inspect — never drains)

This skill manages the per-source work queues. It **never** runs extract or synth —
that is `wiki-ingest`. Every form below maps to one script invocation. CLAUDE.md §6, §7.

## Argument forms

- `/wiki-queue` — inspect pending counts only, no source scan:
  `python "${CLAUDE_PLUGIN_ROOT}/scripts/queues.py" status`.
- `/wiki-queue all` — full source scan (Jira + external repos), enqueue what changed.
  The source scan skips paths matching the `ignore:` globs (built-in junk defaults + the consumer repo's `ignore:` list) and any `docs:` location that resolves inside a `sources` repo (auto-excluded to avoid a wiki→docs→wiki loop); see `wiki.config.yaml`.
  Run `python "${CLAUDE_PLUGIN_ROOT}/scripts/check_for_changes.py"`, then print status.
- `/wiki-queue jira` — Jira-only source scan (incl. first-time backlog when no cursor):
  `python "${CLAUDE_PLUGIN_ROOT}/scripts/check_for_changes.py" --jira`.
- `/wiki-queue repos` — external-repo-only source scan:
  `python "${CLAUDE_PLUGIN_ROOT}/scripts/check_for_changes.py" --code`.
- `/wiki-queue backfill <repo> …` — first-time load of an existing repo's tracked
  files (a source scan is incremental and would otherwise enqueue nothing):
  `python "${CLAUDE_PLUGIN_ROOT}/scripts/check_for_changes.py" --backfill <repo…>`.
  Backfill applies the same `ignore:` globs and docs auto-exclusion as the scan.
- `/wiki-queue <path|folder> …` — enqueue a raw/ drop or ad-hoc paths WITHOUT draining
  (folders expand recursively). **Explicit intent wins**: every file is enqueued unfiltered
  (folders included, any extension) and marked undroppable by triage — triage still reads it
  for guidance but can never skip it — unlike a source scan and backfill, which apply the `ignore:`
  globs. Sole exception: extract-owned imports (`raw/imports/` and the in-place `.md`
  beside a binary doc under `raw/`) are always skipped — their source documents carry
  the identity, so enqueueing the import would double-ingest.
  (`/wiki-ingest <path|folder>` force-enqueues identically, then drains in one step.)
  `python "${CLAUDE_PLUGIN_ROOT}/scripts/check_for_changes.py" --force <args…>`.
- `/wiki-queue --dry-run` — preview a source scan (fetch, no pull/queue/state writes); the preview applies the same `ignore:` globs and docs auto-exclusion as a real scan, so its counts match:
  `python "${CLAUDE_PLUGIN_ROOT}/scripts/check_for_changes.py" --dry-run`.

## Procedure

1. Map the argument to exactly one command above and run it from the consumer wiki
   repo (cwd must be inside a wiki repo; the scripts discover the root via
   `wiki.config.yaml`).
2. Print the command's output verbatim, then always finish by running
   `python "${CLAUDE_PLUGIN_ROOT}/scripts/queues.py" status` so the user sees the
   resulting queue state.
3. A source scan is idempotent and safe to re-run; never drain here. To process the
   queued work, tell the user to run `/wiki-ingest`.

## Report

Print the per-source pending counts (`status`) and what was enqueued. Do not call
`queues.py extracted`/`synthed` — those belong to the drain phase (`wiki-ingest`).
