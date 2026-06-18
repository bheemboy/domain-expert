# domain-expert

A Claude Code plugin that turns a software project's **Jira tickets, source code, and
documents** into an interlinked, provenance-tracked markdown wiki — an LLM-maintained
"domain expert" for a product.

The plugin provides the **tooling and schema**; each product's wiki **content** lives in
its own repo. Install the plugin once, then point it at any number of wiki repos
(`ts-wiki`, OLSV, CDS2ACQ, OLAC, …) — each keeps its own `wiki/`, `raw/`, and
`wiki.config.yaml`, while the scripts and skills travel with the plugin.

## Skills

| Skill | What it does |
|---|---|
| `/wiki-init` | Bootstrap a new wiki repo (interview + scaffold), or upgrade an existing repo's schema after a plugin update |
| `/wiki-queue` | Detect new/changed sources (Jira + repos) and enqueue them, or inspect the queue — **never drains** |
| `/wiki-ingest` | Drain the queue into the wiki (extract → synthesize) |
| `/wiki-lint` | Health-check the wiki (mechanical + semantic) |

The split mirrors the pipeline's two layers: **detection** (`wiki-queue` — find & queue
work) versus **draining** (`wiki-ingest` — turn queued work into wiki pages).

## Install

```
/plugin marketplace add bheemboy/domain-expert
/plugin install domain-expert@domain-expert
```

Updates later: `/plugin marketplace update domain-expert`. (During development you can add
the marketplace from a local clone path instead of `bheemboy/domain-expert`.)

## Per-machine prerequisites

1. **Python deps** — the runtime needs only `pyyaml` and `requests` (`pytest` is for
   running this plugin's own tests). Either install them by name:
   ```
   pip install pyyaml requests
   ```
   …or install the plugin's pinned set without hunting for its versioned install path:
   ```
   pip install -r "$(find ~/.claude/plugins/cache -path '*domain-expert*' -name requirements.txt | head -1)"
   ```
   (Marketplace plugins live at `~/.claude/plugins/cache/<marketplace>/<plugin>/<version>/`;
   the version is in the path, so prefer the command above over a hardcoded path.)
2. **Binary-doc converters** (for PDF/Office extraction):
   ```
   sudo apt install poppler-utils pandoc libreoffice
   ```
3. **Jira credentials** at your wiki's configured `config_dir` (`<config_dir>/jira.token`, mode 600):
   ```
   JIRA_EMAIL=you@example.com
   JIRA_TOKEN=YOUR_API_TOKEN
   ```
   (Or export `JIRA_EMAIL` / `JIRA_TOKEN`; the file wins when both are present.)
4. *(Optional)* **qmd search index** — speeds up related-page lookup during ingest/lint;
   the skills fall back to `grep` if it's absent. Build once, from the wiki repo root:
   ```
   qmd init
   qmd collection add raw  --name raw
   qmd collection add wiki --name wiki
   qmd update && qmd embed
   ```
   The index lives in `.qmd/` (gitignored, machine-local). `/wiki-ingest` refreshes it at
   start/end of a run and `/wiki-lint` at start.

## Start a new wiki for a product

In a fresh, empty repo, run **`/wiki-init`**. It interviews you for the product identity —
display name, internal name, Jira project key, config dir, Jira `base_url` + JQL, source
repos, what counts as business-relevant, domain acronyms, brand/rename terms — then
scaffolds:

- `wiki/` seed tree (`index.md`, `log.md`, `overview.md`, and the
  `entities/ concepts/ processes/ rules/ terminology/` dirs)
- `wiki.config.yaml` (project identity for the tooling)
- `CLAUDE.md` (the schema: §0 your identity, §1+ the generic body)
- `.gitignore`

Then complete the per-machine prerequisites above and prime your sources (next section).

## Day-to-day

Everything is driven by slash commands — **no direct `python scripts/…` calls**:

| Command | Effect |
|---|---|
| `/wiki-queue` | Detect Jira + repos and enqueue what changed |
| `/wiki-queue status` | Show pending queue counts (no detection) |
| `/wiki-ingest` | Drain the queue (extract → synth); `/wiki-ingest N` for a per-phase budget |
| `/wiki-lint` | Full health-check; `/wiki-lint mechanical` for the fast deterministic check |
| `/wiki-init` | Regenerate `CLAUDE.md` from the current plugin schema (preserves §0) |

Detection is incremental and idempotent — re-running with nothing new is a no-op.

## First-time priming

Because detection is incremental, a brand-new source needs a one-time prime:

- **Jira backlog:** `/wiki-queue jira`
- **A source repo's existing files:** `/wiki-queue backfill <repo>`
- **A doc/file drop in `raw/`:** `/wiki-queue raw/<path>` (enqueue only) or
  `/wiki-ingest raw/<path>` (enqueue + drain)

Then `/wiki-ingest` to process. After priming, plain `/wiki-queue` keeps everything current.

## How it works

- **Sources:** `jira`, `raw` (the wiki repo's own `raw/` drop folder), and each external
  git repo listed in `wiki.config.yaml` `sources`.
- **Identity:** one unit of work — a Jira key, or an absolute file path.
- **Queues:** per-source `extract`/`synth` files under `<config_dir>/state/` (machine-local).
  An identity lives in exactly one file at a time; its location is its state.
- **Repo discovery:** the scripts find the wiki repo by walking up from the working
  directory to the nearest `wiki.config.yaml` (override with `$WIKI_CONFIG`) — so the same
  installed plugin serves any wiki repo you `cd` into.
- **Schema:** `CLAUDE.md` §1–§8 is generic and plugin-managed (regenerate via `/wiki-init`);
  only §0 (the product identity) is hand-edited per repo.

## A consumer repo's layout

```
<your-wiki-repo>/
  CLAUDE.md          # schema — §0 product identity (yours), §1+ generic (plugin-managed)
  wiki.config.yaml   # Jira base_url/jql, sources, config_dir, lint terms
  wiki/              # the wiki: index/log/overview + entities/concepts/processes/rules/terminology
  raw/               # raw source material you drop in, plus raw/imports/ (extract output)
```

## Development

The Python package and its tests live in this repo:

```
python -m pytest        # from the plugin repo root
```
