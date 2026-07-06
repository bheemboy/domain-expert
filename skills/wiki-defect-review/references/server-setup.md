# Server setup — automated defect review

The server runs three sibling components, each its own repo:

| Repo | Role |
|---|---|
| `domain-expert-wiki-mgr` | content service: checkouts under `$WIKI_INDEX_ROOT/*/`, the registry, the unified qmd index (`<prefix>__wiki` / `<prefix>__raw`), one 15-min sync timer |
| `domain-expert-app` | Q&A web app (independent consumer) |
| `domain-expert-defect-reviewer` | the reviewer's scheduler: `defect-review-all.sh` + a 5-min systemd timer running `claude -p "/wiki-defect-review --auto"` per enabled wiki |

The reviewer is a **read-only consumer of the content service**.

The reviewer NEVER: runs `git pull`, runs `qmd update`/`qmd embed`, or
writes a tracked file in any checkout (the sync is fail-loud on dirty
trees — a dirtied checkout breaks refresh for every consumer). Its own
files (state, temp attachments) are untracked and live in each wiki's
`config_dir`, outside the repos.

## Prerequisites

**Install order:** `domain-expert-wiki-mgr` first (its README: content
clones, registry, first index build, sync timer), then the reviewer via
`domain-expert-defect-reviewer` (its README: wrapper script + systemd
units + install commands). This doc is the *contract and rollout* — what
the reviewer needs configured and how to earn trust; the install
mechanics live in those two READMEs.

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
   recorded decision to run the sweep with `--dangerously-skip-permissions`
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

5. Per reviewed wiki: `<config_dir>/jira.token` (chmod 600) — same layout
   the plugin uses everywhere; start from the plugin's
   `skills/wiki-init/templates/jira.token.example`.
6. Confirm each wiki's `.gitignore` covers any path the reviewer could
   create inside the checkout (it should create none — state lives in
   `config_dir` — but verify before first run).

## Scheduler

The canonical wrapper (`defect-review-all.sh`) and its systemd units live
in the `domain-expert-defect-reviewer` repo — install per its README. What
they do, which is the contract this skill relies on:

- every 5 minutes (systemd timer, oneshot — runs never overlap), iterate
  `$WIKI_INDEX_ROOT/*/`, skipping wikis without `defect_review.enabled: true`;
- per enabled wiki, derive the qmd collection prefix from the registry and
  export it as `$WIKI_QMD_PREFIX`, then run
  `claude -p --model "${DEFECT_REVIEW_MODEL:-opus}" "/wiki-defect-review --auto"`
  from inside that checkout;
- never `git pull`, never qmd maintenance, never write tracked files —
  the content service owns all of that;
- one wiki failing logs an ERROR and the sweep continues, exiting non-zero
  at the end so the unit shows in `systemctl --failed`.

The 5-minute cadence and the skill's 10-minute settle cool-down are
independent knobs: the timer is how often the bot looks; the scanner
decides what qualifies.

## Rollout order

1. Prove the prompt interactively on the dev machine against real cid-wiki
   tickets: thin report, out-of-scope, exact dupe, near dupe, clean defect.
2. On the server: enable cid-wiki only, run once by hand with
   `--auto --dry-run`, read every decision.
3. Enable the timer with `mode: draft`. Read the notify emails for a week or
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
