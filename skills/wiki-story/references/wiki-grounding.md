# Wiki Grounding (shared)

How `wiki-story` and `wiki-epic` ground authored stories in the wiki. Read this
before drafting.

## qmd-first discovery (hard gate)

Discovery over the wiki MUST prefer `qmd` whenever present. Do NOT default to grep.

1. **Cheap presence gate — ALWAYS run it first:** `qmd status`.
   Pass = `.qmd/` exists, the `qmd` binary runs, and status returns cleanly.
2. **If qmd is present → USE it** for discovery:
   - `qmd search "<objective / key nouns>"` (or `qmd query`) over the `wiki`
     collection to find relevant concept / process / rule / entity / terminology pages.
   - Also search the `raw` collection for prior Jira tickets to use as exemplars.
   Treat hits as leads: open each page before relying on it.
3. **Fall back to `grep` ONLY when qmd is genuinely absent** (no `.qmd/`, binary
   missing, or `qmd status` errors). Note `qmd-unavailable`.

- Do: run `qmd status`, then `qmd search …`.
- Don't: skip straight to `grep -ri` when `.qmd/` is present. The status check IS
  the cheap step.

## Reading the wiki as domain context

After discovery, open the matching pages and pull:
- `concepts/`, `processes/`, `rules/`, `entities/`, `terminology/` — the facts the
  story must respect.
- Each page's `sources:` frontmatter (Jira keys) — provenance for the Grounding footer.
- Prior Jira tickets under `raw/imports/jira/<KEY>.md` — real, product-specific
  format/voice exemplars, on top of `story-examples.md`.

## Ask, don't invent

If the objective names a term, capability, rule, or entity NOT found in the wiki,
ASK the user to clarify rather than inventing it. Offer to research (WebFetch)
only if asked. Never fabricate A/C, error handling, or D/N for behavior not
grounded in the wiki or the user's input.

## The Grounding footer

Every saved story (a standalone file, or each `## Story:` section in an epic file)
ends with:

```
## Grounding
- Wiki: [[concept-slug]], [[rule-slug]]
- Jira: PROJ-123, PROJ-456
```

List the wiki pages and Jira keys that informed the story. This is provenance —
keep it OUT of the A/C body (A/C stays clean per story-format.md).

## Not a wiki repo

If there is no `wiki.config.yaml` / `wiki/` in the current repo, stop: these
skills require a domain-expert wiki.
