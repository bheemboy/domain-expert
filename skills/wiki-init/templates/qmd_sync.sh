#!/usr/bin/env bash
# Bring the qmd index to a ready, fully-embedded state (idempotent).
#
# First bootstraps the project-local index if needed: `qmd init` (non-destructive)
# and ensures the `raw`/`wiki` collections exist. Then runs `qmd update` once to
# re-index collections (pick up file changes,
# register new/changed docs as pending-embed, drop removed ones). Then re-runs
# `qmd embed` until `qmd status` reports zero pending.
#
# Each `qmd embed` invocation is capped at a 30-minute session and commits
# progress incrementally, so a cap-out is harmless: only not-yet-embedded docs
# are retried on the next pass.
#
# Run from the wiki repo root, in your own terminal (NOT via the agent — the
# first build can take hours and would exceed tool timeouts). Re-runnable.
#
# Usage: ./qmd_sync.sh [extra qmd embed args...]
#   e.g. ./qmd_sync.sh -c raw
#   long first build: nohup ./qmd_sync.sh > qmd_sync.log 2>&1 &
#
# Env:
#   QMD_PULL=1   pass --pull to `qmd update` (git pull collections first)
#   QMD_SKIP_UPDATE=1   skip the update step, go straight to embedding
#
# On CPU, leave --max-batch-mb at its default (64 MB); a tiny cap only adds
# overhead and slows each pass.

set -euo pipefail

ensure_collection() {  # ensure_collection <path> <name>
  local path="$1" name="$2"
  if qmd collection list 2>/dev/null | grep -qE "^${name} \("; then
    printf '%s — collection %s already present; skipping.\n' "$(date +%T)" "$name"
  else
    printf '%s — adding collection %s (%s)...\n' "$(date +%T)" "$name" "$path"
    qmd collection add "$path" --name "$name"
  fi
}

# Bootstrap (idempotent): create the project-local index once, then ensure the
# expected collections exist. `qmd init` is non-destructive (preserves any
# existing collections/index), but `qmd collection add` errors on a name that
# already exists, so guard it via ensure_collection to stay re-runnable.
[[ -d .qmd ]] || qmd init
ensure_collection raw  raw
ensure_collection wiki wiki

if [[ "${QMD_SKIP_UPDATE:-}" == "1" ]]; then
  printf '%s — skipping update (QMD_SKIP_UPDATE=1).\n' "$(date +%T)"
else
  printf '%s — refreshing index (qmd update)...\n' "$(date +%T)"
  if [[ "${QMD_PULL:-}" == "1" ]]; then
    qmd update --pull
  else
    qmd update
  fi
fi

pass=0
while qmd status | grep -qE 'Pending: +[1-9]'; do
  pass=$((pass + 1))
  pending=$(qmd status | grep -oE 'Pending: +[0-9]+' | grep -oE '[0-9]+')
  printf '%s — pass %d starting (%s docs pending)...\n' "$(date +%T)" "$pass" "$pending"
  # Don't let a non-zero pass (cap-out, transient error) abort the drain under
  # `set -e`; the loop re-runs on whatever is still pending.
  qmd embed "$@" || printf '%s — pass %d exited non-zero; retrying.\n' "$(date +%T)" "$pass"
done

printf '%s — all embeddings complete after %d pass(es).\n' "$(date +%T)" "$pass"
