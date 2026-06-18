---
name: wiki-init
description: Bootstrap a new project-llm-wiki repo (scaffold wiki/, wiki.config.yaml, CLAUDE.md) or upgrade an existing repo's generic schema body. Use when starting a wiki for a new product, or to refresh the schema after a plugin update.
---

# Wiki Init (bootstrap / upgrade)

Two modes. Detect by presence of `wiki.config.yaml` in the current repo:
no config → **bootstrap**; config present → **upgrade**.

## Bootstrap (empty/new repo)

1. **Interview** the human for §0 identity, one question at a time:
   product/display name, internal name, Jira project key, config_dir (suggest
   `~/.config/<slug>-wiki`), Jira base_url, Jira JQL (offer the default
   `project = <KEY> AND statusCategory = Done ORDER BY resolved ASC`), source repo
   paths, what counts as business-relevant, domain seed acronyms, brand/rename terms.
2. **Scaffold** by copying templates from this skill's `templates/` and the schema
   from `${CLAUDE_PLUGIN_ROOT}/schema/CLAUDE.md.tmpl`, substituting `{{PLACEHOLDERS}}`:
   - `wiki/` tree (index.md, overview.md, log.md, and the five category dirs).
   - `wiki.config.yaml` from `templates/wiki.config.yaml.tmpl`.
   - `CLAUDE.md` from `${CLAUDE_PLUGIN_ROOT}/schema/CLAUDE.md.tmpl`.
   - `.gitignore` from `templates/gitignore`.
   Substitute `{{TODAY}}` with the current ISO date.
3. **Print remaining machine-local prereqs** (do not perform): create
   `<config_dir>/jira.token` (JIRA_EMAIL/JIRA_TOKEN), `pip install -r` the plugin's
   `requirements.txt`, install doc converters (`poppler-utils pandoc libreoffice`),
   optional `qmd init` + `qmd collection add raw/wiki`.
4. Tell the user: prime sources with `/wiki-queue jira` and
   `/wiki-queue backfill <repo>`, then `/wiki-ingest`.

## Upgrade (existing repo)

1. Read the repo's current `CLAUDE.md`; extract its `## 0. Project identity` block.
2. Render `${CLAUDE_PLUGIN_ROOT}/schema/CLAUDE.md.tmpl` but **replace its §0 with the
   repo's existing §0 verbatim**.
3. Show a diff of the generic body (§1+) and ask for confirmation before writing.
4. **Never** touch `wiki/`, `raw/`, or `wiki.config.yaml`. Only `CLAUDE.md` changes.

## Guardrails
- Never overwrite an existing `wiki.config.yaml` or non-empty `wiki/` during bootstrap;
  if present, switch to upgrade mode.
- Never invent §0 facts — ask.
