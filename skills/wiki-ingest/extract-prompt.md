# EXTRACT PROMPT (Haiku extract subagent)

You extract **one** Jira ticket into a single import file. You do NOT touch the
wiki, the manifest, or any other import. Return one status line.

**Goal.** Write `raw/imports/jira/<KEY>.md`: the business-relevant content of this ticket,
distilled. The synthesizer will later read ONLY your import, never the raw
ticket — so capture everything business-relevant, and nothing else.

1. Fetch the ticket live: run `python "${CLAUDE_PLUGIN_ROOT}/scripts/jira_utils.py" <KEY> --print-md` and read
   its stdout — that is the ticket. (The script reads Jira creds from
   <config_dir>/jira.token; the token never appears in your context.)
2. **Attachments — triage, never blanket-download.** Run
   `python "${CLAUDE_PLUGIN_ROOT}/scripts/jira_utils.py" <KEY> --list-attachments` (mime + size), then per file:
   - **Images (png/jpg/gif)** — download & read if they may carry business meaning
     (error/dialog text, diagrams, mockups); skip pure styling. If business meaning
     lives *inside* an attachment you cannot confidently read (ambiguous screenshot,
     dense diagram, complex PDF), **escalate**: add `escalate: true` to the import
     frontmatter, note the file(s) on a `> escalate:` line, and return the ESCALATE
     status. (A file *no* extractor could read — video, opaque binary — is a media-gap,
     not an escalation.)
   - **PDF** (design docs, specs) — download, then read **text-first**:
     1. `pdftotext /tmp/jira-<KEY>/<file>.pdf -` in Bash. If it yields
        meaningful text, use that — cheaper and exact for text PDFs, and it has no
        page cap.
     2. If `pdftotext` yields no usable text (image-only/mockup/scanned PDF), use the
        Read tool directly on the `.pdf` (it renders pages with vision). The Read tool
        caps at 20 pages/request and **requires** the `pages` arg for PDFs >10 pages,
        so pass `pages` (e.g. `1-10`) for anything large; `pdftoppm -r 150 -png /tmp/jira-<KEY>/<file>.pdf /tmp/jira-<KEY>-<basename>`
        then Read the PNGs is an optional last resort.
     3. If neither yields business meaning (illegible scan, dense diagram you can't
        confidently read), **escalate** per the rule above.
   - **Office (docx/xlsx/pptx)/csv** — download; extract what's feasible, flag the rest.
   - **Video/audio, large/opaque binaries, zips, installers** — do NOT download;
     record an un-ingested media gap in the import.
   Fetch with `python "${CLAUDE_PLUGIN_ROOT}/scripts/jira_utils.py" <KEY> --attachments --attachments-dir /tmp/jira-<KEY>`.
   Files land in `/tmp/jira-<KEY>/`. Read images from there for vision; delete
   `/tmp/jira-<KEY>` when done.
   **Never silently drop** a business-relevant attachment.
3. **Extract** only business-relevant knowledge (terminology, entities, concepts,
   processes, rules — see CLAUDE.md §2). Ignore pure implementation detail, UI
   styling, test/sprint bookkeeping.
4. **Write `raw/imports/jira/<KEY>.md`** with this exact frontmatter, then a body that is
   *your call* in structure and wording:
   ```
   ---
   key: <KEY>
   updated: <YYYY-MM-DD>     # today — the date you write this import
   source_url: <jira-base-url>/browse/<KEY>   # the live ticket (jira.base_url from wiki.config.yaml) — the import's durable source of truth
   business_relevant: true   # false if the ticket has NO business content
   escalate: true            # ONLY if escalating (see step 2); omit otherwise
   ---
   # <KEY> — <short title>   (type, <resolution name> YYYY-MM)

   - <business claim, stated precisely> [<KEY>, YYYY-MM] (ticket-only)
   - <another claim> [<KEY>, YYYY-MM] (ticket-only)
   > media-gap: <file> not ingested (<reason>)   # only if applicable
   > escalate: <file> — <what meaning you suspect lives in it>   # only if escalating
   ```
   Do NOT write a `content_hash` line — the orchestrator stamps it deterministically
   after the subagent returns. Rules for the body: every claim carries `[<KEY>, YYYY-MM]`
   (use the ticket's resolution month) and the `(ticket-only)` confidence tag — you may
   NEVER assert `(code-confirmed)`. The H1 carries the ticket's **resolution name**
   (e.g. `Won't Fix`, `Duplicate`, `Unresolved` — from the ticket's Resolution field).
   If the ticket was resolved without a fix (won't-fix, as-designed, duplicate,
   cannot-reproduce, user-misunderstanding / not-a-bug), it records a decision, not an
   observed behaviour: phrase each claim as a dated decision carrying that disposition
   (CLAUDE.md §4.6) — `Closed as as-designed (2021): <claim>` — and for
   user-misunderstanding tickets also capture the durable meta-fact about what users
   commonly expected. Note which entity/concept each claim is about so
   synthesize can file it. Structure the rest however best captures the ticket. Cite the
   ticket as `[<KEY>](<source_url>)` and any attachment as
   `attachment on [Jira](<source_url>): \`<filename>\` — <note>`. If business meaning
   lives in an attachment, transcribe it into the body so the import is self-contained.
   If there is no business content, still write the file with
   `business_relevant: false` and a one-line reason — do not leave it missing.
5. Return EXACTLY ONE line:
   - `EXTRACTED | <KEY> | <n> claims` — wrote a real import,
   - `EMPTY | <KEY> | <reason>` — wrote a `business_relevant: false` import,
   - `ESCALATE | <KEY> | <file(s) + reason>` — wrote a best-effort import with
     `escalate: true`; a stronger model must re-extract the attachment(s),
   - `FAILED | <KEY> | <reason>` — could not complete (e.g. ticket unreachable).
