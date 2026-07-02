---
name: wiki-doc-author
description: Author or update a single customer-facing online help page grounded in the domain-expert wiki. Use when the user asks to author, write, or update an online doc or help page grounded in the wiki. Drafts in conversation; writes to disk only on explicit "save as MD" command.
---

# Wiki Doc Author

Author ONE customer-facing online help page, grounded in the wiki, written to
the bundled style guide — direct, accurate, no internal jargon.

## Guardrails

- **Not a wiki repo** (no `wiki.config.yaml` / `wiki/`) → **stop** with:

  > This skill requires a domain-expert wiki repo (`wiki.config.yaml` + `wiki/`
  > directory). No wiki found here — run `/wiki-init` first.

- **Ask, don't invent** — if the topic references something not in the wiki,
  ASK the user. Never fabricate product facts.
- **Never silently clobber** — if the target file already exists, confirm
  overwrite or append before writing.
- **No internal identifiers** — this is customer-facing output. Apply
  `R-VOICE-09`: strip internal identifiers using the `identifier_patterns`
  override (from the Documentation Domain Context) and the Jira project key
  (`project.key` in `wiki.config.yaml`).

---

## Workflow

### 1. Resolve target

Determine whether the user wants a **new** page or an **update** to an
**existing** page.

**New page:**

```bash
python "${CLAUDE_PLUGIN_ROOT}/scripts/doc_target.py" "<title>"
```

This uses the first `docs:` location from `wiki.config.yaml` and computes a
kebab-case slug to propose the output path. Echo the proposed path to the user;
do not create or modify any file yet.

**Existing page:**

Accept the path the user names. Verify it exists and that it lives under a
`docs:` location. Do not modify it yet.

**No `docs:` location configured:**

If `wiki.config.yaml` has no `docs:` block, explain that it is needed only at
save time, and show the user how to add it:

```yaml
docs:
  location: <path-to-online-help-root>
```

Do not invent a folder. After the user adds the block, proceed.

---

### 2. Ground (qmd-first gate)

Retrieve the relevant wiki pages that cover the same topic area — the factual
basis for the draft. Follow the canonical gate in
`${CLAUDE_PLUGIN_ROOT}/prompts/qmd-first-gate.md` (`qmd status` first; search
two or three key nouns from the page title or the user's description over the
`wiki` collection; grep only when qmd is genuinely absent).

If the topic references something not in the wiki, **ASK — do not invent.**

---

### 3. Pick the Diátaxis topic type

Before drafting, identify the `R-TOPIC` type:

| Type | Use when |
|---|---|
| **Tutorial** | Learning-oriented; guides a reader through a task to build understanding |
| **How-to** | Task-oriented; solves a specific real-world problem step by step |
| **Reference** | Information-oriented; describes a thing (API, config, parameter) |
| **Explanation** | Understanding-oriented; discusses concepts, trade-offs, background |
| **Troubleshooting** | Recognized hybrid: problem + symptom + cause + solution |

State the chosen type to the user before drafting. If the page could fit more
than one type, ASK which lens to use.

---

### 4. Draft in conversation

Draft the page in conversation — do NOT write any file yet.

Write to the bundled style guide at `${CLAUDE_PLUGIN_ROOT}/style-guide/`
(start at its README, then apply the relevant rule files):

- **Voice and grammar** — `style-rules.md` (`R-VOICE`, `R-GRAM`)
- **Structure and topic shape** — `style-rules.md` (`R-STRUCT`, `R-TOPIC`)
- **Procedures** — `style-rules.md` (`R-PROC`)
- **Formatting, code, links** — `style-rules.md` (`R-FMT`, `R-CODE`, `R-LINK`)
- **Admonitions and lists** — `style-rules.md` (`R-ADMON`, `R-LIST`)
- **Accessibility and alt text** — `style-rules.md` (`R-A11Y`, `R-ALT`)
- **Release notes** (if applicable) — `release-notes.md` (`R-RELNOTES`)
- **Troubleshooting pages** (if applicable) — `troubleshooting.md` (`R-TROUBLE`)
- **Platform mechanics** (admonition syntax, front-matter, code fences) —
  `platforms/<profile>.md`

**Override buckets** — apply the **Documentation Domain Context** block from the
wiki's `CLAUDE.md` §0 (or `AGENTS.md`): it defines all four buckets (`platform`,
`vendor_name`/`forbidden_role_names`, `identifier_patterns`, project term table)
and the industry-standard defaults that apply when it is absent or commented out.
`wiki.config.yaml` carries only the `docs:` location, never overrides.

---

### 5. Iterate

Continue refining the draft across turns. The user may change scope, type,
or tone. Write NOTHING to disk until the user gives the explicit save command.

---

### 6. Persist only on "save as MD"

When the user says **"save as MD"** (or an equivalent explicit command):

1. **Pre-save gate** — read and apply each item in `${CLAUDE_PLUGIN_ROOT}/style-guide/review-checklist.md`
   to the draft (it is a checklist, not a script). Flag any failures. Ask whether to proceed or fix first.

2. **Internal-identifier sweep** — apply `R-VOICE-09`: strip internal
   identifiers using the `identifier_patterns` override (from the Documentation
   Domain Context) and the Jira project key (`project.key` in `wiki.config.yaml`).

3. **Sources footer** — end the page with a `## Sources` footer listing the wiki
   pages used as grounding, so reviewers can trace accuracy claims.

4. **Write the file** at the resolved target path from step 1 (new page: the
   `doc_target.py` proposal; existing page: the path the user named).
   - If the target file already exists: confirm **overwrite** or **append**
     before writing. Never silently clobber.

5. **Commit** — if the docs location is inside a git repository, commit the
   new or updated file.
