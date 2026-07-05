# domain-expert

A Claude Code plugin that turns a software project's Jira tickets, source code, and
documents into an interlinked, provenance-tracked Markdown wiki. The result is an
LLM-maintained "domain expert" for your product.

The plugin supplies the tooling and schema. Each product's wiki content lives in its own
repo, one per product: a wiki repo holds its own `wiki/`, `raw/`, and `wiki.config.yaml`,
while the scripts and skills travel with the plugin. Install the plugin once per machine,
then create or adopt a wiki repo for each product.

## Installation

Install the plugin once per machine.

1. Add the marketplace and install the plugin, in Claude Code:
   ```
   /plugin marketplace add bheemboy/domain-expert
   /plugin install domain-expert@domain-expert
   ```
   To update later, run `/plugin marketplace update domain-expert`.
2. Install the Python dependencies:
   ```
   pip install pyyaml requests
   ```
3. Install the binary-document converters, used for PDF and Office extraction:
   ```
   sudo apt install poppler-utils pandoc libreoffice
   ```

## Start a new wiki for a product

Do this once per wiki repo. If you are adopting a wiki repo someone else scaffolded, skip
step 1 and do steps 2 and 3 for your checkout.

1. **Scaffold the wiki.** In a fresh, empty repo, run `/wiki-init`. It interviews you for the
   product identity (display name, internal name, Jira project key, config dir, Jira
   `base_url` and JQL (Jira Query Language), source repos, what counts as business-relevant,
   domain acronyms, and brand or rename terms), then builds the repo:
   ```
   <your-wiki-repo>/
     CLAUDE.md          # schema: §0 product identity (yours), §1+ generic (plugin-managed)
     wiki.config.yaml   # Jira base_url/jql, sources, config_dir, lint terms
     wiki/              # the wiki itself: index, log, overview, and the entities/, concepts/,
                        #   processes/, rules/, and terminology/ directories
     raw/               # source material you drop in, plus raw/imports/ (extract output)
   ```
   It also writes a `.gitignore`. The `CLAUDE.md` product-identity section (§0) is filled from
   your interview answers; the rest of the schema is generic and plugin-managed.
2. **Add Jira credentials.** Create the credentials file at the `config_dir` you set in step 1
   (`<config_dir>/jira.token`, mode 600):
   ```
   JIRA_EMAIL=you@example.com
   JIRA_TOKEN=YOUR_API_TOKEN
   ```
   You can instead export `JIRA_EMAIL` and `JIRA_TOKEN`. When both are present, the file wins.
3. **Build the search index** *(optional)*. The qmd index speeds up related-page lookup
   during ingest and lint; the skills fall back to `grep` when it is absent. `wiki-init`
   scaffolds `qmd_sync.sh` into the repo root — run it once yourself, from the wiki repo
   root, in your own terminal:
   ```
   ./qmd_sync.sh
   ```
   It is idempotent: it bootstraps the index (`qmd init` + the `raw`/`wiki` collections)
   on first run, then refreshes and embeds until nothing is pending. On CPU the first
   build can run for **hours** across many `qmd embed` passes — far longer than an agent
   tool call can stay open, so run it directly (not through Claude), backgrounding the
   long first build if you like:
   ```
   nohup ./qmd_sync.sh > qmd_sync.log 2>&1 &
   ```
   The index lives in `.qmd/` (gitignored and machine-local, so rebuild it per machine).
   `/wiki-ingest` refreshes it at the start and end of a run; `/wiki-lint` refreshes it at
   the start of a run.

## Command reference

Every task runs from a slash command; there are no direct `python scripts/…` calls.
Commands are grouped by skill.

