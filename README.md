# domain-expert

A Claude Code plugin that turns a software project's Jira tickets, source code, and
documents into an interlinked, provenance-tracked markdown wiki: an LLM-maintained
"domain expert" for a product.

The plugin provides the tooling and schema; each product's wiki content lives in its own
repo. You install the plugin once, then point it at any number of wiki repos (`ts-wiki`,
`OLSV`, `CDS2ACQ`, `OLAC`). Each repo keeps its own `wiki/`, `raw/`, and `wiki.config.yaml`,
while the scripts and skills travel with the plugin.

## Skills

The plugin provides four skills, split across the pipeline's two layers. `/wiki-queue`
detects new or changed sources and queues them; `/wiki-ingest` drains that queue into wiki
pages (extract, then synthesize). `/wiki-init` scaffolds or upgrades a wiki repo, and
`/wiki-lint` health-checks the result. The [Command reference](#command-reference) lists
every command and argument form.

## Install

Add the marketplace and install the plugin in Claude Code:

```
/plugin marketplace add bheemboy/domain-expert
/plugin install domain-expert@domain-expert
```

To update later, run `/plugin marketplace update domain-expert`. During development, you
can add the marketplace from a local clone path instead of `bheemboy/domain-expert`.

## Per-machine prerequisites

Complete these once per machine.

1. Install the Python dependencies. The runtime needs only `pyyaml` and `requests`
   (`pytest` is for running this plugin's own tests):
   ```
   pip install pyyaml requests
   ```
   To install the plugin's pinned set instead, without hunting for its versioned install
   path:
   ```
   pip install -r "$(find ~/.claude/plugins/cache -path '*domain-expert*' -name requirements.txt | head -1)"
   ```
   Marketplace plugins live at `~/.claude/plugins/cache/<marketplace>/<plugin>/<version>/`.
   The version is in the path, so prefer the command above over a hardcoded path.
2. Install the binary-document converters, used for PDF and Office extraction:
   ```
   sudo apt install poppler-utils pandoc libreoffice
   ```
3. Create the Jira credentials file at your wiki's configured `config_dir`
   (`<config_dir>/jira.token`, mode 600):
   ```
   JIRA_EMAIL=you@example.com
   JIRA_TOKEN=YOUR_API_TOKEN
   ```
   You can instead export `JIRA_EMAIL` and `JIRA_TOKEN`; the file wins when both are present.
4. *(Optional)* Build the qmd search index. It speeds up related-page lookup during ingest
   and lint; the skills fall back to `grep` when it is absent. Build it once, from the wiki
   repo root:
   ```
   qmd init
   qmd collection add raw  --name raw
   qmd collection add wiki --name wiki
   qmd update && qmd embed
   ```
   The index lives in `.qmd/` (gitignored, machine-local). `/wiki-ingest` refreshes it at
   the start and end of a run, and `/wiki-lint` at the start.

## Start a new wiki for a product

In a fresh, empty repo, run `/wiki-init`. It interviews you for the product identity
(display name, internal name, Jira project key, config dir, Jira `base_url` and JQL (Jira
Query Language), source repos, what counts as business-relevant, domain acronyms, and brand
or rename terms), then scaffolds:

- `wiki/` seed tree (`index.md`, `log.md`, `overview.md`, and the `entities/`, `concepts/`,
  `processes/`, `rules/`, and `terminology/` directories)
- `wiki.config.yaml` (project identity for the tooling)
- `CLAUDE.md` (the schema: §0 your identity, §1+ the generic body)
- `.gitignore`

Then complete the per-machine prerequisites above and prime your sources (see
[First-time priming](#first-time-priming)).

## Command reference

Every task is driven by a slash command; there are no direct `python scripts/…` calls.
Commands are grouped by skill.

| Command | What it does, and when to use it |
|---|---|
| `/wiki-init` | Scaffolds a new wiki repo (interview, then `wiki/`, `wiki.config.yaml`, and `CLAUDE.md`), or upgrades an existing repo's generic schema. Run it once when starting a wiki for a new product, and again after a plugin update to refresh the schema. Upgrade rewrites only the generic schema body and leaves your hand-written product-identity section (`CLAUDE.md` §0: names, Jira key, source repos) untouched. |
| `/wiki-ingest` | Detects new Jira and repo changes when the queue is empty, then ingests everything pending (extract, then synthesize). The default day-to-day command: run it to bring the wiki up to date. |
| `/wiki-ingest N` | Same as `/wiki-ingest`, including the detect-when-empty step, but caps each phase at N items. Use it to work through a large backlog in controlled chunks (for example, `/wiki-ingest 30` repeatedly) instead of one long run. |
| `/wiki-ingest <path\|folder>` | Enqueues the given `raw/` path (folders expand recursively) and ingests it in one step, skipping detection. Use it to pull in a specific document or folder you just dropped into `raw/`. |
| `/wiki-lint` | Runs the full health-check: deterministic checks plus a semantic review (stale, contradictory, or unsuperseded claims). Run it periodically, and before relying on the wiki for answers. |
| `/wiki-lint mechanical` | Runs only the fast deterministic checks (no LLM): broken `[[wikilinks]]`, orphan pages, duplicate slugs, index drift, and frontmatter gaps. Use it for a quick structural check or in a pre-commit or CI step. |
| `/wiki-queue` | Forces a full detection pass (Jira and repos) and enqueues what changed, without draining. Use it when you know new work landed and want it queued now, rather than waiting for `/wiki-ingest` to detect on an empty queue. |
| `/wiki-queue jira` | Detects Jira changes only and enqueues them, including the first-time backlog when no cursor exists yet. Use it to prime or refresh Jira without touching repos. |
| `/wiki-queue code` | Detects external-repo changes only (the commits a `git pull` brings in) and enqueues them. Use it to pick up source-code changes without a Jira pass. |
| `/wiki-queue <path\|folder>` | Enqueues a `raw/` drop or ad-hoc paths (folders expand recursively) without draining. Use it to stage several drops before a single `/wiki-ingest`. |
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
