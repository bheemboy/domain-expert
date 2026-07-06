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
   - `wiki.config.yaml` from `templates/wiki.config.yaml.tmpl` (keys: Jira base_url/jql, sources, config_dir, lint terms; optional commented blocks: `docs:`, `synth_tuning:`, `ignore:`, `defect_review:`).
   - `CLAUDE.md` from `${CLAUDE_PLUGIN_ROOT}/schema/CLAUDE.md.tmpl` — its §0 carries
     the optional, commented **Documentation Domain Context** override block (vendor
     identity, identifier sweep, `platform`, project term table) for `/wiki-doc-*`;
     leave it commented (defaults apply), do not fill it from the interview.
   - `.gitignore` from `templates/gitignore`.
   - `qmd_sync.sh` (repo root) from `templates/qmd_sync.sh`, copied verbatim (no
     placeholders); ensure it stays executable (`chmod +x`).
   Substitute `{{TODAY}}` with the current ISO date.
3. **Print remaining machine-local prereqs** (do not perform): create
   `<config_dir>/jira.token`, chmod 600 (start from
   `${CLAUDE_PLUGIN_ROOT}/skills/wiki-init/templates/jira.token.example`),
   `pip install -r` the plugin's
   `requirements.txt` (includes docling for layout-aware PDF conversion — heavy,
   ~2 GB with models), install doc converters (`poppler-utils pandoc libreoffice`),
   optional search index — the human runs `./qmd_sync.sh` from the repo root in their
   own terminal (it bootstraps `qmd init` + the `raw`/`wiki` collections, then embeds;
   the first build can run for hours, so do NOT run it for them). Long build:
   `nohup ./qmd_sync.sh > qmd_sync.log 2>&1 &`.
4. Tell the user: prime sources with `/wiki-queue jira` and
   `/wiki-queue backfill <repo>`, then `/wiki-ingest`.

## Upgrade (existing repo)

1. Read the repo's current `CLAUDE.md`; extract its `## 0. Project identity` block — that is, everything from the `## 0. Project identity` heading up to (but not including) the `## 1. Raw → wiki` heading.
2. Render `${CLAUDE_PLUGIN_ROOT}/schema/CLAUDE.md.tmpl` but **replace its §0 with the
   repo's existing §0 verbatim** — with one addition: if the existing §0 does **not**
   already contain a `### Documentation Domain Context` subsection, append that block
   (the commented `<!-- documentation_domain_context: … -->` block) from the
   freshly-rendered template's §0 to the end of the preserved §0. This lets repos
   created before the block existed gain it on upgrade without losing any hand-edited
   §0 identity. If the subsection is already present, keep the repo's version verbatim.
3. Show a diff of the generic body (§1+) and ask for confirmation before writing.
4. **Refresh `qmd_sync.sh`** (repo root) from `templates/qmd_sync.sh` — it is plugin-owned
   and copied verbatim (no placeholders), so it must track the plugin on upgrade:
   - Missing → copy it in, `chmod +x`.
   - Present and identical → nothing to do.
   - Present but differs → show a diff and ask for confirmation before overwriting
     (a user *may* have hand-edited it); on confirm, copy and keep it executable.
5. **Append missing optional config blocks** to `wiki.config.yaml` — the config
   counterpart of step 2's Documentation-Domain-Context rule: repos created
   before an optional block existed gain it on upgrade, commented and inert,
   without losing a single hand-edited line. Deterministic — never edit the
   config yourself:
   a. `python "${CLAUDE_PLUGIN_ROOT}/scripts/config_upgrade.py"` (dry-run) —
      prints the blocks that would be appended (`docs:`, `synth_tuning:`,
      `ignore:`, `defect_review:` when absent; a key present at top level,
      active or commented, always leaves the repo's version alone).
   b. Show the human the dry-run output; on confirmation, re-run with
      `--write`. "All optional blocks present" → nothing to do.
6. **OKF migration (pre-OKF wikis only).** Detect a pre-OKF wiki: content pages
   missing `title:`/`description:` frontmatter, or `## [` event headings in
   `wiki/log.md`, or no `okf_version` in `wiki/index.md`. If detected:
   a. `python "${CLAUDE_PLUGIN_ROOT}/scripts/migrate_okf.py"` (dry-run) — show the
      human the report (pages touched, needs-description list, unparsed log lines).
   b. On **explicit confirmation only**, run with `--write`.
   c. For each page on the `needs-description` report, read the page and write a
      one-line `description:` yourself (it becomes the index catalog entry); show
      the human the list of descriptions you wrote.
   d. Verify: `python "${CLAUDE_PLUGIN_ROOT}/scripts/lint_wiki.py"` and
      `python "${CLAUDE_PLUGIN_ROOT}/scripts/build_index.py" --check` both clean
      (advisory `description-long` WARNs are expected on wikis with paragraph-length
      index summaries — surface them, don't fix them mechanically).
   Skip this step entirely when no pre-OKF marker is found.
7. **Never** touch `raw/`. `wiki.config.yaml` is **append-only** (step 5:
   missing optional blocks, commented, diff-confirmed) — existing lines are
   never modified. `CLAUDE.md` and `qmd_sync.sh` are the normal upgrade
   surface; `wiki/` is modified **only** by the explicit, human-confirmed
   OKF migration in step 6.

## Guardrails
- Never overwrite an existing `wiki.config.yaml` or non-empty `wiki/` during bootstrap;
  if present, switch to upgrade mode.
- Never invent §0 facts — ask.
