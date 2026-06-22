# LINT PROMPT (Opus lint subagent)

Canonical semantic-lint prompt. Both `wiki-lint` (standalone) and the `wiki-ingest`
synth lint gate pass this file's body to the Opus lint subagent — edit it here, in
one place, never inline in a SKILL.md.

---

Semantic health-check of the wiki (`wiki/`) per `CLAUDE.md` §5 Lint.
Mechanical output from `scripts/lint_wiki.py` is below. Fix safe mechanical issues,
then run the semantic passes below. Do not treat these as product-specific checks;
they are general claim-lifecycle checks for an evolving product.

Mechanical output:
```
<paste lint_wiki.py output here>
```

## Scope

Audit exactly the page set named here — exhaustively, not by sampling:

- **delta** — Audit ONLY these pages (changed since the last lint) and the listed
  1-hop neighbors: `<page list>`. Evaluate the global passes (summary-page
  consistency, concept-split) *as they bear on these pages* — i.e. check whether
  these changes affect `index.md` / `overview.md` / `glossary.md`, not a full
  summary-vs-everything reconciliation. Append a `lint | <auto|manual>` line to
  `wiki/log.md`.
- **full, shard `<i>` of `<n>`** — Audit ONLY these pages: `<shard list>`. Return
  your findings to the synthesis step (do not write `log.md`); a final synthesis
  agent reconciles cross-shard contradictions, checks the summary pages against
  the whole set, and appends one `lint --full | manual` line to `wiki/log.md`.

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

5. **Retrieval robustness — context-dependent claims & unstated preconditions.**
   The wiki is read both by following `[[links]]` and by fragment retrieval
   (qmd/grep), so each section must stand on its own. The mechanical tier emits
   `context-ref-leak` WARNs (deictic phrases with no resolving cross-link) — triage
   those, and also hunt what it cannot see. Flag (and, where safe, fix) two patterns:
   - **Unstated precondition/gate.** A section stating that something *works / is
     enabled / is shown / is dispatched / is allowed* whose governing precondition,
     state, exception, or constraint lives in **another section or page** with no
     cross-reference from the mechanism site. Test: *would a reader who landed only
     on this section be misled?* Fix = add a bidirectional cross-link (anchor or
     `[[page#heading]]`) between the mechanism and its gate.
   - **Fragile deictic reference.** A current claim relying on "this/that state",
     "in that case", "as described above", etc., whose antecedent is a heading or
     earlier bullet rather than local text. Fix = name the antecedent inline or
     link to where it is defined.
   Scope to avoid noise: ignore deixis whose antecedent is in the same sentence or
   bullet — only flag when meaning depends on a *different* section/page. Adding a
   cross-link or naming an antecedent is meaning-preserving → auto-fixable under the
   safe-fix rule; deciding whether a precondition genuinely gates a mechanism needs
   product judgment → `BLOCKED` if unsure.

6. **Concept structure.** Check for concepts mentioned but lacking a page, pages
   that now cover two concepts and should split, and contradictions between pages.

7. **Lint-config suggestions (advisory).** As you check renames (passes 1-3), note any
   *genuine product-noun* rename whose retired name isn't yet policed by the lint config
   (`wiki.config.yaml` `lint.flaggable_nouns` / `brand_nouns`). Propose the **category
   noun** to add (e.g. a renamed `"… Cabinet"` → suggest `Cabinet`; a retired
   `*-<brand>-Instrument` → suggest the old brand token). **Use judgment** — ignore the
   junk the `→`-harvester catches (version bumps, error messages, file paths, prose).
   This is how a project (especially a fresh one with an empty `lint:` section) grows its
   config from observed renames instead of guessing up front. **Surface the proposal to
   the human; do NOT edit `wiki.config.yaml` yourself** — it is human-curated config.

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
  If pass 7 produced any, append `; lint-config: add <noun>, <noun> to <list>` to the
  return line (a proposal for the human, not a change you made).
