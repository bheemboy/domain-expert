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
   during ingest and lint; the skills fall back to `grep` when it is absent. Run once, from
   the wiki repo root:
   ```
   qmd init
   qmd collection add raw  --name raw
   qmd collection add wiki --name wiki
   qmd update && qmd embed
   ```
   The index lives in `.qmd/` (gitignored and machine-local, so rebuild it per machine).
   `/wiki-ingest` refreshes it at the start and end of a run; `/wiki-lint` refreshes it at
   the start.

Then prime your sources (see [First-time priming](#first-time-priming)) and run
`/wiki-ingest`.

## Command reference

Every task runs from a slash command; there are no direct `python scripts/…` calls.
Commands are grouped by skill.

| Command | What it does, and when to use it |
|---|---|
| `/wiki-init` | Scaffolds a new wiki repo (interview, then `wiki/`, `wiki.config.yaml`, and `CLAUDE.md`), or upgrades an existing repo's generic schema. Run it once when starting a wiki, and again after a plugin update to refresh the schema. An upgrade rewrites only the generic schema body; your hand-written product-identity section (`CLAUDE.md` §0: names, Jira key, source repos) stays untouched. |
| `/wiki-ingest` | Scans your sources for new Jira and repo changes when the queue is empty, then ingests everything pending (extract, then synthesize). The default day-to-day command: run it to bring the wiki up to date. |
| `/wiki-ingest N` | The same as `/wiki-ingest`, but caps each phase at N items. Use it to work through a large backlog in controlled chunks, such as `/wiki-ingest 30` run a few times. |
| `/wiki-ingest <path\|folder>` | Enqueues a path or folder, then ingests it in one step (no scan). Takes every file, unfiltered; see [Force-enqueue](#force-enqueue) below. The path must be under `raw/` or a configured source repo, given relative to the repo root (for example, `raw/specs/api.pdf`) or as an absolute path. |
| `/wiki-lint` | Runs the full health check: deterministic checks plus a semantic review (stale, contradictory, or unsuperseded claims). Run it periodically, and before you rely on the wiki for answers. |
| `/wiki-lint mechanical` | Runs only the fast deterministic checks: broken `[[wikilinks]]`, orphan pages, duplicate slugs, index drift, and frontmatter gaps. Use it for a quick structural check, or in a pre-commit or CI step. |
| `/wiki-queue` | Shows pending extract and synth counts per source. Use it to check what is queued before or after a run. |
| `/wiki-queue all` | Runs a full source scan and enqueues what changed, without ingesting anything. A *source scan* checks Jira and your source repos for items that are new or changed since the last run; it is incremental, so re-running it with nothing new does nothing. Use it when you know new work landed and want it queued now. |
| `/wiki-queue jira` | Scans Jira only for changes and enqueues them, including the first-time backlog when no cursor exists yet. Use it to prime or refresh Jira without touching repos. |
| `/wiki-queue repos` | Scans external repos only for changes (the commits a `git pull` brings in) and enqueues them. Use it to pick up source-code changes without a Jira pass. |
| `/wiki-queue <path\|folder>` | Enqueues a path or folder without ingesting it. Takes every file, unfiltered; see [Force-enqueue](#force-enqueue) below. Same path rules as `/wiki-ingest <path\|folder>` above. Use it to stage several `raw/` drops before a single `/wiki-ingest`. |
| `/wiki-queue backfill <repo> …` | Enqueues a repo's git-tracked files via `git ls-files`, so gitignored files and `.git/` internals are skipped. It also applies the `ignore:` globs (see [Ignore filtering](#ignore-filtering) below). It lists tracked files only, so it never picks up untracked files, unlike the force-enqueue forms above. Name a repo by its `wiki.config.yaml` source name (for example, `my-project`) or by path, and pass several to backfill more than one at once. Run it once when first adding a repo, since an incremental source scan enqueues nothing for an already-current clone. |
| `/wiki-queue --dry-run` | Previews what a source scan would enqueue: it fetches, but does not pull, queue, or write state. |

### Ignore filtering

Source scans and `backfill` skip files that match the `ignore:` globs, so build output and
vendored code never enter the queue. The globs are a built-in set of junk defaults
(`node_modules/` and `vendor/` trees; minified, bundle, and map output; `*.d.ts`;
lockfiles; binary assets; styling; certs) plus any patterns you add under `ignore:` in
`wiki.config.yaml`.

Filtering applies only when a repo or source scan expands to many files. Naming a single
file's own path always enqueues that file, even if it matches a glob. Run any queue command
with `--dry-run` to preview the kept-versus-ignored split.

### Force-enqueue

Force-enqueuing takes every file under the path or folder, with no `ignore:` filtering and
any extension. The forced files are never dropped during triage. (Triage still reads each
one to judge density and add a focus note; it just cannot skip the file.) Use it for
genuinely valuable assets or images that the filters would otherwise drop.

Two commands force-enqueue, and both expand folders recursively:

- `/wiki-queue <path|folder>` queues the files only.
- `/wiki-ingest <path|folder>` queues the files, then ingests them.

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
