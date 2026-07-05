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

**The content service half is not set up here.** Checkouts under
`$WIKI_INDEX_ROOT`, the registry, the unified qmd index build, and the
sync/update timers are installed per the app repo's
`deploy/README-deploy.md` (§1a–1g: node + qmd CLI, content clones,
registry.yaml, first index build, systemd units). This doc covers only
what the *reviewer* adds on top.

1. Install the reviewer's toolchain (the app does not provide these):
   - **Claude Code CLI** — same installer you used on dev; verify with
     `claude --version` as the service user.
   - **The `domain-expert` plugin** — add your plugin marketplace and
     install it exactly as on the dev machine; verify
     `/wiki-defect-review` appears in an interactive session in a wiki
     checkout.
   - **Python deps for the plugin's scripts** — `pip install requests pyyaml`
     (system or service-user python3; the wrapper's registry lookup needs
     `pyyaml` too). Do NOT install the plugin's full `requirements.txt`
     here: `docling` (~2 GB with models) is for doc ingest, which never
     runs on this server.
2. Auth on the server: `claude setup-token` (subscription) or
   `ANTHROPIC_API_KEY` in the wrapper's environment.
   **Model floor: Opus.** Side-by-side runs on real tickets showed smaller
   models produce noticeably weaker reviews. The wrapper pins
   `--model "${DEFECT_REVIEW_MODEL:-opus}"` — override the env var only to
   go *up* (e.g. a Mythos-class model), never below Opus.
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
     candidate_jql: 'issuetype = Defect AND status in ("New", "Open")'  # your project's real type/status names
     max_question_rounds: 3
   ```

   The qmd collection prefix is not a config key — the wrapper derives it
   from the registry and exports `$WIKI_QMD_PREFIX` (see below).

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
: "${DOMAIN_EXPERT_REGISTRY:?set DOMAIN_EXPERT_REGISTRY to the registry.yaml path}"
export WIKI_INDEX_ROOT

log() { printf '%s defect-review: %s\n' "$(date '+%Y-%m-%dT%H:%M:%S%z')" "$*"; }

# Registry key for a checkout (the qmd collection prefix, e.g. cid). The
# registry is the content service's single source of truth for key -> root.
prefix_for() {  # prefix_for <checkout-dir>
  python3 - "$1" <<'PY'
import sys, pathlib, os, yaml
target = pathlib.Path(sys.argv[1]).resolve()
reg = yaml.safe_load(open(os.environ["DOMAIN_EXPERT_REGISTRY"])) or {}
for w in reg.get("wikis") or []:
    if pathlib.Path(w["root"]).expanduser().resolve() == target:
        print(w["key"])
        break
PY
}

rc=0
for d in "$WIKI_INDEX_ROOT"/*/; do
  d="${d%/}"
  [[ -f "$d/wiki.config.yaml" ]] || continue
  # Cheap enabled gate — the skill re-checks, this just skips the claude spawn.
  grep -qE '^\s*enabled:\s*true' <(sed -n '/^defect_review:/,/^[^[:space:]]/p' "$d/wiki.config.yaml") || {
    log "skip $(basename "$d") (defect_review not enabled)"; continue; }
  prefix=$(prefix_for "$d")
  [[ -n "$prefix" ]] || {
    log "ERROR: $(basename "$d") enabled but not in registry $DOMAIN_EXPERT_REGISTRY"; rc=1; continue; }
  log "reviewing $(basename "$d") (qmd prefix: $prefix)"
  ( cd "$d" && WIKI_QMD_PREFIX="$prefix" claude -p --model "${DEFECT_REVIEW_MODEL:-opus}" "/wiki-defect-review --auto" ) || {
    log "ERROR: review failed in $(basename "$d")"; rc=1; }
done
exit $rc
```

## Cron

```
*/5 * * * * WIKI_INDEX_ROOT=/srv/wikis DOMAIN_EXPERT_REGISTRY=/etc/domain-expert/registry.yaml flock -n /run/defect-review.lock /usr/local/bin/defect-review-all.sh >> /var/log/defect-review.log 2>&1
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
- Notify API — from **inside a wiki checkout** (the script locates
  `wiki.config.yaml` from the working directory), with `<plugin-root>` =
  the installed plugin's path (find it via `claude plugin list` or under
  `~/.claude/plugins/`):

  ```
  cd $WIKI_INDEX_ROOT/cid-wiki
  python <plugin-root>/scripts/jira_utils.py <KEY> --notify --subject test --body-file /tmp/t.md --to you@example.com
  ```

  Use a throwaway ticket; confirm the email arrives and nothing shows on
  the ticket.
