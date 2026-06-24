# Doc Review Report Format

Authoritative schema for findings produced by the `wiki-doc-review` engine
prompt. Per-doc sections come first, then a per-run summary.

---

## Per-doc section

Each reviewed document gets its own section, in the order the resolver returned
the files.

### Header line

```
## <doc path>
```

Use the absolute path as returned by `doc_scope.py`. This is the section
heading — one per doc.

### Factual findings (lens: `factual` or `both`)

```
### Factual findings

#### Incorrect
- [<wiki page path or [[wikilink]]>] <claim as stated in the doc> → <what the wiki says> | Fix: <one-line fix>

#### Stale
- [<wiki page path or [[wikilink]]>] <claim as stated in the doc> → <current wiki state> | Fix: <one-line fix>

#### Missing
- [<wiki page path or [[wikilink]]>] <fact the wiki holds that the doc omits> | Fix: <one-line fix>
```

Rules:
- Every finding cites a specific wiki page. No invented citations.
- One bullet per distinct claim — do not split a single logical issue.
- If the factual lens is active but the section has zero findings, omit the
  section and use the `CLEAN` sentinel (see below).

### Style findings (lens: `style` or `both`)

```
### Style findings
- R-<CATEGORY>-NN: <issue description and exact fix>
```

Rules:
- Use the rule ID from the style guide (`R-VOICE-*`, `R-GRAM-*`, `R-STRUCT-*`,
  `R-TOPIC-*`, `R-PROC-*`, `R-FMT-*`, `R-CODE-*`, `R-LINK-*`, `R-ADMON-*`,
  `R-LIST-*`, `R-NUM-*`, `R-A11Y-*`, `R-ALT-*`, `R-INCL-*`, `R-LOC-*`,
  `R-RELNOTES-*`, `R-TROUBLE-*`, `R-SHOT-*`).
- One bullet per distinct style issue.
- If the style lens is active but the section has zero findings, omit the
  section and use the `CLEAN` sentinel.

### Clean sentinel

When a doc has no findings under the active lens (either lens returns nothing,
or both are clean):

```
CLEAN | <doc path>
```

Do not include both a findings list and a `CLEAN` sentinel for the same doc.

---

## Per-run summary

Append after all per-doc sections.

```
---

## Summary

**Docs reviewed:** N
<list of paths, one per line>

**Totals**
- Incorrect: N
- Stale: N
- Missing: N
- Style (R-*): N
- Clean: N
```

Include `Clean` in totals. Note that "Clean" means docs with zero findings
across all active lenses, not a count of individual findings. Keep totals
unambiguous: `Style (R-*)` is the count of individual style rule violations,
not the number of docs with style issues.

Under a single-lens run (`factual` or `style` only), omit the inactive lens's
counts from the totals. `CLEAN | <path>` / `Clean` means a doc had no findings
**under the active lens(es)**.

---

## Full example (illustrative)

```
## /docs/feature-setup.md

### Factual findings

#### Incorrect
- [[concepts/auth-flow]] The doc states tokens expire after 24 hours → wiki says
  tokens expire after 1 hour. | Fix: Change "24 hours" to "1 hour".

#### Missing
- [[processes/role-assignment]] The doc omits role-assignment prerequisites that
  the wiki lists as required before setup. | Fix: Add a Prerequisites section
  referencing role assignment.

### Style findings
- R-STRUCT-02: Page has no introductory paragraph before the first heading. | Fix:
  Add a one-sentence overview of what this page covers.
- R-VOICE-01: "The user must click..." uses third person. | Fix: Change to "Click...".

---

## /docs/api-reference.md

CLEAN | /docs/api-reference.md

---

## Summary

**Docs reviewed:** 2
/docs/feature-setup.md
/docs/api-reference.md

**Totals**
- Incorrect: 1
- Stale: 0
- Missing: 1
- Style (R-*): 2
- Clean: 1  # Clean = docs with zero findings under the active lens(es)
```
