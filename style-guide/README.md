# Documentation Style Guide

A bundled, 100%-generic documentation style guide grounded in industry-standard
methodology: Microsoft Writing Style Guide, Google developer documentation style
guide, WCAG 2.1, Diátaxis, DITA 1.3, Semantic Versioning 2.0.0, and Keep a
Changelog 1.1.0. All rules carry stable `R-<CATEGORY>-NN` identifiers; gaps in a
sequence mean a rule was dropped by the disposition — do not renumber survivors.
Cite rule IDs in review comments and lint output.

---

## How skills load this guide

The `wiki-doc-review` and `wiki-doc-author` skills read the guide from
`${CLAUDE_PLUGIN_ROOT}/style-guide/`. No additional configuration is needed: all
files in this directory are loaded automatically when those skills run.

---

## Rule-ID scheme and prefix → file map

| Prefix family | File |
|---|---|
| R-VOICE, R-GRAM, R-STRUCT, R-TOPIC, R-PROC, R-FMT, R-CODE, R-LINK, R-ADMON, R-LIST, R-NUM, R-A11Y, R-ALT, R-INCL, R-LOC, R-SHOT | `style-rules.md` |
| R-RELNOTES | `release-notes.md` |
| R-TROUBLE | `troubleshooting.md` |

Additional resources (no rule IDs):

- `review-checklist.md` — structured checklist for doc reviews.
- `terminology-conventions.md` — generic grammar and usage conventions for
  terminology tables (product/feature terms come from the wiki's `terminology/`
  folder, not from this guide).
- `platforms/` — platform-specific formatting profiles (see below).

---

## Override buckets

The guide is fully functional with no overrides, using industry-standard defaults
(voice = second-person "you"; "we recommend" is the only first-person idiom
permitted in customer-facing prose). Four override buckets let a host project
inject project-specific values without modifying the generic guide.

Overrides are sourced from the host wiki's **Documentation Domain Context**
(scaffolded by `wiki-init`) and from the wiki's `terminology/` folder.

### 1. Vendor identity

Keys: `vendor_name`, `forbidden_role_names`

Supply the vendor/product name and any role names the guide must never use
(for example, role names specific to a software platform). The genericity
guard (`scripts/lint_style_guide.py`) rejects these tokens from the bundled
guide itself.

### 2. Identifier patterns

Key: `identifier_patterns`

A list of regex patterns matching product-specific identifiers (part numbers,
record keys, catalog codes, and similar). The lint scope gate uses these to
detect scope leakage; they have no effect on prose rules.

### 3. Platform

Key: `platform` (default: `docusaurus`)

Selects the active platform profile. Valid values correspond to files in
`platforms/`. See **Platform profiles** below.

### 4. Project terminology table

Optional. A reference to the wiki's `terminology/` folder, which carries
product and feature names, preferred forms, and forbidden synonyms. Product
terminology is **not** in this guide — it comes from the wiki.

---

## Platform profiles

Platform profiles define formatting mechanics (admonition syntax, code-fence
conventions, front-matter fields, and similar) that differ across publishing
toolchains.

| Profile file | Use when |
|---|---|
| `platforms/docusaurus.md` | Publishing with Docusaurus (default) |
| `platforms/commonmark.md` | Any CommonMark-compatible toolchain |

Set `platform: commonmark` in the Documentation Domain Context to switch from
the default. With no `platform:` key, `docusaurus` is assumed.
