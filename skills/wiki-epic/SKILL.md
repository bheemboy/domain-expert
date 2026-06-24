---
name: wiki-epic
description: Break a broad objective into an epic and its child stories, grounded in the domain-expert wiki. Proposes a numbered breakdown, waits for approval, then auto-writes all stories. Drafts in conversation; saves Markdown only on explicit command.
---

# Wiki Epic

Break a broad objective into an epic + child stories, grounded in the wiki. Same
methodology as `wiki-story`, one altitude up.

## Always load first (shared brain — the same files wiki-story uses)

- [../wiki-story/references/wiki-grounding.md](../wiki-story/references/wiki-grounding.md) — qmd-first discovery + reading the wiki
- [../wiki-story/references/story-format.md](../wiki-story/references/story-format.md) — A/C vs D/N vs Q/N rules, voice, common mistakes
- [../wiki-story/references/story-personas.md](../wiki-story/references/story-personas.md) — persona selection + default roster
- [../wiki-story/references/story-sizing.md](../wiki-story/references/story-sizing.md) — INVEST, sizing, splitting, checklist
- [../wiki-story/references/story-examples.md](../wiki-story/references/story-examples.md) — worked examples

## Workflow

1. **Ground** the objective (../wiki-story/references/wiki-grounding.md):
   qmd-first gate, pull relevant wiki pages + prior Jira exemplars. Ask about
   anything not in the wiki.
2. **Propose the breakdown** — epic framing (objective, value) + a NUMBERED list
   of child-story titles with one-line descriptions; note dependencies (e.g.,
   "1 before 2"). **Wait for approval. Do not write stories yet.**
3. **On approval, auto-write** every child story in full (Description, A/C, D/N,
   Q/N) per ../wiki-story/references/story-format.md, using the shared rules.
4. **Iterate** — refine any story or the breakdown across turns. Still NOTHING
   on disk.
5. **Persist only on explicit command:**
   - **"save as MD"** → run the pre-submission checklist
     (../wiki-story/references/story-sizing.md) on each story; write the single
     epic file and commit (see Saving).
   - **"add to Jira"** → reply that Jira write is not implemented in v1
     (planned seam); offer "save as MD" instead.

## Saving (MD)

- **One file:** `stories/<epic-slug>.md` at the wiki repo root.
- **Structure:** epic framing first, then each child story under a
  `## Story: <title>` boundary (machine-readable for the future Jira step), each
  ending with its own `## Grounding` footer.
- Slug = kebab-case of the epic title. If the file exists, confirm append vs.
  overwrite — never silently clobber.
- Commit after writing.

## Guardrails

- Not a wiki repo → stop with a clear message.
- A/C stays clean; provenance goes in each story's `## Grounding` footer.
- Ask, don't invent.
