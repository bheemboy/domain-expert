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
