---
name: wiki-story
description: Write a single Jira-style user story (A/C, D/N, Q/N) grounded in the domain-expert wiki. Use when the user gives a focused story title or description, optionally targeting an existing epic. Drafts in conversation; saves Markdown only on explicit command.
---

# Wiki Story

Author ONE user story, grounded in the wiki, for an internal engineering/QA
audience — direct, functional, no marketing language.

## Always load first (the shared brain)

- [references/wiki-grounding.md](references/wiki-grounding.md) — qmd-first discovery + reading the wiki as domain context
- [references/story-format.md](references/story-format.md) — A/C vs D/N vs Q/N rules, voice/tone, common mistakes
- [references/story-personas.md](references/story-personas.md) — persona selection + the default roster
- [references/story-sizing.md](references/story-sizing.md) — INVEST, sizing, splitting, the pre-submission checklist
- [references/story-examples.md](references/story-examples.md) — worked examples

## Workflow

1. **Resolve target.** A standalone story, or one "into epic `<slug>`". If
   targeting an epic whose file `stories/<slug>.md` is missing, list existing
   epics under `stories/` and offer to create it. Do not create any file yet.
2. **Ground** (references/wiki-grounding.md): run the qmd-first gate, pull
   relevant wiki pages + prior Jira exemplars. If the objective references
   something not in the wiki, ASK — do not invent.
3. **Select persona** from the default roster (references/story-personas.md);
   confirm if ambiguous.
4. **Draft in conversation** — Title, Description (`As a <persona>, I want …
   so that …`), A/C, D/N, Q/N per references/story-format.md. Write NOTHING
   to disk yet.
5. **Iterate** with the user across turns.
6. **Persist only on explicit command:**
   - **"save as MD"** → run the pre-submission checklist
     (references/story-sizing.md), flag any failures; then write the file and
     commit (see Saving).
   - **"add to Jira"** → reply that Jira write is not implemented in v1
     (planned seam); offer "save as MD" instead.

## Saving (MD)

- **Standalone:** `stories/<story-slug>.md` at the wiki repo root.
- **Into an epic:** append a `## Story: <title>` section to `stories/<epic-slug>.md`.
- Every story ends with a `## Grounding` footer (wiki pages + Jira keys) per
  references/wiki-grounding.md.
- Slug = kebab-case of the title. If the target file/section already exists,
  confirm append vs. overwrite — never silently clobber.
- Commit the file after writing.

## Guardrails

- Not a wiki repo (no `wiki.config.yaml` / `wiki/`) → stop with a clear message.
- Never put provenance citations inside A/C — they go in the `## Grounding` footer.
- Ask, don't invent (references/wiki-grounding.md).
