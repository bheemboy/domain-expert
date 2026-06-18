---
name: wiki-queue
description: Detect new/changed product sources and enqueue them, or inspect the work queue — without draining. Use to run detection (Jira/repos), backfill a repo or raw/ folder the first time, or check pending counts. Draining (extract→synth) is wiki-ingest.
---

# Wiki Queue (detect / enqueue / inspect — never drains)

This skill manages the per-source work queues. It **never** runs extract or synth —
that is `wiki-ingest`. Every form below maps to one script invocation. CLAUDE.md §6, §7.

## Argument forms

- `/wiki-queue` — full detection pass (Jira + external repos), enqueue what changed.
  Run `python "${CLAUDE_PLUGIN_ROOT}/scripts/check_for_changes.py"`, then print status.
- `/wiki-queue jira` — Jira-only detection (incl. first-time backlog when no cursor):
  `python "${CLAUDE_PLUGIN_ROOT}/scripts/check_for_changes.py" --jira`.
- `/wiki-queue code` — external-repo-only detection:
  `python "${CLAUDE_PLUGIN_ROOT}/scripts/check_for_changes.py" --code`.
- `/wiki-queue backfill <repo> …` — first-time load of an existing repo's tracked
  files (detection is incremental and would otherwise enqueue nothing):
  `python "${CLAUDE_PLUGIN_ROOT}/scripts/check_for_changes.py" --backfill <repo…>`.
- `/wiki-queue <path|folder> …` — enqueue a raw/ drop or ad-hoc paths WITHOUT draining
  (folders expand recursively):
  `python "${CLAUDE_PLUGIN_ROOT}/scripts/check_for_changes.py" --force <args…>`.
- `/wiki-queue status` — inspect pending counts only, no detection:
  `python "${CLAUDE_PLUGIN_ROOT}/scripts/queues.py" status`.
- `/wiki-queue --dry-run` — preview detection (fetch, no pull/queue/state writes):
  `python "${CLAUDE_PLUGIN_ROOT}/scripts/check_for_changes.py" --dry-run`.

## Procedure

1. Map the argument to exactly one command above and run it from the consumer wiki
   repo (cwd must be inside a wiki repo; the scripts discover the root via
   `wiki.config.yaml`).
2. Print the command's output verbatim, then always finish by running
   `python "${CLAUDE_PLUGIN_ROOT}/scripts/queues.py" status` so the user sees the
   resulting queue state.
3. Detection is idempotent and safe to re-run; never drain here. To process the
   queued work, tell the user to run `/wiki-ingest`.

## Report

Print the per-source pending counts (`status`) and what was enqueued. Do not call
`queues.py extracted`/`synthed` — those belong to the drain phase (`wiki-ingest`).
