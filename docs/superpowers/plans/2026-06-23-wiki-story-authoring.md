# Wiki-backed Story & Epic Authoring Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add two prompt-only skills — `wiki-story` and `wiki-epic` — to the `domain-expert` plugin that author Jira-style stories/epics grounded in the wiki, and tighten the qmd-first discovery rule in the existing skills.

**Architecture:** Two new skills under `skills/` share one methodology reference set (`skills/wiki-story/references/`). `wiki-epic` references that set by relative path so there is a single source of truth. A pytest meta-suite guards structure (files exist, frontmatter valid, cross-skill links resolve, qmd-gate wording present, the `## Story:` boundary parses). The story methodology is adapted from the `writing-stories` skill in the sister repo at `/home/surehman/projects/personal/cid-knowledge/.claude/skills/writing-stories/`.

**Tech Stack:** Markdown skills (Claude Code plugin), Python 3.12 + pytest for the structural meta-tests.

## Global Constraints

- v1 is **Markdown drafts only**. "add to Jira" is recognized but replies "not implemented in v1". No Jira write code.
- **No eager writes.** Drafts live in conversation; persist only on explicit "save as MD".
- **qmd-first gate (verbatim rule):** always run the cheap `qmd status` check first; if qmd is present, USE qmd for discovery; fall back to `grep` ONLY when qmd is genuinely absent or `qmd status` errors. The status check is the cheap step — never grep to "save a step".
- **No new feature scripts** in v1 (skills are prompt-only). New code is limited to pytest meta-tests under `tests/`.
- **File layout:** flat `stories/` at the wiki repo root — one file per epic (epic + stories inline), one file per standalone story. Slug-based filenames (kebab-case, no date prefix).
- **Per-story conventions:** each story uses a `## Story: <title>` boundary and ends with a `## Grounding` footer (wiki pages + Jira keys). A/C never carries citations.
- **Default persona roster:** `user`, `admin`, `support engineer` (others inferred/asked). `wiki.config.yaml` `personas:` is the reserved seam for a configurable roster.
- **Skill discovery:** a skill is a directory `skills/<name>/SKILL.md` with frontmatter `name:` equal to the directory name; the slash command is that name. No `commands/` dir.
- **Branch:** all work on `wiki-story-authoring` (already created). Version bumps 0.7.3 → 0.8.0 mirrored in `plugin.json` and `.claude-plugin/marketplace.json`.

---

### Task 1: Structural meta-test suite (failing) + golden fixture

**Files:**
- Create: `tests/test_story_skills.py`
- Create: `tests/fixtures/sample-epic.md`

**Interfaces:**
- Produces: the test module `tests/test_story_skills.py` with functions `test_shared_references_exist`, `test_wiki_grounding_has_qmd_gate`, `test_personas_default_roster`, `test_wiki_story_skill_frontmatter`, `test_wiki_epic_skill_frontmatter`, `test_wiki_story_documents_story_boundary`, `test_wiki_epic_references_resolve`, `test_existing_skills_qmd_gate`, `test_sample_epic_boundaries_parse`. Later tasks make these pass.

- [ ] **Step 1: Write the golden fixture**

Create `tests/fixtures/sample-epic.md` — a minimal epic file proving the `## Story:` boundary convention parses:

```markdown
# Epic: Sample epic for boundary parsing

This fixture exists only to lock the machine-readable story boundary used by
the future "add to Jira" step. It is not product content.

## Story: First sample story

**Description:** As a user, I want a thing so that I get value.

## Grounding
- Wiki: [[sample-concept]]
- Jira: SAMPLE-1

## Story: Second sample story

**Description:** As an admin, I want another thing so that I manage it.

## Grounding
- Wiki: [[sample-rule]]
- Jira: SAMPLE-2
```

- [ ] **Step 2: Write the meta-test suite**

Create `tests/test_story_skills.py`:

