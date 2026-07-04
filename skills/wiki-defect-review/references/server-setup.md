# Server setup — automated defect review

The reviewer is a **read-only consumer of the wiki content service** that
already exists on the server for `domain-expert-app`:

- content checkouts under `$WIKI_INDEX_ROOT/*/` (one per product);
- a unified qmd index at `$WIKI_INDEX_ROOT/.qmd` with `<prefix>__wiki` /
  `<prefix>__raw` collections;
- the app's `domain-expert-update.timer` (15 min) pulling all checkouts and
  refreshing the index in the same run.

The reviewer NEVER: runs `git pull`, runs `qmd update`/`qmd embed`, or
writes a tracked file in any checkout (the sync is fail-loud on dirty
trees — a dirtied checkout breaks refresh for every consumer). Its own
files (state, temp attachments) are untracked and live in each wiki's
`config_dir`, outside the repos.

## Prerequisites

1. Claude Code CLI installed, plus the `domain-expert` plugin.
2. Auth on the server: `claude setup-token` (subscription) or
   `ANTHROPIC_API_KEY` in the wrapper's environment.
3. Permissions for headless runs: a non-interactive `claude -p` cannot answer
   permission prompts. In each wiki checkout, pre-approve what the skill
   runs — the plugin's `python "${CLAUDE_PLUGIN_ROOT}/scripts/…"` commands,
   `qmd` searches, and temp-file writes — via `.claude/settings.json`
   permission allow rules (test interactively first), or make an explicit,
   recorded decision to run the cron with `--dangerously-skip-permissions`
   on this trusted, single-purpose server. Verify with one manual
   `claude -p "/wiki-defect-review --auto --dry-run"` run in one checkout
   before enabling the timer.
4. Per reviewed wiki, in `wiki.config.yaml`:

   ```yaml
   defect_review:
     enabled: true
     mode: draft                  # flip to `post` only after the draft phase earns trust
     notify_user: you@example.com
     candidate_jql: 'issuetype = Bug AND status in ("New", "Open")'
     max_question_rounds: 3
     qmd_collection_prefix: cid   # the app-registry key for THIS wiki (cid, ts, …)
   ```

5. Per reviewed wiki: `<config_dir>/jira.token` (JIRA_EMAIL/JIRA_TOKEN lines,
   chmod 600) — same layout the plugin uses everywhere.
6. Confirm each wiki's `.gitignore` covers any path the reviewer could
   create inside the checkout (it should create none — state lives in
   `config_dir` — but verify before first run).

## Wrapper script

Install as `/usr/local/bin/defect-review-all.sh` (chmod +x):

```bash
#!/usr/bin/env bash
# defect-review-all.sh — run /wiki-defect-review --auto in each enabled wiki.
# Read-only consumer of the content service: NO git pull, NO qmd maintenance.
set -uo pipefail

: "${WIKI_INDEX_ROOT:?set WIKI_INDEX_ROOT to the parent dir of the content checkouts}"
export WIKI_INDEX_ROOT

log() { printf '%s defect-review: %s\n' "$(date '+%Y-%m-%dT%H:%M:%S%z')" "$*"; }

rc=0
for d in "$WIKI_INDEX_ROOT"/*/; do
  d="${d%/}"
  [[ -f "$d/wiki.config.yaml" ]] || continue
  # Cheap enabled gate — the skill re-checks, this just skips the claude spawn.
  grep -qE '^\s*enabled:\s*true' <(sed -n '/^defect_review:/,/^[^[:space:]]/p' "$d/wiki.config.yaml") || {
    log "skip $(basename "$d") (defect_review not enabled)"; continue; }
  log "reviewing $(basename "$d")"
  ( cd "$d" && claude -p "/wiki-defect-review --auto" ) || {
    log "ERROR: review failed in $(basename "$d")"; rc=1; }
done
exit $rc
```

## Cron

```
*/5 * * * * WIKI_INDEX_ROOT=/srv/wikis flock -n /run/defect-review.lock /usr/local/bin/defect-review-all.sh >> /var/log/defect-review.log 2>&1
```

- 5-minute cadence; the 10-minute cool-down is enforced by the scanner
  itself — the two knobs are independent.
- `flock -n` skips a tick while the previous run is still going.

## Rollout order

1. Prove the prompt interactively on the dev machine against real cid-wiki
   tickets: thin report, out-of-scope, exact dupe, near dupe, clean defect.
2. On the server: enable cid-wiki only, run once by hand with
   `--auto --dry-run`, read every decision.
3. Enable the cron with `mode: draft`. Read the notify emails for a week or
   two; paste the good ones.
4. Flip cid-wiki to `mode: post` when the drafts are consistently
   paste-worthy. Enable ts-wiki (`enabled: true`) when ready.

## Verify before first live run

- qmd concurrent reads: with the app up, run a search from `$WIKI_INDEX_ROOT`
  while `qmd_sync` runs; confirm no errors/locks.
- Notify API: `python jira_utils.py <KEY> --notify --subject test --body-file /tmp/t.md --to you@example.com`
  on a throwaway ticket; confirm the email arrives and nothing shows on the
  ticket.
