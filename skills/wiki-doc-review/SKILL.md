---
name: wiki-doc-review
description: Review customer-facing online docs or help content against the wiki for stale, incorrect, or missing information, and for style conformance. Use when the user asks to review docs / online help for accuracy, freshness, or style.
---

# Wiki Doc Review

Review one or more customer-facing documentation pages against the wiki — the
single source of truth. READ-ONLY throughout: produce findings, never edit the
docs.

**Args:** `[<path|folder>] [factual|style|both]`

- `<path|folder>` — a single doc file, a folder of docs, or omit for all
  configured docs.
- `factual | style | both` — the review lens. Defaults to `both`.

---

## 1. Guardrails

Check that the current repo is a domain-expert wiki repo:

```
test -f wiki.config.yaml && test -d wiki/
```

If either is missing → **stop** with:

> This skill requires a domain-expert wiki repo (`wiki.config.yaml` + `wiki/`
> directory). No wiki found here — run `/wiki-init` first.

---

## 2. Resolve scope

Run the resolver, passing the user's path arg if one was given (omit the arg
when none was given):

```bash
python "${CLAUDE_PLUGIN_ROOT}/scripts/doc_scope.py" [<path|folder>]
```

This prints one absolute doc path per line (all configured docs when no arg is
given, the single file when a file is given, or all `.md`/`.mdx` files under
the folder).

**If the resolver returns nothing:**

- Check `wiki.config.yaml` for a `docs:` block.
- If `docs:` is absent, explain how to add it — do NOT guess a folder:

  > No docs are configured. Add a `docs:` block to `wiki.config.yaml` that
  > points at the product's online-help root, for example:
  >
  > ```yaml
  > docs:
  >   root: ../my-product-docs/docs
  > ```
  >
  > Then re-run `/wiki-doc-review`.

- If `docs:` is present but the resolver still returns nothing, report the
  empty scope and stop — do not fabricate a file list.

**Echo the exact file list** before proceeding. No silent sampling. If no lens
arg was given, the default is `both`.

```
Reviewing N doc(s) [lens: <lens> (default: both if omitted)]:
  <absolute path 1>
  <absolute path 2>
  …
```

---

## 3. Refresh + ground

### 3a. Index refresh

```bash
qmd update && qmd embed --max-batch-mb 1
```

If `qmd` is missing or the command fails, note `qmd-unavailable` and continue —
never block the review.

### 3b. Per-doc grounding (qmd-first gate)

For each doc to be reviewed, retrieve the relevant wiki pages that cover the
same topic area.

1. **Cheap presence gate — ALWAYS run it first:** `qmd status`.
   Pass = `.qmd/` exists, the `qmd` binary runs, and status returns cleanly.
2. **If qmd is present → USE it:**
   - Extract two or three key nouns from the doc's title or opening paragraph.
   - `qmd search "<key nouns>"` over the `wiki` collection.
   - Open each hit before relying on it.
3. **Fall back to `grep` ONLY when qmd is genuinely absent** (no `.qmd/`,
   binary missing, or `qmd status` errors). Note `qmd-unavailable`.

Do NOT default to grep when `.qmd/` is present. The `qmd status` check IS the
cheap step.

Also search the wiki for topics the doc covers — hits that do NOT appear in the
doc are **Missing** candidates for the factual lens.

---

## 4. Run the lens(es)

Determine scope size from the file list resolved in step 2.

### Single doc

Fill the `## Scope` **single doc** option in
`${CLAUDE_PLUGIN_ROOT}/prompts/doc-review-prompt.md` with:

- the doc path
- its wiki grounding (the grounding pages retrieved in step 3b)
- the lens (`factual`, `style`, or `both`)
- the active platform profile — the `platform:` value from `wiki.config.yaml`
  (default `docusaurus`) plus any Documentation Domain Context overrides
  (`vendor_name`, `forbidden_role_names`, `identifier_patterns`, project term
  table reference).

Produce findings inline; write the report per
`${CLAUDE_PLUGIN_ROOT}/skills/wiki-doc-review/references/report-format.md`.

### Folder or all docs (fan-out)

Mirrors `wiki-lint --full`.

1. Shard the file list into groups of ~8 docs per shard. The orchestrator
   resolves the doc list from step 2 with `python
   "${CLAUDE_PLUGIN_ROOT}/scripts/doc_scope.py" <arg>` (one path per line),
   then groups that list into shards either by calling
   `doc_scope.shard_docs(paths, max_per_shard=8)` from Python, or by chunking
   the printed paths into groups of ~8. The shards are deterministic — use them
   as-is.

2. Spawn one **clean subagent** (`subagent_type: general-purpose`) per shard.
   Each subagent:
   - Receives the engine prompt
     (`${CLAUDE_PLUGIN_ROOT}/prompts/doc-review-prompt.md`) with the `## Scope`
     **shard `<i>` of `<n>`** option filled with that shard's doc list, the
     per-doc grounding for its docs, the active lens, and the platform profile.
   - Returns its shard findings to the orchestrator. It does NOT write any
     report file.

3. Spawn ONE final synthesis subagent with all shard findings. It:
   - Reconciles cross-shard contradictions (same doc cited twice, conflicting
     severity, duplicate findings).
   - Produces the consolidated final report per
     `${CLAUDE_PLUGIN_ROOT}/skills/wiki-doc-review/references/report-format.md`.

---

## 5. Report

Report per `${CLAUDE_PLUGIN_ROOT}/skills/wiki-doc-review/references/report-format.md`.

- READ-ONLY: never modify any doc, wiki page, or config file.
- On `BLOCKED`: surface the blocker verbatim and stop — do not guess or
  fabricate findings.
- If a doc has no findings under the active lens, emit `CLEAN | <doc path>`.