```python
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SKILLS = ROOT / "skills"
REFS = SKILLS / "wiki-story" / "references"
SHARED_REF_FILES = [
    "story-format.md",
    "story-personas.md",
    "story-sizing.md",
    "story-examples.md",
    "wiki-grounding.md",
]


def _frontmatter_name(skill_md: Path) -> str:
    text = skill_md.read_text(encoding="utf-8")
    assert text.startswith("---"), f"{skill_md} missing frontmatter"
    fm = text.split("---", 2)[1]
    m = re.search(r"^name:\s*(.+)$", fm, re.MULTILINE)
    assert m, f"{skill_md} frontmatter missing name:"
    return m.group(1).strip()


def test_shared_references_exist():
    for fname in SHARED_REF_FILES:
        assert (REFS / fname).is_file(), f"missing shared reference {fname}"


def test_wiki_grounding_has_qmd_gate():
    text = (REFS / "wiki-grounding.md").read_text(encoding="utf-8")
    assert "qmd status" in text, "wiki-grounding.md must document the cheap `qmd status` gate"
    assert "grep" in text.lower(), "wiki-grounding.md must document the grep fallback"


def test_personas_default_roster():
    text = (REFS / "story-personas.md").read_text(encoding="utf-8").lower()
    for persona in ("user", "admin", "support engineer"):
        assert persona in text, f"default roster missing {persona!r}"


def test_wiki_story_skill_frontmatter():
    assert _frontmatter_name(SKILLS / "wiki-story" / "SKILL.md") == "wiki-story"


def test_wiki_epic_skill_frontmatter():
    assert _frontmatter_name(SKILLS / "wiki-epic" / "SKILL.md") == "wiki-epic"


def test_wiki_story_documents_story_boundary():
    text = (SKILLS / "wiki-story" / "SKILL.md").read_text(encoding="utf-8")
    assert "## Story:" in text, "wiki-story SKILL.md must document the `## Story:` boundary"
    assert "## Grounding" in text, "wiki-story SKILL.md must document the `## Grounding` footer"


def test_wiki_epic_references_resolve():
    base = SKILLS / "wiki-epic"
    text = (base / "SKILL.md").read_text(encoding="utf-8")
    rels = re.findall(r"\.\./wiki-story/references/[\w./-]+\.md", text)
    assert rels, "wiki-epic SKILL.md must reference the shared references dir"
    for rel in rels:
        target = (base / rel).resolve()
        assert target.is_file(), f"unresolved reference link: {rel}"


def test_existing_skills_qmd_gate():
    synth = (SKILLS / "wiki-ingest" / "synth-prompt.md").read_text(encoding="utf-8")
    assert "qmd status" in synth, "synth-prompt.md must use the cheap qmd status gate"
    assert "You may use `qmd query`/`qmd search`" not in synth, (
        "old soft 'You may use qmd' wording must be replaced"
    )
    lint = (SKILLS / "wiki-lint" / "SKILL.md").read_text(encoding="utf-8")
    assert "qmd status" in lint, "wiki-lint SKILL.md lookup must use the cheap qmd status gate"


STORY_BOUNDARY = re.compile(r"^## Story:\s+.+$", re.MULTILINE)


def test_sample_epic_boundaries_parse():
    sample = ROOT / "tests" / "fixtures" / "sample-epic.md"
    text = sample.read_text(encoding="utf-8")
    titles = STORY_BOUNDARY.findall(text)
    assert len(titles) >= 2, "sample epic must contain at least two `## Story:` boundaries"
```

- [ ] **Step 3: Run the suite to verify it fails**

Run: `pytest tests/test_story_skills.py -v`
Expected: `test_sample_epic_boundaries_parse` PASSES (fixture exists); the other 8 FAIL (files/wording not created yet).

- [ ] **Step 4: Commit**

```bash
git add tests/test_story_skills.py tests/fixtures/sample-epic.md
git commit -m "test(story-skills): structural meta-suite + golden epic fixture"
```

---

### Task 2: Shared reference set (the methodology brain)

**Files:**
- Create: `skills/wiki-story/references/story-format.md`
- Create: `skills/wiki-story/references/story-sizing.md`
- Create: `skills/wiki-story/references/story-examples.md`
- Create: `skills/wiki-story/references/story-personas.md`
- Create: `skills/wiki-story/references/wiki-grounding.md`
- Test: `tests/test_story_skills.py`

**Interfaces:**
- Produces: the five shared reference files loaded by both skills. `wiki-grounding.md` defines the qmd-first gate, the Grounding footer convention, and "ask, don't invent".

- [ ] **Step 1: Copy three reference files verbatim from the sister repo**

Source dir: `/home/surehman/projects/personal/cid-knowledge/.claude/skills/writing-stories/`

Copy verbatim (content is product-agnostic and needs no change):
- `story-format.md` → `skills/wiki-story/references/story-format.md`
- `story-sizing.md` → `skills/wiki-story/references/story-sizing.md`
- `story-examples.md` → `skills/wiki-story/references/story-examples.md`

```bash
SRC=/home/surehman/projects/personal/cid-knowledge/.claude/skills/writing-stories
mkdir -p skills/wiki-story/references
cp "$SRC/story-format.md"   skills/wiki-story/references/story-format.md
cp "$SRC/story-sizing.md"   skills/wiki-story/references/story-sizing.md
cp "$SRC/story-examples.md" skills/wiki-story/references/story-examples.md
```

- [ ] **Step 2: Create `story-personas.md` (adapted with the concrete default roster)**

Start from `$SRC/story-personas.md`, then make two changes: (a) replace the `{placeholder}` "Persona structure (typical)" table with the concrete default roster; (b) add the `wiki.config.yaml` seam note. Write `skills/wiki-story/references/story-personas.md`:

```markdown
# Story Personas

