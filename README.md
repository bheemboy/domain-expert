# domain-expert

A Claude Code plugin that turns a software project's Jira tickets, source code, and
documents into an interlinked, provenance-tracked markdown wiki: an LLM-maintained
"domain expert" for a product.

The plugin provides the tooling and schema; each product's wiki content lives in its own
repo. You install the plugin once, then point it at any number of wiki repos (`ts-wiki`,
`OLSV`, `CDS2ACQ`, `OLAC`). Each repo keeps its own `wiki/`, `raw/`, and `wiki.config.yaml`,
while the scripts and skills travel with the plugin.

## Skills

The plugin provides four skills, split across the pipeline's two layers: detection
(`wiki-queue` finds and queues work) and draining (`wiki-ingest` turns queued work into
wiki pages).

| Skill | What it does |
|---|---|
| `/wiki-init` | Bootstraps a new wiki repo, or upgrades an existing repo's schema after a plugin update |
| `/wiki-queue` | Detects new or changed sources and enqueues them, or inspects the queue; never drains |
| `/wiki-ingest` | Drains the queue into the wiki (extract, then synthesize) |
| `/wiki-lint` | Health-checks the wiki (mechanical and semantic) |

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

## Usage

Every task is driven by a slash command; there are no direct `python scripts/…` calls.

You normally run just these two commands:

| Command | Effect |
|---|---|
| `/wiki-ingest` | Detects new Jira and repo changes when the queue is empty, then ingests them (extract, then synthesize) |
| `/wiki-ingest N` | Same as `/wiki-ingest` (including the detect-when-empty step), but caps each phase at N items, for working through a large backlog in chunks |
| `/wiki-lint` | Runs a full health-check (mechanical and semantic) |

These commands report state and change nothing:

| Command | Effect |
|---|---|
| `/wiki-queue status` | Shows pending queue counts |
| `/wiki-lint mechanical` | Runs the fast deterministic checks only (no LLM) |

Use these for special, first-time, or custom scenarios:

| Command | When to use it |
|---|---|
| `/wiki-queue` | Force a full detection pass (Jira and repos) without draining, when you know new work landed and don't want to wait for the queue to empty |
| `/wiki-queue jira` | Detect Jira changes only, including the first-time backlog |
| `/wiki-queue code` | Detect external-repo changes only |
| `/wiki-queue backfill <repo>` | Load a repo's existing tracked files the first time |
| `/wiki-queue <path\|folder>` | Enqueue a `raw/` drop or ad-hoc paths without draining |
| `/wiki-queue --dry-run` | Preview detection without pulling, queueing, or writing state |
| `/wiki-ingest <path\|folder>` | Enqueue a `raw/` drop and ingest it in one step |
| `/wiki-init` | Bootstrap a new wiki repo, or upgrade `CLAUDE.md` to the current plugin schema (preserves §0) |

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
