# LINT PROMPT (Opus lint subagent)

Semantic health-check of the wiki (`wiki/`) per `CLAUDE.md` §5 Lint.
Mechanical output from `scripts/lint_wiki.py` is below. Fix safe mechanical issues,
then run the semantic passes below. Do not treat these as product-specific checks;
they are general claim-lifecycle checks for an evolving product.

Mechanical output:
```
<paste lint_wiki.py output here>
```

First read `wiki/index.md`, `wiki/overview.md`, `wiki/terminology/glossary.md`,
and the most recent lint/synth entries in `wiki/log.md`. These summary pages are
high-risk: their broad current-sounding claims must reflect the newest specific
pages in the linked graph.

You may use `qmd query`/`qmd search` (project index over `raw` + `wiki`) to
hunt contradictions and supersede candidates — hits are leads: open the file
before asserting. If qmd is unavailable, fall back to grep. Follow `[[links]]`
from broad pages into specific pages before deciding a summary is correct.

Mandatory semantic passes:

1. **Temporal claim consistency.** For pages containing claims from multiple
   source dates, check whether older current claims are still compatible with
   newer claims on the same subject. If a newer source changes, narrows, renames,
   replaces, fixes, or invalidates an older claim, the older claim must be scoped
   (version/configuration/product name), moved to `## Superseded`, or flagged.

2. **Summary-page consistency.** Check `overview.md`, `index.md`, and `glossary.md`
   against newer, more specific linked pages. If a summary makes an old broad
   claim and a newer linked page expands/narrows/replaces that scope, update the
   summary or return `BLOCKED`.

3. **Rename/replacement cascade.** When a source renames or replaces a product
   noun, role, privilege, project, report, page, endpoint, storage path, test,
   or workflow, verify related current sections, relationships, glossary entries,
   and index summaries use the newest applicable term or clearly mark historical
   terminology.

4. **Absolute-claim drift.** Pay special attention to current claims using
   `only`, `always`, `never`, `must`, `required`, `not supported`, `disabled`,
   `all`, or `none`. If newer sources add exceptions or additional supported
   cases, the absolute claim must be narrowed or flagged.

5. **Concept structure.** Check for concepts mentioned but lacking a page, pages
   that now cover two concepts and should split, and contradictions between pages.

- **Auto-fix** only safe, unambiguous issues (missing cross-link, broken link
  target, obvious duplicate merge, index/glossary summary drift, clearly stale
  unscoped old claim where the replacement is explicit).
- Do not auto-fix issues that need product judgment, such as whether a newer claim
  replaces an older claim or merely adds another configuration.
- Append one `lint` line to `wiki/log.md`.
- Return:
  - `CLEAN | checked: <pages/passes>; residual-risk: <short note>`
  - `FIXED | <short list>; checked: <pages/passes>; residual-risk: <short note>`
  - `BLOCKED | <issues needing human judgment>; checked: <pages/passes>`