How to choose the persona for a story. These skills ship a small **default
roster**; a host wiki may override it (see "Configurable roster" below).

## Why personas matter

Every story's Description opens with "As a [persona], I want [capability] so
that [benefit]." The persona is the target user whose perspective the A/C is
written from. The wrong persona produces A/C that tests the wrong viewpoint.

## Default roster

| Persona | Use for |
|---------|---------|
| **user** | Day-to-day operational stories — running work, viewing status, routine actions. |
| **admin** | Configuration and management stories. The default for most stories. |
| **support engineer** | Troubleshooting, diagnostics, recovery, remote assistance. |

Other personas (platform/sysadmin, provisioning, account admin, SRE/infra)
appear only when a story is squarely in their area — infer them from the
objective and the wiki's `entities/`, and confirm with the user.

## Selection rules

- **Default to `admin`** — most stories benefit the administrator.
- **Use `user`** for daily-operation stories.
- **Use `support engineer`** for troubleshooting/recovery stories.
- **Use a rarely-used persona** only when the story is squarely in its area.
- **Never use "developer" as a target persona** — "As a developer, I want a
  migration" is a task, not a story (see Common Mistakes in story-format.md).
- **Ask if unclear** — if you cannot determine the persona from the objective
  and the wiki, ask the user.

## Configurable roster (seam)

If the host wiki defines a `personas:` list in `wiki.config.yaml`, use that
roster instead of the default above. (Not required in v1; the default roster
applies when the key is absent.)
```

- [ ] **Step 3: Create `wiki-grounding.md` (new)**

Write `skills/wiki-story/references/wiki-grounding.md`:

```markdown
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

​```
## Grounding
- Wiki: [[concept-slug]], [[rule-slug]]
- Jira: PROJ-123, PROJ-456
​```

List the wiki pages and Jira keys that informed the story. This is provenance —
keep it OUT of the A/C body (A/C stays clean per story-format.md).

## Not a wiki repo

