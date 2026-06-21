---
name: wiki-lint
description: Health-check the wiki — mechanical (deterministic script) plus semantic (Opus) checks. Run standalone any time, or invoked automatically by the /wiki-ingest synth lint gate.
---

# Lint the Wiki

Two tiers. Run both (default) or just the mechanical tier with `mechanical`.

## 1. Mechanical (always; deterministic)
Run `python "${CLAUDE_PLUGIN_ROOT}/scripts/lint_wiki.py"`. Deterministic checks: broken `[[wikilinks]]`,
orphan pages, duplicate slugs, `index.md` drift, frontmatter gaps. Exit 0 = clean,
non-zero = issues (printed). This is cheap — safe to run often and forward. It also
emits advisory `WARN` lines (`context-ref-leak`, `supersession-leak`) that never
affect the exit code — these are candidate lists for semantic passes 5 and 3 below.

If the arg is `mechanical`, stop here and report the output. The mechanical tier is pure
Python: it touches no model and no qmd index.

## 2. Semantic (Opus subagent)
First refresh the search index so the semantic pass queries current content:
`qmd update && qmd embed`. If `qmd` is missing or the refresh fails, continue without it
and note `qmd-unavailable` in the report and the `lint` line in `log.md`; never block the
lint.

Then, only when no synth/extract subagent is running (lint writes to `wiki/`), **spawn one
Opus lint subagent** (Agent tool, `subagent_type: general-purpose`, `model: opus`)
with the **canonical lint prompt** at `${CLAUDE_PLUGIN_ROOT}/skills/wiki-lint/lint-prompt.md`,
substituting the mechanical output into its `<paste lint_wiki.py output here>` slot.
Wait for it and report. This is the single source of truth for the semantic passes —
the `/wiki-ingest` synth lint gate passes the same file to its subagent.

On `BLOCKED`, surface the issues and do not guess. This same tier is what the
`/wiki-ingest` synth lint gate invokes every 20 sources.
