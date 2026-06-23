# Wiki-backed story & epic authoring — design

**Date:** 2026-06-23
**Status:** Approved (design); ready for implementation planning
**Plugin:** `domain-expert`

## Summary

Extend the `domain-expert` plugin from a knowledge **extractor** (sources → wiki)
into a knowledge **consumer** that authors Jira-style stories and epics grounded
in the wiki. Two new skills — `wiki-story` and `wiki-epic` — share one
methodology reference set and read the wiki as live domain context. Output is
Markdown only in v1; "add to Jira" is a deliberate future seam.

The methodology (INVEST, A/C vs D/N vs Q/N, persona selection, sizing/splitting,
common mistakes) is adapted from the standalone `writing-stories` skill
(`bheemboy/cid-knowledge`). What makes these skills different: they ground every
story in the actual wiki (`concepts/`, `processes/`, `rules/`, `terminology/`,
`entities/`) and in real prior Jira tickets, instead of a hand-written
domain-context section.

## Goals

- Author a single story (`wiki-story`) or an epic with its child stories (`wiki-epic`).
- Ground stories in the wiki via qmd-first discovery; never invent facts not in the wiki.
- Iterate on drafts **in conversation**; persist only on explicit command.
- Save Markdown to `stories/` in the wiki repo, keeping an epic and its stories together.
- Tighten the qmd-first discovery rule across the existing skills too.

## Non-goals (v1)

- No Jira **write** (create tickets). Recognized as a save target; replies "not implemented in v1".
- No configurable persona roster yet (built-in defaults now; config seam left).
- No new Python scripts (skills are prompt-only in v1).

## Decisions (from brainstorming)

| # | Decision |
|---|----------|
| Output | Markdown drafts only in v1. Jira write deferred behind a clean "save target" seam. |
| Personas | Infer at authoring time from a built-in default roster (`user`, `admin`, `support engineer`, …); confirm if ambiguous. `wiki.config.yaml` `personas:` key reserved as the future configurable-roster seam. |
| Packaging | Two skills + one shared reference set (Option B). `wiki-epic` delegates to `wiki-story`'s shared rules. |
| Epic flow | `wiki-epic` proposes a breakdown, waits for approval, then **auto-writes** the child stories. |
| Persistence | No eager writes. Iterate in conversation; persist on explicit "save as MD". |
| File layout | Flat `stories/` at the wiki repo root: one file per epic (epic + stories inline), one file per standalone story. |

## Components & packaging

```
skills/
  wiki-story/
    SKILL.md                 # write ONE story (standalone, or appended into an existing epic file)
    references/              # the shared brain — both skills load these
      story-format.md        # A/C vs D/N vs Q/N rules, voice/tone, common mistakes
      story-personas.md      # persona-selection method + built-in default roster
      story-sizing.md        # INVEST, sizing, splitting, pre-submission checklist
      story-examples.md      # worked examples
      wiki-grounding.md      # NEW: qmd-first discovery + how to read the wiki as domain context
  wiki-epic/
    SKILL.md                 # breakdown → approve → auto-write stories into one epic file
```

- `wiki-epic/SKILL.md` references `../wiki-story/references/*.md` by relative path so the
  methodology has a single source of truth (no duplication, no drift).
- `references/story-*.md` are adapted from the `writing-stories` skill; `wiki-grounding.md`
  is new and domain-expert-specific.

## Wiki grounding (the novel part)

How a skill grounds a story:

1. **qmd-first discovery (hard gate).** See "qmd-first rule" below. Use `qmd` over the
   `wiki` collection (and `raw` for prior Jira stories) when present; `grep` only when absent.
2. **Pull** the matching `concepts/`, `processes/`, `rules/`, `terminology/`, `entities/`
   pages and their `sources:` (Jira keys).
3. **Exemplars.** Use real prior Jira tickets under `raw/imports/jira/` as product-specific
   format/voice examples, on top of the generic `story-examples.md`.
4. **Ground the draft.**
   - A/C, D/N, Q/N stay clean per the format rules (no citations inside A/C).
   - Each saved file ends with a `## Grounding` footer listing the wiki pages and Jira keys
     that informed it (provenance, on-brand with the plugin, useful for review and the future
     Jira step).
   - If the objective references something not in the wiki, **ask** rather than invent.

### Personas

- Built-in default roster baked into `story-personas.md`: `user`, `admin`,
  `support engineer`, and a couple more.
- Selected at authoring time from the objective + `entities/`; confirm when ambiguous.
- A `wiki.config.yaml` `personas:` key is the documented seam for the future configurable
  roster; when present it overrides the defaults.

