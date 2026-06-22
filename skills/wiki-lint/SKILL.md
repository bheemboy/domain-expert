---
name: wiki-lint
description: Health-check the wiki — mechanical (deterministic script) plus semantic (Opus) checks. Run standalone any time, or invoked automatically by the /wiki-ingest synth lint gate.
---

# Lint the Wiki

Tiers below. Args: `mechanical` (deterministic only), `--full` (exhaustive whole-wiki
semantic), or none (delta — changed since last lint + neighbors). Mechanical always runs first.

## 1. Mechanical (always; deterministic)
Run `python "${CLAUDE_PLUGIN_ROOT}/scripts/lint_wiki.py"`. Deterministic checks: broken `[[wikilinks]]`,
orphan pages, duplicate slugs, `index.md` drift, frontmatter gaps. Exit 0 = clean,
non-zero = issues (printed). This is cheap — safe to run often and forward. It also
emits advisory `WARN` lines (`context-ref-leak`, `supersession-leak`) that never
affect the exit code — these are candidate lists for semantic passes 5 and 3 below.

If the arg is `mechanical`, stop here and report the output. The mechanical tier is pure
Python: it touches no model and no qmd index.

## 2. Semantic (Opus subagent) — delta (default) or `--full`

First refresh the search index: `qmd update && qmd embed --max-batch-mb 1` (the 1 MB batch
cap avoids `qmd embed` timeouts on slower machines). If `qmd` is missing or the
refresh fails, continue and note `qmd-unavailable`; never block the lint.

Resolve the page set deterministically, then spawn the Opus engine over it. Only run when
no synth/extract subagent is writing to `wiki/`.

**Delta (default — `/wiki-lint`).** Audit what changed since the last deliberate lint:
1. `python "${CLAUDE_PLUGIN_ROOT}/scripts/lint_scope.py" delta` → the page set (neighbor-
   expanded), one slug per line. If empty, report `CLEAN | nothing changed since last lint`
   and stop — do not spawn a subagent.
2. Spawn one Opus subagent (`subagent_type: general-purpose`, `model: opus`) with
   `${CLAUDE_PLUGIN_ROOT}/prompts/lint-prompt.md`, filling the `## Scope` **delta** option
   with that page list and the mechanical output. It appends a `lint | manual` line.

**Full (`/wiki-lint --full`).** Exhaustive whole-wiki audit:
1. `python "${CLAUDE_PLUGIN_ROOT}/scripts/lint_scope.py" full` → one shard (comma-separated
   slugs) per line.
2. Spawn one Opus subagent per shard with the prompt's `## Scope` **full, shard i of n**
   option; each returns findings (does not write `log.md`).
3. Spawn one final Opus synthesis subagent with all shard findings + `index.md`,
   `overview.md`, `glossary.md`: reconcile cross-shard contradictions, check the summary
   pages against the whole set, apply safe fixes, and append one `lint --full | manual` line.

Report the subagent return verbatim. On `BLOCKED`, surface and do not guess.
