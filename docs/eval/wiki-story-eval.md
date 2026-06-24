# wiki-story / wiki-epic manual eval

Run these against a real domain-expert wiki repo. Each line is pass/fail.

## wiki-story
- [ ] Standalone story: objective in → grounded draft in conversation, nothing written.
- [ ] "save as MD" → `stories/<slug>.md` created, ends with a `## Grounding` footer.
- [ ] A/C contains no Jira keys / file paths (provenance only in Grounding footer).
- [ ] Into an existing epic: story appended under a new `## Story:` section.
- [ ] Into a missing epic: skill lists epics and offers to create, does not clobber.
- [ ] Unknown term not in the wiki → skill ASKS instead of inventing.
- [ ] Save over an existing slug → skill confirms append vs. overwrite.

## wiki-epic
- [ ] Objective in → numbered breakdown proposed, waits for approval (no writes).
- [ ] After approval → all child stories written in conversation.
- [ ] "save as MD" → single `stories/<epic-slug>.md` with one `## Story:` per child.

## qmd-first gate (all skills)
- [ ] With `.qmd/` present: discovery runs `qmd status` then `qmd search` (not grep).
- [ ] With qmd removed: skill falls back to grep and notes qmd-unavailable.
