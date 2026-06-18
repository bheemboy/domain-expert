# domain-expert

A Claude Code plugin that turns a software project's Jira tickets, source code, and
documents into an interlinked, provenance-tracked markdown wiki: an LLM-maintained
"domain expert" for a product.

The plugin provides the tooling and schema; each product's wiki content lives in its own
repo, one per product. A wiki repo keeps its own `wiki/`, `raw/`, and `wiki.config.yaml`,
while the scripts and skills travel with the plugin. You install the plugin once per
machine, then create or adopt a wiki repo for each product.

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

Do this once per wiki repo. If you are adopting a wiki repo someone already scaffolded,
skip step 1 and do steps 2 and 3 for your checkout.

1. In a fresh, empty repo, run `/wiki-init` to scaffold the wiki. It interviews you for the
   product identity (display name, internal name, Jira project key, config dir, Jira
   `base_url` and JQL (Jira Query Language), source repos, what counts as business-relevant,
   domain acronyms, and brand or rename terms), then creates:
   - `wiki/` seed tree (`index.md`, `log.md`, `overview.md`, and the `entities/`,
     `concepts/`, `processes/`, `rules/`, and `terminology/` directories)
   - `wiki.config.yaml` (project identity for the tooling)
   - `CLAUDE.md` (the wiki's schema: a product-identity section filled from your interview
     answers, plus a generic body the plugin manages)
   - `.gitignore`
2. Create the Jira credentials file at the `config_dir` you set in step 1
   (`<config_dir>/jira.token`, mode 600):
   ```
   JIRA_EMAIL=you@example.com
   JIRA_TOKEN=YOUR_API_TOKEN
   ```
   You can instead export `JIRA_EMAIL` and `JIRA_TOKEN`; the file wins when both are present.
3. *(Optional)* Build the qmd search index. It speeds up related-page lookup during ingest
   and lint; the skills fall back to `grep` when it is absent. Run once, from the wiki repo
   root:
   ```
   qmd init
   qmd collection add raw  --name raw
   qmd collection add wiki --name wiki
   qmd update && qmd embed
   ```
   The index lives in `.qmd/` (gitignored and machine-local, so rebuild it per machine).
   `/wiki-ingest` refreshes it at the start and end of a run, and `/wiki-lint` at the start.

Then prime your sources (see [First-time priming](#first-time-priming)) and run
`/wiki-ingest`.

## Command reference

Every task is driven by a slash command; there are no direct `python scripts/…` calls.
Commands are grouped by skill.

| Command | What it does, and when to use it |
|---|---|
| `/wiki-init` | Scaffolds a new wiki repo (interview, then `wiki/`, `wiki.config.yaml`, and `CLAUDE.md`), or upgrades an existing repo's generic schema. Run it once when starting a wiki for a new product, and again after a plugin update to refresh the schema. Upgrade rewrites only the generic schema body and leaves your hand-written product-identity section (`CLAUDE.md` §0: names, Jira key, source repos) untouched. |
| `/wiki-ingest` | Detects new Jira and repo changes when the queue is empty, then ingests everything pending (extract, then synthesize). The default day-to-day command: run it to bring the wiki up to date. |
| `/wiki-ingest N` | Same as `/wiki-ingest`, including the detect-when-empty step, but caps each phase at N items. Use it to work through a large backlog in controlled chunks (for example, `/wiki-ingest 30` repeatedly) instead of one long run. |
| `/wiki-ingest <path\|folder>` | Enqueues a path under `raw/` or a configured source repo (folders expand recursively), then ingests it in one step, skipping detection. Give the path relative to the wiki repo root (for example, `raw/specs/api.pdf`) or as an absolute path. A path outside `raw/` and the configured source repos is rejected. Use it to pull in a specific document or folder you just dropped into `raw/`. To enqueue a drop and then drain under a per-phase budget, see `/wiki-queue <path\|folder>` followed by `/wiki-ingest N`. |
| `/wiki-lint` | Runs the full health-check: deterministic checks plus a semantic review (stale, contradictory, or unsuperseded claims). Run it periodically, and before relying on the wiki for answers. |
| `/wiki-lint mechanical` | Runs only the fast deterministic checks: broken `[[wikilinks]]`, orphan pages, duplicate slugs, index drift, and frontmatter gaps. Use it for a quick structural check or in a pre-commit or CI step. |
| `/wiki-queue` | Forces a full detection pass (Jira and repos) and enqueues what changed, without draining. Use it when you know new work landed and want it queued now, rather than waiting for `/wiki-ingest` to detect on an empty queue. |
| `/wiki-queue jira` | Detects Jira changes only and enqueues them, including the first-time backlog when no cursor exists yet. Use it to prime or refresh Jira without touching repos. |
| `/wiki-queue code` | Detects external-repo changes only (the commits a `git pull` brings in) and enqueues them. Use it to pick up source-code changes without a Jira pass. |
| `/wiki-queue <path\|folder>` | Enqueues a path under `raw/` or a configured source repo (folders expand recursively) without draining. Give the path relative to the wiki repo root (for example, `raw/specs`) or as an absolute path. A path outside `raw/` and the configured source repos is rejected. Use it to stage several `raw/` drops before a single `/wiki-ingest`. |
| `/wiki-queue backfill <repo>` | Enqueues every tracked file in a configured repo. Use it once when first adding a repo, since incremental detection enqueues nothing for an already-current clone. |
| `/wiki-queue --dry-run` | Previews what detection would enqueue, fetching but not pulling, queueing, or writing state. Use it to preview a detection pass before committing to it. |
| `/wiki-queue status` | Shows pending extract and synth counts per source. Use it to check what's queued before or after a run. |

Detection is incremental and idempotent; running it with nothing new is a no-op.

## First-time priming

Because detection is incremental, a brand-new source needs a one-time prime:

| Source | Prime with |
|---|---|
| Jira backlog | `/wiki-queue jira` |
| A source repo's existing files | `/wiki-queue backfill <repo>` |
| A document or file drop in `raw/` | `/wiki-queue raw/<path>` (enqueue only), or `/wiki-ingest raw/<path>` (enqueue and drain) |

After priming, run `/wiki-ingest` to process the queue. Plain `/wiki-ingest` keeps
everything current from then on.

## How it works

A few terms describe the model:

- **Sources**. `jira`, `raw` (the wiki repo's own `raw/` drop folder), and each external
  git repo listed in `wiki.config.yaml` `sources`.
- **Identity**. One unit of work: a Jira key, or an absolute file path.
- **Queues**. Per-source `extract` and `synth` files under `<config_dir>/state/`
  (machine-local). An identity lives in exactly one file at a time, and its location is its
  state.
- **Repo discovery**. The scripts find the wiki repo by walking up from the working
  directory to the nearest `wiki.config.yaml` (override with `$WIKI_CONFIG`), so the same
  installed plugin serves any wiki repo you `cd` into.
- **Schema**. `CLAUDE.md` §1–§8 is generic and plugin-managed (regenerate via
  `/wiki-init`); only §0, the product identity, is hand-edited per repo.

## A consumer repo's layout

A wiki repo that uses the plugin has this shape:

```
<your-wiki-repo>/
  CLAUDE.md          # schema: §0 product identity (yours), §1+ generic (plugin-managed)
  wiki.config.yaml   # Jira base_url/jql, sources, config_dir, lint terms
  wiki/              # the wiki: index/log/overview + entities/concepts/processes/rules/terminology
  raw/               # raw source material you drop in, plus raw/imports/ (extract output)
```

## Development

The Python package and its tests live in this repo. Run the suite from the plugin repo root:

```
python -m pytest
```
