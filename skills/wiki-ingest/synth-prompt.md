# SYNTH PROMPT (Sonnet synth subagent)

You synthesize a **batch of sources** into the wiki, in the order
given (oldest → newest). Each source is either an **import** (`raw/imports/jira/<KEY>.md`,
for Jira; `raw/imports/<hash8>/<name>.md` for binary docs) or a **raw file read directly**
(code and prose) — step 2's `classify` call tells you which file to read and which
confidence tag to use. Work from the wiki schema. Do not touch any manifest.

1. Read `CLAUDE.md` §3 (layout), §4 (provenance/recency/superseding), §6
   (index/log), and `wiki/index.md` (existing pages) so you update, not duplicate.
   For lead-finding, run the cheap `qmd status` gate first. If qmd is present
   (`.qmd/` exists, the binary runs, status is clean), USE `qmd query`/`qmd search`
   (project index over `raw` + `wiki`) to find pages an import touches or earlier
   claims it supersedes — hits are leads: open the file before asserting. Fall
   back to grep/index.md ONLY when qmd is genuinely absent or `qmd status` errors.
   `wiki/index.md` stays canonical for whether a page exists.
2. For each path **in order**, run `python "${CLAUDE_PLUGIN_ROOT}/scripts/ingest_state.py" classify <path>`
   → `<kind>\t<read_target>`. Run `python "${CLAUDE_PLUGIN_ROOT}/scripts/queues.py" read-note <path>`;
   if it prints a non-empty triage note, treat it as a **focus hint** for where the business
   value sits — but ALWAYS read `<read_target>` in full regardless; the note never replaces the
   read — then read `<read_target>` and tag/cite by kind:
   - `jira`  → read the import; tag `(ticket-only)`; cite `[<KEY>, YYYY-MM]`.
   - `doc`   → read the import (converted PDF/Office text); tag `(doc-stated)`; cite `[doc: <source>]` (its `source:` path).
   - `prose` → read the file **directly** (`.md`/`.txt`); tag `(doc-stated)`; cite `[doc: <repo-relative path>]`.
   - `code`  → read the file **directly** (source code); tag `(code-confirmed)`; cite `[code: <repo-relative path>]`.
   Only imports carry `business_relevant:` — skip a `jira`/`doc` import marked
   `business_relevant: false` (record nothing, report it complete). For `prose`/`code`,
   judge business-relevance from the content (§2) and record nothing if there is none.
   For the rest, **create or update** the relevant `wiki/` page(s):
   - Apply provenance + recency (§4): carry each claim's citation + confidence tag
     (above). Override precedence is by tag — `(code-confirmed)` > `(doc-stated)` >
     `(ticket-only)` — plus §4.4 (code wins over any ticket regardless of date). When a
     `code` source confirms/corrects an existing claim, upgrade it to `(code-confirmed)`
     and move the old statement to `## Superseded` (`→ corrected by code`). Where a newer
     source changes a behaviour, move the old statement to `## Superseded` and make the
     new one current.
   - **Rename/replacement sweep (mandatory, closed loop).** A rename is a graph
     operation, not a local edit: if an import renames, replaces, or retires a term
     (product noun, role, privilege, project, instrument, report, storage path,
     endpoint, test, or workflow), updating the page it is "about" is NOT enough —
     it touches every page that names the old term. After updating the owning page,
     `grep -rin "<old term>" wiki/` and reconcile EVERY hit: rewrite to the new
     term, scope the line to its era (e.g. prefix `(v1.0)` or keep its
     `[KEY, YYYY-MM]` cite), or move it to `## Superseded` with the
     `[OLD → replaced by NEW]` annotation. **Always include the [[glossary]] row,
     the [[index]] one-line summary, and any name-history list.** The sweep is done
     only when grep shows no *unscoped current* use of the old term. (qmd hits are
     leads; grep over `wiki/` is the authoritative worklist here.)
   - A single import may touch several pages (often 3–10). Add `[[wikilinks]]`.
   - **References** — for a `jira`/`doc` source, add ONE entry linking its import
     `[<KEY> — <title>](../../raw/imports/jira/<KEY>.md)` (from `wiki/overview.md`, `../raw/imports/jira/<KEY>.md`);
     never link the raw `jira-exports/...` file or the live ticket (the import records the
     ticket URL in `source_url:`). A `prose`/`code` source has **no import** — its inline
     `[doc: …]` / `[code: …]` citation is the provenance; do not fabricate an import link.
3. Update `wiki/index.md` (new pages / changed summaries) and append ONE `synth`
   line per source to `wiki/log.md` in the standard format (§6).
4. Return EXACTLY ONE line:
   - `SYNTHED | completed: <id> <id> … | pages: <slugs>` — list every source you fully
     finished, by the id it has in the manifest (a Jira KEY, or a file path for doc/raw
     lines), so the orchestrator can mark them done,
   - `NEEDS-INPUT | <one specific question>` — only for a genuine ambiguity needing
     the human (e.g. two imports conflict with the SAME date). Resolve normal
     recency conflicts yourself.
   - `FAILED | <reason>` — could not complete; list any KEYs you did finish.
