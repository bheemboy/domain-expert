# Server setup — automated defect review

Everything server-side lives in **one repo**, `domain-expert-server`:

| Component | Where | Role |
|---|---|---|
| wiki-mgr | container (compose stack) | content service: checkouts under `$WIKI_INDEX_ROOT/*/`, the registry (`<repo>/registry.yaml`), the unified qmd index (`<prefix>__wiki` / `<prefix>__raw`), 15-min sync loop |
| app | container (compose stack, built from `<repo>/app/`) | Q&A web app (independent consumer) |
| defect reviewer | **host process**, `<repo>/defect-reviewer/` | `defect-review-all.sh` + a 5-min systemd timer running `claude -p "/wiki-defect-review --auto"` per enabled wiki |

The reviewer runs on the host (not in a container) because Claude Code
subscription auth wants a host login; the stack bind-mounts content from
real host paths precisely so a host process sees the same tree.

The reviewer is a **read-only consumer of the content service**.

The reviewer NEVER: runs `git pull`, runs `qmd update`/`qmd embed`, or
writes a tracked file in any checkout (the sync is fail-loud on dirty
trees — a dirtied checkout breaks refresh for every consumer). Its own
files (state, temp attachments) are untracked and live in each wiki's
`config_dir`, outside the repos.

## Prerequisites

**Install order:** the compose stack first (the server repo's root README:
content clones, registry, first index build, wiki-mgr running), then the
reviewer per `<repo>/defect-reviewer/README.md` (wrapper script + systemd
units + install commands). This doc is the *contract and rollout* — what
the reviewer needs configured and how to earn trust; the install mechanics
live in those two READMEs.

1. Install the reviewer's toolchain (the containers do not provide these):
   - **Claude Code CLI** — same installer you used on dev; verify with
     `claude --version` as the service user. Needs ≥ 2.1.x
     (`--permission-mode dontAsk`, `--settings`).
   - **The `domain-expert` plugin** — add your plugin marketplace and
     install it exactly as on the dev machine; verify
     `/wiki-defect-review` appears in an interactive session in a wiki
     checkout.
   - **Python deps for the plugin's scripts** — `pip install requests pyyaml`
     (system or service-user python3; the wrapper's registry lookup needs
     `pyyaml` too). Do NOT install the plugin's full `requirements.txt`
     here: `docling` (~2 GB with models) is for doc ingest, which never
     runs on this server.
   - **qmd on the host** — same major version as the stack's images.
2. Auth on the server: `claude setup-token` (subscription) or
   `ANTHROPIC_API_KEY` in the wrapper's environment.
   **Model floor: Opus.** Side-by-side runs on real tickets showed smaller
   models produce noticeably weaker reviews. The wrapper pins
   `--model "${DEFECT_REVIEW_MODEL:-opus}"` — override the env var only to
   go *up* (e.g. a Mythos-class model), never below Opus.
3. Permissions for headless runs: a non-interactive `claude -p` cannot
   answer permission prompts. The wrapper passes
   `--permission-mode dontAsk --settings <repo>/defect-reviewer/claude-settings.json`
   — an allowlist of exactly what the skill runs (the plugin's
   `python3 …/scripts/*.py` commands, `qmd` searches, temp files) plus
   deny rules for `curl`/`wget` and direct `jira.token` reads. Anything
   uncovered fails loudly rather than hanging. Do NOT substitute
   `--dangerously-skip-permissions`. After a plugin update, a sweep failure
   naming a denied command means the allowlist needs a new rule.
4. Jira credentials — a **scoped API token** so the reviewer's authority in
   Jira is bounded independently of anything Claude does: scopes
   `read:jira-work`, `read:jira-user`, `write:jira-work` only (creation
   steps in `<repo>/defect-reviewer/README.md`). Scoped tokens authenticate
   only via `https://api.atlassian.com/ex/jira/<cloudId>` — set
   `jira.api_base_url` in each wiki's `wiki.config.yaml`; `jira.base_url`
   stays the site URL. Classic tokens keep working with `api_base_url`
   unset.
5. Per reviewed wiki, in `wiki.config.yaml`:

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

6. Per reviewed wiki: `<config_dir>/jira.token` (chmod 600) — two lines,
   same as on dev: `JIRA_EMAIL=you@example.com` / `JIRA_TOKEN=<api-token>`.
7. Moving from a machine that already reviewed tickets? Copy each wiki's
   `<config_dir>/state/defect-review.json` across before the first sweep,
   or the same tickets get re-reviewed once.
8. Confirm each wiki's `.gitignore` covers any path the reviewer could
   create inside the checkout (it should create none — state lives in
   `config_dir` — but verify before first run).

## Scheduler

The canonical wrapper (`defect-review-all.sh`) and its systemd units live
in `<repo>/defect-reviewer/` — install per its README. What they do, which
is the contract this skill relies on:

- every 5 minutes (systemd timer, oneshot — runs never overlap), iterate
  `$WIKI_INDEX_ROOT/*/`, skipping wikis without `defect_review.enabled: true`;
- per enabled wiki, derive the qmd collection prefix from the registry
  (`DOMAIN_EXPERT_REGISTRY=<repo>/registry.yaml`) and export it as
  `$WIKI_QMD_PREFIX`, then run
  `claude -p --model "${DEFECT_REVIEW_MODEL:-opus}" --permission-mode dontAsk --settings <repo>/defect-reviewer/claude-settings.json "/wiki-defect-review --auto"`
  from inside that checkout;
- never `git pull`, never qmd maintenance, never write tracked files —
  the content service owns all of that;
- one wiki failing logs an ERROR and the sweep continues, exiting non-zero
  at the end so the unit shows in `systemctl --failed`.

The 5-minute cadence and the skill's 10-minute settle cool-down are
independent knobs: the timer is how often the bot looks; the scanner
decides what qualifies.

## Rollout order

1. Prove the prompt interactively on the dev machine against real
   tickets: thin report, out-of-scope, exact dupe, near dupe, clean defect.
2. On the server: enable one wiki, run once by hand with
   `--auto --dry-run`, read every decision.
3. Enable the timer with `mode: draft`. Read the notify emails for a week or
   two; paste the good ones.
4. Flip to `mode: post` when the drafts are consistently paste-worthy.
   Enable the next wiki (`enabled: true`) when ready.

Already earned trust on dev (wikis at `mode: post` with real posted
reviews)? Steps 2's dry-run and one manual live sweep are still mandatory
on the server — they validate the *server's* config, token, and allowlist
— but the draft phase needn't be repeated.

## Verify before first live run

- qmd concurrent reads: with the app up, run a search from `$WIKI_INDEX_ROOT`
  while wiki-mgr's sync runs; confirm no errors/locks.
- Notify API — from **inside a wiki checkout** (the script locates
  `wiki.config.yaml` from the working directory), with `<plugin-root>` =
  the installed plugin's path (find it via `claude plugin list` or under
  `~/.claude/plugins/`):

  ```
  cd $WIKI_INDEX_ROOT/cid-wiki
  python <plugin-root>/scripts/jira_utils.py <KEY> --notify --subject test --body-file /tmp/t.md --to you@example.com
  ```

  Use a throwaway ticket; confirm the email arrives and nothing shows on
  the ticket. With a scoped token this also proves the notify endpoint
  works through the api.atlassian.com gateway.
