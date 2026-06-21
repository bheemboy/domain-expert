---
name: wiki-init
description: Bootstrap a new domain-expert repo (scaffold wiki/, wiki.config.yaml, CLAUDE.md) or upgrade an existing repo's generic schema body. Use when starting a wiki for a new product, or to refresh the schema after a plugin update.
---

# Wiki Init (bootstrap / upgrade)

Two modes. Detect by presence of `wiki.config.yaml` in the current repo:
no config → **bootstrap**; config present → **upgrade**.

## Bootstrap (empty/new repo)

1. **Interview** the human for §0 identity, one question at a time:
   product/display name, internal name, Jira project key, config_dir (suggest
   `~/.config/<slug>-wiki`), Jira base_url, Jira JQL (offer the default
   `project = <JIRA_KEY> AND statusCategory = Done`; the answer fills
   `{{JIRA_JQL}}` — if the user accepts the default, substitute the literal string
   `project = <JIRA_KEY> AND statusCategory = Done` with the real key in place of
   `<JIRA_KEY>`; **do NOT include `ORDER BY` in the configured JQL** — the source scan
   (`build_jql` in `check_for_changes.py`) appends ` ORDER BY Updated ASC`
   automatically, so a user-supplied `ORDER BY` would produce malformed double-ORDER-BY
   JQL), source repo paths, what counts as business-relevant, domain seed acronyms,
   brand/rename terms.
2. **Scaffold** by copying templates from this skill's `templates/` and the schema
   from `${CLAUDE_PLUGIN_ROOT}/schema/CLAUDE.md.tmpl`, substituting `{{PLACEHOLDERS}}`.
   The same interview answers render in two surface forms depending on the target file:
   - Brand/rename terms: `{{BRAND_TERMS}}` is the inline prose form (comma-separated
     phrase, used in `CLAUDE.md` §0); `{{BRAND_TERMS_YAML_LIST}}` is the YAML-array
     form (e.g. `[ASV, CA, QualA]`, used in `wiki.config.yaml`).
   - Source repo paths: `{{SOURCE_REPOS_YAML_LIST}}` is a YAML list of the repo paths
     (e.g. `["~/projects/work/asv"]`); if none, `[]`.
   Render each placeholder in the format its surrounding file requires at substitution time.
   Files scaffolded:
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

1. Read the repo's current `CLAUDE.md`; extract its `## 0. Project identity` block — that is, everything from the `## 0. Project identity` heading up to (but not including) the `## 1. Raw → wiki` heading.
2. Render `${CLAUDE_PLUGIN_ROOT}/schema/CLAUDE.md.tmpl` but **replace its §0 with the
   repo's existing §0 verbatim**.
3. Show a diff of the generic body (§1+) and ask for confirmation before writing.
4. **Never** touch `wiki/`, `raw/`, or `wiki.config.yaml`. Only `CLAUDE.md` changes.

## Guardrails
- Never overwrite an existing `wiki.config.yaml` or non-empty `wiki/` during bootstrap;
  if present, switch to upgrade mode.
- Never invent §0 facts — ask.
