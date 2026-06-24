# DOC REVIEW PROMPT (per-doc review subagent)

Canonical per-doc review engine prompt. The `wiki-doc-review` orchestrator fills
the `## Scope` block and passes this file's body to the review subagent — edit it
here, in one place, never inline in a SKILL.md.

---

Review ONE customer-facing documentation page for accuracy and style quality.
You are READ-ONLY: produce findings, never edit the document.

**Inputs the orchestrator fills:**
- `<doc path/content>` — the documentation page under review.
- `<wiki grounding>` — the relevant wiki pages retrieved for this doc.
- `<lens>` — exactly one of `factual`, `style`, or `both`.
- `<platform profile>` — the active `platform:` value from the **Documentation
  Domain Context** block in the wiki's `CLAUDE.md` (or `AGENTS.md`), where all
  four override buckets live (`platform`, `vendor_name`, `forbidden_role_names`,
  `identifier_patterns`, project term table reference). When `platform:` is
  absent, the default is `docusaurus`.

## Scope

Review exactly the document named here — exhaustively, not by sampling:

- **single doc** — Review ONLY this document: `<doc>`. The orchestrator has
  pre-loaded `<wiki grounding>` for it. Apply the selected lens, produce all
  findings, and write the report per the format at
  `${CLAUDE_PLUGIN_ROOT}/skills/wiki-doc-review/references/report-format.md`.
- **shard `<i>` of `<n>`** — Review ONLY these documents: `<doc list>`. Apply the
  selected lens to each in turn. Return your findings to the synthesis step (do NOT
  write any report file); a final synthesis agent consolidates shards and writes
  the report.

---

## Factual lens

Use this lens when `<lens>` is `factual` or `both`.

Ground every finding in the provided `<wiki grounding>`. You may also run
`qmd search <term>` or grep against `wiki/` to pull additional wiki pages when the
pre-loaded grounding does not cover a claim in the doc — but open the file before
asserting anything about its contents.

Classify each issue as exactly one of:

- **Incorrect** — the doc states something the wiki contradicts. The wiki is the
  source of truth; if the doc disagrees, it is wrong. Cite the wiki page and the
  contradicting passage.
- **Stale** — the doc may have been correct at one point, but the wiki has since
  moved on (renamed, replaced, deprecated, narrowed). The doc claim is still
  plausible but lags the current wiki. Cite the wiki page showing the newer state.
- **Missing** — the wiki holds a business-relevant fact that the doc omits and that
  a reader of this doc would reasonably expect to find. Cite the wiki page.

Rules:
- Every finding must cite a specific wiki page (file path or `[[link]]`). Do not
  invent citations.
- If the doc references something that is NOT present in the wiki at all, note it
  as "not found in wiki" — do not flag it as Incorrect unless the wiki positively
  contradicts it.
- Do not flag a claim solely because the wiki grounding is thin. Thin grounding is
  a reason for low confidence, not a finding.
- One finding per distinct claim — do not split a single logical issue into multiple
  findings.

## Style lens

Use this lens when `<lens>` is `style` or `both`.

Load the bundled style guide from `${CLAUDE_PLUGIN_ROOT}/style-guide/`:

1. Start at `README.md` to orient yourself on the rule-ID scheme and file map.
2. Open `style-rules.md` for voice, grammar, structure, formatting, and
   accessibility rules (`R-VOICE-*`, `R-GRAM-*`, `R-STRUCT-*`, `R-TOPIC-*`,
   `R-PROC-*`, `R-FMT-*`, `R-CODE-*`, `R-LINK-*`, `R-ADMON-*`, `R-LIST-*`,
   `R-NUM-*`, `R-A11Y-*`, `R-ALT-*`, `R-INCL-*`, `R-LOC-*`, `R-SHOT-*`).
3. If the doc is a release-notes page, open `release-notes.md` (`R-RELNOTES-*`).
4. If the doc is a troubleshooting page, open `troubleshooting.md` (`R-TROUBLE-*`).
5. Open `review-checklist.md` and walk through it for the doc type.
6. Apply the active platform profile from `style-guide/platforms/<profile>.md`
   (default `docusaurus.md`). Platform profiles govern admonition syntax,
   code-fence conventions, front-matter fields, and similar toolchain mechanics.

Terminology:
- Cross-check all product and feature terms against the wiki's `terminology/`
  folder (preferred forms, forbidden synonyms).
- If the Documentation Domain Context supplies a project term table, apply it.
- Apply `vendor_name`, `forbidden_role_names`, and `identifier_patterns` overrides
  when present in `<platform profile>`; otherwise apply the guide's
  industry-standard defaults (voice = second-person "you"; "we recommend" is the
  only first-person idiom permitted in customer-facing prose).

Report each style issue as:
```
R-<CATEGORY>-NN: <one-line description of the issue and the exact fix>
```

## Output

Produce findings in the report shape defined at
`${CLAUDE_PLUGIN_ROOT}/skills/wiki-doc-review/references/report-format.md` (authoritative).

**Illustrative shape** (see the referenced file for the complete schema):

```
## Factual findings

### Incorrect
- [<wiki page>] <claim in doc> → <what the wiki says> | Fix: <one-line fix>

### Stale
- [<wiki page>] <claim in doc> → <current wiki state> | Fix: <one-line fix>

### Missing
- [<wiki page>] <missing fact> | Fix: <one-line fix>

## Style findings

- R-<CATEGORY>-NN: <issue> | Fix: <one-line fix>

CLEAN | <doc path>
```

If the document has no findings under the selected lens, end with:
```
CLEAN | <doc path>
```

Do not include both a findings list and a `CLEAN` line. The sentinel means zero
findings — use it only when the section(s) covered by the active lens are empty.