## qmd-first rule (applies to new and existing skills)

Discovery/lead-finding over the wiki must prefer `qmd` whenever present — not default to grep.

1. **Cheap presence gate (always run it):** `qmd status`. Pass = `.qmd/` exists, the `qmd`
   binary runs, and status returns cleanly.
2. **If qmd is present → use it** for discovery. No silent skipping.
3. **Fall back to `grep` only when qmd is genuinely absent** (no `.qmd/`, binary missing, or
   status errors). The status check *is* the cheap step — never grep "to save time".

The canonical wording lives once in `references/wiki-grounding.md`. Existing skills get the
same rule inline:

- **`wiki-ingest/synth-prompt.md` (lines 11–14):** rewrite the "you may use qmd … fall back to
  grep" wording into the hard gate above. **Leave the rename-sweep grep (lines 45–46)
  untouched** — there `grep` over `wiki/` is the authoritative worklist and qmd hits are only
  leads; that is correct.
- **`wiki-lint/SKILL.md`:** the index *refresh* wording (lines 23–24) is fine as-is; apply the
  gate to any related-page **lookup** step.
- **`wiki-queue`:** no qmd usage today — no change.

## Workflows

### `wiki-story` (single story)

1. Resolve target: standalone, or "into epic `<slug>`" (append to that epic file).
2. qmd-first grounding → relevant wiki pages + prior Jira exemplars.
3. Select persona (default roster); confirm if ambiguous.
4. Draft the story **in conversation** — Description, A/C, D/N, Q/N. Nothing written to disk.
5. **Iterate** across turns on user feedback.
6. On explicit **"save as MD"**: run the `story-sizing.md` pre-submission checklist
   (self-review, flag failures); write/append the file under `stories/`; add the
   `## Grounding` footer; commit.

### `wiki-epic` (epic + stories)

1. qmd-first grounding for the broad objective.
2. Propose **epic framing + numbered child-story list** (titles + one-liners; note
   dependencies). **Wait for approval.**
3. On approval, **auto-write all child stories** in conversation using the shared rules.
4. **Iterate** — refine any story or the breakdown across turns. Still nothing on disk.
5. On **"save as MD"**: write the single `stories/<epic-slug>.md` (epic framing + all stories
   inline, each under a machine-readable `## Story: <title>` boundary for the future Jira
   step); self-review; commit.

"add to Jira" is recognized as a save target but in v1 replies that it is not yet implemented.

## File layout & format

```
stories/
  <epic-slug>.md                # epic framing + all child stories, inline
  <standalone-story-slug>.md    # one standalone story
```

- Filenames are slug-based (no date prefix); the slug is the story/epic identity.
- Each story (standalone file or section within an epic file) uses a consistent
  `## Story: <title>` boundary so the future "add to Jira" step parses one epic ticket + N
  child tickets cleanly.
- Story body: Description (with `As a <persona>, I want … so that …`), A/C, D/N, Q/N per
  `story-format.md`, then a `## Grounding` footer (wiki pages + Jira keys).

## Error handling

- **Not a wiki repo** (no `wiki.config.yaml` / `wiki/`) → stop with a clear message.
- **qmd status errors** → fall back to `grep`, note `qmd-unavailable`; never block.
- **No relevant wiki pages found** → say so and ask; do not author from nothing.
- **Unknown term** (not in wiki) → ask the user to clarify; research only if asked.
- **Persona ambiguous** → ask, don't guess.
- **Story targeted into an epic, but that epic file is missing** → list existing epics, offer to create.
- **Save would overwrite** (slug/epic file exists) → confirm append vs. overwrite; never
  silently clobber.
- **"add to Jira"** → recognized; replies "not implemented in v1" (the seam).

## Testing strategy

v1 is prompt-only (no new Python), so:

- A documented **manual eval checklist** against the live wiki: standalone story; epic
  breakdown → approve → write; qmd-present vs qmd-absent paths; unknown-term → ask;
  overwrite → confirm.
- **Golden-output checks:** a saved story passes the `story-sizing.md` pre-submission
  checklist; an epic file's `## Story:` boundaries parse cleanly.
- Existing `pytest` suite stays green. If "add to Jira" later adds a parser script, that gets
  unit tests under `tests/`.

## Future seams (not built in v1)

- **Add to Jira:** create epic + linked child stories via the Jira write API; ADF body
  formatting; dedup against existing tickets. The `## Story:` boundary + `## Grounding`
  footer + flat `stories/` layout are designed to make this a parse-and-post step.
- **Configurable persona roster:** `wiki.config.yaml` `personas:` overrides the built-in
  defaults.
```
