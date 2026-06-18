---
name: wiki-lint
description: Health-check the wiki — mechanical (deterministic script) plus semantic (Opus) checks. Run standalone any time, or invoked automatically by the /wiki-ingest synth lint gate.
---

# Lint the Wiki

Two tiers. Run both (default) or just the mechanical tier with `mechanical`.

## 1. Mechanical (always; no LLM)
Run `python "${CLAUDE_PLUGIN_ROOT}/scripts/lint_wiki.py"`. Deterministic checks: broken `[[wikilinks]]`,
orphan pages, duplicate slugs, `index.md` drift, frontmatter gaps. Exit 0 = clean,
non-zero = issues (printed). This is cheap — safe to run often and forward.

If the arg is `mechanical`, stop here and report the output. The mechanical tier is pure
Python: it touches no LLM, no model, and no qmd index.

## 2. Semantic (Opus subagent)
First refresh the search index so the semantic pass queries current content:
`qmd update && qmd embed`. If `qmd` is missing or the refresh fails, continue without it
and note `qmd-unavailable` in the report and the `lint` line in `log.md`; never block the
lint.

Then, only when no synth/extract subagent is running (lint writes to `wiki/`), **spawn one
Opus lint subagent** (Agent tool, `subagent_type: general-purpose`, `model: opus`)
with the prompt below, passing it the mechanical output. Wait for it and report.

> Semantic health-check of the wiki (`wiki/`) per `CLAUDE.md` §5 Lint.
> Mechanical output from `scripts/lint_wiki.py` is below. Fix safe mechanical issues,
> then run the semantic passes below. Do not treat these as product-specific checks;
> they are general claim-lifecycle checks for an evolving product.
>
> Mechanical output:
> ```
> <paste lint_wiki.py output>
> ```
>
> First read `wiki/index.md`, `wiki/overview.md`, `wiki/terminology/glossary.md`,
> and the most recent lint/synth entries in `wiki/log.md`. These summary pages are
> high-risk: their broad current-sounding claims must reflect the newest specific
> pages in the linked graph.
>
> You may use `qmd query`/`qmd search` (project index over `raw` + `wiki`) to
> hunt contradictions and supersede candidates — hits are leads: open the file
> before asserting. If qmd is unavailable, fall back to grep. Follow `[[links]]`
> from broad pages into specific pages before deciding a summary is correct.
>
> Mandatory semantic passes:
>
> 1. **Temporal claim consistency.** For pages containing claims from multiple
>    source dates, check whether older current claims are still compatible with
>    newer claims on the same subject. If a newer source changes, narrows, renames,
>    replaces, fixes, or invalidates an older claim, the older claim must be scoped
>    (version/configuration/product name), moved to `## Superseded`, or flagged.
>
> 2. **Summary-page consistency.** Check `overview.md`, `index.md`, and `glossary.md`
>    against newer, more specific linked pages. If a summary makes an old broad
>    claim and a newer linked page expands/narrows/replaces that scope, update the
>    summary or return `BLOCKED`.
>
> 3. **Rename/replacement cascade.** When a source renames or replaces a product
>    noun, role, privilege, project, report, page, endpoint, storage path, test,
>    or workflow, verify related current sections, relationships, glossary entries,
>    and index summaries use the newest applicable term or clearly mark historical
>    terminology.
>
> 4. **Absolute-claim drift.** Pay special attention to current claims using
>    `only`, `always`, `never`, `must`, `required`, `not supported`, `disabled`,
>    `all`, or `none`. If newer sources add exceptions or additional supported
>    cases, the absolute claim must be narrowed or flagged.
>
> 5. **Concept structure.** Check for concepts mentioned but lacking a page, pages
>    that now cover two concepts and should split, and contradictions between pages.
>
> 6. **Lint-config suggestions (advisory).** As you check renames (passes 1-3), note any
>    *genuine product-noun* rename whose retired name isn't yet policed by the lint config
>    (`wiki.config.yaml` `lint.flaggable_nouns` / `brand_nouns`). Propose the **category
>    noun** to add (e.g. a renamed `"… Cabinet"` → suggest `Cabinet`; a retired
>    `*-<brand>-Instrument` → suggest the old brand token). **Use judgment** — ignore the
>    junk the `→`-harvester catches (version bumps, error messages, file paths, prose).
>    This is how a project (especially a fresh one with an empty `lint:` section) grows its
>    config from observed renames instead of guessing up front. **Surface the proposal to
>    the human; do NOT edit `wiki.config.yaml` yourself** — it is human-curated config.
>
> - **Auto-fix** only safe, unambiguous issues (missing cross-link, broken link
>   target, obvious duplicate merge, index/glossary summary drift, clearly stale
>   unscoped old claim where the replacement is explicit).
> - Do not auto-fix issues that need product judgment, such as whether a newer claim
>   replaces an older claim or merely adds another configuration.
> - Append one `lint` line to `wiki/log.md`.
> - Return:
>   - `CLEAN | checked: <pages/passes>; residual-risk: <short note>`
>   - `FIXED | <short list>; checked: <pages/passes>; residual-risk: <short note>`
>   - `BLOCKED | <issues needing human judgment>; checked: <pages/passes>`
>   If pass 6 produced any, append `; lint-config: add <noun>, <noun> to <list>` to the
>   return line (a proposal for the human, not a change you made).

On `BLOCKED`, surface the issues and do not guess. This same tier is what the
`/wiki-ingest` synth lint gate invokes every 20 sources.