If there is no `wiki.config.yaml` / `wiki/` in the current repo, stop: these
skills require a domain-expert wiki.
```

(Note: when writing the file, the Grounding footer code-fence above uses normal triple backticks; the zero-width markers are only to display the fence inside this plan.)

- [ ] **Step 4: Run the tests that this task satisfies**

Run: `pytest tests/test_story_skills.py::test_shared_references_exist tests/test_story_skills.py::test_wiki_grounding_has_qmd_gate tests/test_story_skills.py::test_personas_default_roster -v`
Expected: all three PASS.

- [ ] **Step 5: Commit**

```bash
git add skills/wiki-story/references/
git commit -m "feat(wiki-story): shared story methodology + wiki-grounding references"
```

---

### Task 3: `wiki-story` skill

**Files:**
- Create: `skills/wiki-story/SKILL.md`
- Test: `tests/test_story_skills.py`

**Interfaces:**
- Consumes: `skills/wiki-story/references/*.md` (Task 2).
- Produces: the `wiki-story` skill (slash command `/wiki-story`) — single-story authoring, draft-in-conversation, save-on-command.

- [ ] **Step 1: Create `skills/wiki-story/SKILL.md`**

```markdown
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
```

- [ ] **Step 2: Run the tests this task satisfies**

Run: `pytest tests/test_story_skills.py::test_wiki_story_skill_frontmatter tests/test_story_skills.py::test_wiki_story_documents_story_boundary -v`
Expected: both PASS.

- [ ] **Step 3: Commit**

```bash
git add skills/wiki-story/SKILL.md
git commit -m "feat(wiki-story): single-story authoring skill"
```

---

### Task 4: `wiki-epic` skill

**Files:**
- Create: `skills/wiki-epic/SKILL.md`
- Test: `tests/test_story_skills.py`

**Interfaces:**
- Consumes: `skills/wiki-story/references/*.md` (Task 2) by relative path `../wiki-story/references/`.
- Produces: the `wiki-epic` skill (slash command `/wiki-epic`) — breakdown → approve → auto-write stories into one epic file.

- [ ] **Step 1: Create `skills/wiki-epic/SKILL.md`**

```markdown
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
```

- [ ] **Step 2: Run the tests this task satisfies**

Run: `pytest tests/test_story_skills.py::test_wiki_epic_skill_frontmatter tests/test_story_skills.py::test_wiki_epic_references_resolve -v`
Expected: both PASS (the relative links resolve to the Task 2 files).

- [ ] **Step 3: Commit**

```bash
git add skills/wiki-epic/SKILL.md
git commit -m "feat(wiki-epic): epic breakdown + auto-write skill"
```

---

### Task 5: Tighten qmd-first in existing skills

**Files:**
- Modify: `skills/wiki-ingest/synth-prompt.md:11-14`
- Modify: `skills/wiki-lint/SKILL.md` (add a lookup gate after the index-refresh note)
- Test: `tests/test_story_skills.py`

**Interfaces:**
- Produces: hard qmd-first wording in both existing skills, matching the canonical rule in `references/wiki-grounding.md`.

- [ ] **Step 1: Replace the soft wording in `synth-prompt.md`**

Replace this exact block (lines 11–14):

```
   You may use `qmd query`/`qmd search` (project index over `raw` + `wiki`)
   to find pages an import touches or earlier claims it supersedes — hits are
   leads: open the file before asserting. `wiki/index.md` stays canonical for
   whether a page exists; if qmd is unavailable, fall back to grep/index.md.
```

with:

```
   For lead-finding, run the cheap `qmd status` gate first. If qmd is present
   (`.qmd/` exists, the binary runs, status is clean), USE `qmd query`/`qmd search`
   (project index over `raw` + `wiki`) to find pages an import touches or earlier
   claims it supersedes — hits are leads: open the file before asserting. Fall
   back to grep/index.md ONLY when qmd is genuinely absent or `qmd status` errors.
   `wiki/index.md` stays canonical for whether a page exists.
```

Leave the rename-sweep grep (lines 45–46) untouched — there grep over `wiki/` is the authoritative worklist and qmd hits are only leads; that is correct.

- [ ] **Step 2: Add a lookup gate to `wiki-lint/SKILL.md`**

Read `skills/wiki-lint/SKILL.md`. Immediately after the existing index-refresh sentence (the line ending "...never block the lint."), add this paragraph:

```
For related-page lookup during the semantic review, use the qmd-first gate: run
`qmd status`; if qmd is present, use `qmd search` over the `wiki` collection;
fall back to grep only when qmd is genuinely absent or `qmd status` errors.
```

- [ ] **Step 3: Run the test this task satisfies**

Run: `pytest tests/test_story_skills.py::test_existing_skills_qmd_gate -v`
Expected: PASS (`qmd status` present in both files; the old "You may use `qmd query`/`qmd search`" phrase gone from synth-prompt.md).

- [ ] **Step 4: Commit**

```bash
git add skills/wiki-ingest/synth-prompt.md skills/wiki-lint/SKILL.md
git commit -m "fix(wiki-ingest,wiki-lint): qmd-first lookup gate (don't default to grep)"
```

---

### Task 6: Docs, eval checklist, and version bump

**Files:**
- Modify: `README.md` (command table + repo-layout + an authoring section)
- Modify: `.claude-plugin/plugin.json` (version, description, keywords)
- Modify: `.claude-plugin/marketplace.json` (version)
- Create: `docs/eval/wiki-story-eval.md`
- Test: `tests/` (full suite)

**Interfaces:**
- Consumes: the finished skills from Tasks 2–5.
- Produces: user-facing docs, a manual eval checklist, and synced version metadata.

- [ ] **Step 1: Add the two commands to the README command table**

In `README.md`, add these rows to the `| Command | What it does… |` table (after the `/wiki-lint` rows):

```
| `/wiki-story <title or description>` | Writes ONE user story (A/C, D/N, Q/N) grounded in the wiki. Drafts in the conversation so you can iterate; saves Markdown to `stories/` only when you say "save as MD". Target an existing epic with "into epic `<slug>`". |
| `/wiki-epic <objective>` | Breaks a broad objective into an epic + child stories. Proposes a numbered breakdown, waits for your approval, then auto-writes the stories. Iterate in the conversation; "save as MD" writes a single `stories/<epic-slug>.md`. |
```

- [ ] **Step 2: Document the `stories/` layout in the README**

Add a short section after the "Command reference" section:

```markdown
## Authoring stories and epics

`/wiki-story` and `/wiki-epic` turn the wiki into authored work. They draft in
the conversation — nothing is written until you say **"save as MD"** — and save
to a flat `stories/` directory at the wiki repo root:

​```
stories/
  <epic-slug>.md                # an epic and its child stories, inline
  <standalone-story-slug>.md    # a standalone story
​```

Each story sits under a `## Story: <title>` boundary and ends with a `## Grounding`
footer listing the wiki pages and Jira keys that informed it. Writing back to
Jira is planned but not yet implemented; "add to Jira" reports that today.
```

(The code-fence above uses normal triple backticks; the zero-width markers are only to show the fence inside this plan.)

- [ ] **Step 3: Bump and extend `plugin.json`**

In `.claude-plugin/plugin.json`:
- Change `"version": "0.7.3"` → `"version": "0.8.0"`.
- Change the description's skill list from `Skills: wiki-init, wiki-queue, wiki-ingest, wiki-lint.` → `Skills: wiki-init, wiki-queue, wiki-ingest, wiki-lint, wiki-story, wiki-epic.`
- Change `"keywords": ["wiki", "jira", "ingest", "knowledge-base", "documentation"]` → `"keywords": ["wiki", "jira", "ingest", "knowledge-base", "documentation", "stories", "epics"]`.

- [ ] **Step 4: Sync `marketplace.json` version**

In `.claude-plugin/marketplace.json`, change the plugin entry `"version": "0.7.3"` → `"version": "0.8.0"`.

- [ ] **Step 5: Create the manual eval checklist**

Create `docs/eval/wiki-story-eval.md`:

```markdown
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
```

- [ ] **Step 6: Run the full test suite**

Run: `pytest -q`
Expected: all tests PASS (the 9 new `test_story_skills.py` tests plus the pre-existing suite).

- [ ] **Step 7: Commit**

```bash
git add README.md .claude-plugin/plugin.json .claude-plugin/marketplace.json docs/eval/wiki-story-eval.md
git commit -m "docs(wiki-story,wiki-epic): README, eval checklist, version 0.8.0"
```

---

## Self-Review

**Spec coverage:**
- Components & packaging (two skills + shared refs) → Tasks 2, 3, 4. ✓
- Wiki grounding + Grounding footer → Task 2 (`wiki-grounding.md`), used by Tasks 3, 4. ✓
- Personas (default roster + config seam) → Task 2 (`story-personas.md`), test in Task 1. ✓
- qmd-first rule (new + existing skills) → Tasks 2 (canonical) + 5 (existing). ✓
- Workflows (wiki-story single; wiki-epic breakdown→approve→auto-write) → Tasks 3, 4. ✓
- File layout & `## Story:` boundary → Tasks 3, 4; golden fixture + parse test in Task 1. ✓
- Error handling (not-a-wiki, ask-don't-invent, no-clobber, add-to-Jira seam) → Guardrails in Tasks 3, 4; eval in Task 6. ✓
- Testing strategy (structural meta-tests, golden output, manual eval) → Task 1 + Task 6 eval doc. ✓
- Non-goals (no Jira write, no config roster, no feature scripts) → honored throughout. ✓

**Placeholder scan:** No "TBD"/"TODO"/"handle edge cases" — all file content and commands are concrete. The only deferrals are the explicit v1 seams (Jira write, config roster), which are spec non-goals, not plan gaps.

**Type/name consistency:** Test function names in Task 1 match the files/wording produced in Tasks 2–5; reference filenames are identical across `SHARED_REF_FILES`, Task 2 creations, and the skill load-lists; `../wiki-story/references/` paths in Task 4 match the dir created in Task 2 (verified by `test_wiki_epic_references_resolve`); the `## Story:` / `## Grounding` strings are identical in the fixture, the regex, and both SKILL.md files.
```