| Command | What it does, and when to use it |
|---|---|
| `/wiki-init` | Scaffolds a new wiki repo (interview, then `wiki/`, `wiki.config.yaml`, and `CLAUDE.md`), or upgrades an existing repo's generic schema. Run it once when starting a wiki, and again after a plugin update to refresh the schema. An upgrade rewrites only the generic schema body; your hand-written product-identity section (`CLAUDE.md` §0: names, Jira key, source repos) stays untouched. On a pre-OKF wiki, the upgrade also offers the one-shot [OKF migration](#okf-conformance) (shown as a dry-run report first; applied only on your confirmation). |
| `/wiki-ingest` | Scans your sources for new Jira and repo changes when the queue is empty, then ingests everything pending (extract, then synthesize). The default day-to-day command: run it to bring the wiki up to date. |
| `/wiki-ingest N` | The same as `/wiki-ingest`, but caps each phase at N items. Use it to work through a large backlog in controlled chunks, such as `/wiki-ingest 30` run a few times. |
| `/wiki-ingest <path\|folder>` | Enqueues a path or folder, then ingests it in one step (no scan). Takes every file, unfiltered; see [Force-enqueue](#force-enqueue) below. The path must be under `raw/` or a configured source repo, given relative to the repo root (for example, `raw/specs/api.pdf`) or as an absolute path. |
| `/wiki-lint` | Delta health check: deterministic checks plus a semantic review of the pages **changed since the last lint** and their direct neighbors. Fast; run it any time. After an ingest run it usually reports nothing new — the signal the wiki is current. |
| `/wiki-lint --full` | Exhaustive whole-wiki audit: shards the wiki so every page is reviewed, with a cross-shard reconciliation pass. It also re-opens the source repos to verify ticket- and doc-derived claims where they make absolute claims or conflict with code, applying *code wins over any ticket* (§4.4). Slower; run it rarely — before relying on the wiki for something important, before a release, or periodically. |
| `/wiki-lint mechanical` | Runs only the fast deterministic checks: broken `[[wikilinks]]`, orphan pages, duplicate slugs, index-catalog drift (exact, against the generated catalog), frontmatter gaps (including `title`/`description`), title↔H1 mismatch, and the `okf_version` declaration. Use it for a quick structural check, or in a pre-commit or CI step. |
| `/wiki-queue` | Shows pending extract and synth counts per source. Use it to check what is queued before or after a run. |
| `/wiki-queue all` | Runs a full source scan and enqueues what changed, without ingesting anything. A *source scan* checks Jira and your source repos for items that are new or changed since the last run; it is incremental, so re-running it with nothing new does nothing. Use it when you know new work landed and want it queued now. |
| `/wiki-queue jira` | Scans Jira only for changes and enqueues them, including the first-time backlog when no cursor exists yet. Use it to prime or refresh Jira without touching repos. |
| `/wiki-queue repos` | Scans external repos only for changes (the commits a `git pull` brings in) and enqueues them. Use it to pick up source-code changes without a Jira pass. |
| `/wiki-queue <path\|folder>` | Enqueues a path or folder without ingesting it. Takes every file, unfiltered; see [Force-enqueue](#force-enqueue) below. Same path rules as `/wiki-ingest <path\|folder>` above. Use it to stage several `raw/` drops before a single `/wiki-ingest`. |
| `/wiki-queue backfill <repo> …` | Enqueues a repo's git-tracked files via `git ls-files`, so gitignored files and `.git/` internals are skipped. It also applies the `ignore:` globs (see [Ignore filtering](#ignore-filtering) below). It lists tracked files only, so it never picks up untracked files, unlike the force-enqueue forms above. Name a repo by its `wiki.config.yaml` source name (for example, `my-project`) or by path, and pass several to backfill more than one at once. Run it once when first adding a repo, since an incremental source scan enqueues nothing for an already-current clone. |
| `/wiki-queue --dry-run` | Previews what a source scan would enqueue: it fetches, but does not pull, queue, or write state. |
| `/wiki-story <title or description>` | Writes ONE user story (A/C, D/N, Q/N) grounded in the wiki. Drafts in the conversation so you can iterate; saves Markdown to `stories/` only when you say "save as MD". Target an existing epic with "into epic `<slug>`". |
| `/wiki-epic <objective>` | Breaks a broad objective into an epic + child stories. Proposes a numbered breakdown, waits for your approval, then auto-writes the stories. Iterate in the conversation; "save as MD" writes a single `stories/<epic-slug>.md`. |
| `/wiki-doc-author <title or page>` | Authors or updates ONE customer-facing help page, grounded in the wiki and written to the bundled style guide. Drafts in the conversation; saves Markdown to the configured `docs:` location only when you say "save as MD". |
| `/wiki-doc-review [<path\|folder>] [factual\|style\|both]` | Reviews customer-facing docs against the wiki (factual: stale/incorrect/missing) and the bundled style guide (style: R-… findings). On-demand, read-only; default scope = configured `docs:`, default lens = both. |
| `/wiki-defect-review [<KEY> \| --auto [--dry-run]]` | Reviews a new defect like a human reviewer — clarifying asks, troubleshooting steps, scope check, duplicates, verdict — grounded in the wiki. Interactive per ticket, or `--auto` polling for servers (draft-email first, direct posting after the trust flip). |

### OKF conformance

Every wiki this plugin maintains is an [Open Knowledge Format (OKF) v0.1](https://github.com/GoogleCloudPlatform/knowledge-catalog/blob/main/okf/SPEC.md)
bundle, so any OKF-aware tool can consume it directly:

- **Core fields.** Every content page carries `title` (mirrors the H1),
  `description` (the one-line summary the index catalog renders), and `type`
  in its YAML frontmatter. `wiki/index.md` declares `okf_version: "0.1"`.
- **Generated catalog.** The per-category listing in `wiki/index.md` sits inside
  `<!-- catalog:begin/end -->` markers and is rendered from page `description:`
  frontmatter by `scripts/build_index.py`; lint fails on any drift. Hand-written
  prose outside the markers is yours.
- **Log.** `wiki/log.md` uses OKF date groups (`## YYYY-MM-DD` headings, newest
  first) with one `- <op> | <payload>` bullet per event.
- **Extension fields.** `status`, `sources`, `code_refs`, and `updated` are
  producer extensions; OKF consumers preserve unknown keys, so they travel with
  the bundle. Confidence tags and supersession sections live in page bodies.
- **Wikilinks caveat.** Page bodies cross-reference with Obsidian `[[wikilinks]]`
  (they power lint's neighbor expansion and graph views); an OKF consumer sees
  them as plain text. The `## References` sections use standard relative Markdown
  links, so provenance edges remain visible to OKF tools.

Wikis created before v0.12.0 migrate with the one-shot mechanical step offered by
`/wiki-init` (upgrade mode): it backfills `title`/`description`, restructures
`log.md`, and inserts the `okf_version` declaration — shown as a dry-run report
first and applied only on your confirmation.

### Reviewing online documentation

The `/wiki-doc-review` command reviews your documented APIs, guides, and other customer-facing material against the wiki and a bundled style guide. It draws its doc locations from the `docs:` block in `wiki.config.yaml` (see [Start a new wiki for a product](#start-a-new-wiki-for-a-product) for setup).

### Defect review

The `/wiki-defect-review` command acts as a first-line reviewer on newly
submitted defects: it reads the ticket (screenshots included; small logs and
PDFs too — videos and zips are disclosed as unviewed), asks the submitter
sharply-scoped clarifying questions or troubleshooting steps when the report
is thin, judges whether the defect belongs to the product, finds duplicates
in the wiki and in recent Jira, and delivers a structured verdict.

**Invocation** (run inside a wiki repo — the repo's `project.key` decides
which Jira project is reviewed, e.g. cid-wiki → OLAC, ts-wiki → CDS2ASV):

| Form | What happens |
|------|--------------|
| `/wiki-defect-review OLAC-1234` | Interactive spot review of one ticket. Shows the proposed comment plus the full analysis in conversation. Never emails, posts, or writes state on its own. |
| `/wiki-defect-review` + pasted ticket text | Same interactive review over pasted content — no Jira fetch, analysis only. |
| `/wiki-defect-review --auto` | Headless sweep: scans for settled unreviewed tickets (10-min cool-down, skips tickets where the bot spoke last or a draft email is pending), reviews each, and **delivers** per the configured `mode`. |
| `/wiki-defect-review --auto --dry-run` | Same scan and reviews, but prints every would-deliver decision (key, comment kind, comment text) instead of delivering. Writes no state. Run this first on any new setup. |

**Delivery mode is configuration, not a flag** — the trust switch lives in
`wiki.config.yaml` so a cron line can't typo it:

```yaml
defect_review:
  enabled: true                # --auto gate; interactive works regardless
  mode: draft                  # draft = notify email to you, paste to post
                               # post  = comment directly on the ticket
  notify_user: you@example.com
  candidate_jql: 'issuetype = Defect AND status in ("New", "Open")'
  max_question_rounds: 3       # ask-comment rounds before a forced verdict
```

Use your project's real issue-type and status names in `candidate_jql`
(issue types vary per Jira project — `Defect`, `Bug`, …). The project key,
the 10-minute cool-down, and the bot marker are supplied by code and never
belong in the JQL.

**Model floor: Opus or better.** Side-by-side runs of the same ticket on
different models showed smaller models produce noticeably weaker reviews.
The server wrapper pins `--model opus` (override upward via
`DEFECT_REVIEW_MODEL`); for interactive spot reviews, use an Opus-class
session.

**Rollout ladder** — earn trust one rung at a time:

1. **Interactive spot reviews** on a few real tickets (a thin report, a
   duplicate, an out-of-scope one) to tune expectations — dev machine.
2. **`--auto --dry-run`** — read every decision the bot would have made.
3. **`--auto` with `mode: draft`** — the bot emails you each proposed
   comment via Jira's notify API (invisible on the ticket); you paste the
   good ones. The pasted marker is what tells the bot the ticket is handled.
4. **Flip to `mode: post`** once the drafts are consistently paste-worthy.

Headless scheduling, server prerequisites (permissions for `claude -p`,
shared content checkouts, unified qmd index), and the cron wrapper live in
`skills/wiki-defect-review/references/server-setup.md`.

### Ignore filtering

Source scans and `backfill` skip files that match the `ignore:` globs, so build output and
vendored code never enter the queue. The globs are a built-in set of junk defaults
(`node_modules/` and `vendor/` trees; minified, bundle, and map output; `*.d.ts`;
lockfiles; binary assets; styling; certs) plus any patterns you add under `ignore:` in
`wiki.config.yaml`.

Filtering applies only when a repo or source scan expands to many files. Naming a single
file's own path always enqueues that file, even if it matches a glob. Run any queue command
with `--dry-run` to preview the kept-versus-ignored split.

If a `docs:` location resolves *inside* one of your `sources` repos, the scan, `backfill`,
and `--dry-run` auto-exclude it — no `ignore:` entry needed. Customer-facing online help is
written *by* `/wiki-doc-author` and reviewed *by* `/wiki-doc-review`; re-ingesting it would
create a wiki → docs → wiki loop and erode the wiki as an independent source of truth. To
deliberately seed an existing system's online help once, name the path explicitly
(`/wiki-ingest <docs-path>`), which bypasses all ignore filtering.

### Force-enqueue

Force-enqueuing takes every file under the path or folder, with no `ignore:` filtering and
any extension. The forced files are never dropped during triage. (Triage still reads each
one to judge density and add a focus note; it just cannot skip the file.) Use it for
genuinely valuable assets or images that the filters would otherwise drop.

Two commands force-enqueue, and both expand folders recursively:

- `/wiki-queue <path|folder>` queues the files only.
- `/wiki-ingest <path|folder>` queues the files, then ingests them.

## Authoring stories and epics

`/wiki-story` and `/wiki-epic` turn the wiki into authored work. They draft in
the conversation — nothing is written until you say **"save as MD"** — and save
to a flat `stories/` directory at the wiki repo root. Separately, `/wiki-doc-author` authors customer-facing online help pages (distinct from Jira stories), saving under the `docs:` location.

```
stories/
  <epic-slug>.md                # an epic and its child stories, inline
  <standalone-story-slug>.md    # a standalone story
```

Each story sits under a `## Story: <title>` boundary and ends with a `## Grounding`
footer listing the wiki pages and Jira keys that informed it. Writing back to
Jira is planned but not yet implemented; "add to Jira" reports that today.

## First-time priming

Because a source scan is incremental, a brand-new source needs a one-time prime:

| Source | Prime with |
|---|---|
| Jira backlog | `/wiki-queue jira` |
| A source repo's existing files | `/wiki-queue backfill <repo> …` |
| A document or file drop in `raw/` | `/wiki-queue raw/<path>` (enqueue only), or `/wiki-ingest raw/<path>` (enqueue and ingest) |

With several source repos, prime them in one call (`/wiki-queue backfill <repo1> <repo2>
…`) or one at a time. The order does not matter, since you ingest once at the end.

After priming, run `/wiki-ingest` to process the queue. From then on, plain `/wiki-ingest`
keeps everything current.
