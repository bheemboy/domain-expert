# ESCALATION PREAMBLE (prepend to the extract prompt for a Sonnet re-extract)

**Escalated re-extract.** A cheaper extract of this ticket flagged that business
meaning lives in attachment(s) it could not confidently read — see the `> escalate:`
line(s) in the existing `raw/imports/jira/<KEY>.md`. You are the stronger escalation extractor:
re-do the extract from scratch, paying particular attention to downloading and reading
the flagged attachment(s). **Overwrite** `raw/imports/jira/<KEY>.md` completely and do NOT
include `escalate: true` — you are the final extract. If a flagged file is still
genuinely unreadable, record it as a `> media-gap:` instead and finish with `EXTRACTED`
(or `EMPTY`); never return `ESCALATE`.
