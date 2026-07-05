# QMD-FIRST GATE (canonical)

The one place this gate is spelled out — skills and references link here instead
of restating it. Discovery over the wiki MUST prefer `qmd` whenever present.
Do NOT default to grep.

1. **Cheap presence gate — ALWAYS run it first:** `qmd status`.
   Pass = `.qmd/` exists, the `qmd` binary runs, and status returns cleanly.
2. **If qmd is present → USE it:** `qmd search "<key nouns>"` (or `qmd query`)
   over the `wiki` collection. Hits are leads — open each page before relying
   on it.
3. **Fall back to `grep` ONLY when qmd is genuinely absent** (no `.qmd/`, binary
   missing, or `qmd status` errors). Note `qmd-unavailable`.

The `qmd status` check IS the cheap step — never skip straight to `grep -ri`
while `.qmd/` is present.

4. **Unified server index (only when `$WIKI_INDEX_ROOT` is set):** the index
   is the shared one at `$WIKI_INDEX_ROOT/.qmd` — run qmd from that
   directory — and collections are namespaced per product:
   `cd "$WIKI_INDEX_ROOT" && qmd search -c <prefix>__wiki "<key nouns>"`
   (likewise `<prefix>__raw`), where `<prefix>` is the wiki's configured
   `defect_review.qmd_collection_prefix` (the app-registry key, e.g. `cid` —
   NOT the Jira project key). That index is shared with a running app:
   treat it as READ-ONLY — never `qmd update`, `qmd embed`, or
   `qmd collection add` against it; its maintenance belongs to the content
   service's sync. If `$WIKI_INDEX_ROOT` is set but the prefix is not
   configured, fall back to steps 1–3 in the repo itself.
