# Review checklist — anti-patterns

Scan for these when reviewing existing content or before publishing new content.
Each row maps to the rule that governs it; cite the `R-…` ID when flagging. Open
[style-rules.md](style-rules.md), [release-notes.md](release-notes.md), or
[troubleshooting.md](troubleshooting.md) for the full rule text.
Preferred spelling, casing, and synonyms for generic tech-writing conventions are
in [terminology-conventions.md](terminology-conventions.md); product/feature
terminology comes from the wiki's `terminology/` pages and the optional project
term-table override in the Documentation Domain Context (CLAUDE.md / AGENTS.md).

| Anti-pattern | Use instead | Rule |
|---|---|---|
| ALL CAPS admonition labels (NOTE, CAUTION, WARNING) | Sentence case (Note, Caution, Warning) | R-ADMON-01 |
| Bold for inline commands, file paths, or file names | Monospace | R-CODE-01..06, R-FMT-01 |
| Bolded period in a term-list lead-in (`**Term.**`) | Period in plain text (`**Term**.`) | R-LIST-10 |
| Italic label on a bulleted term list | Bold label, plain-text period | R-LIST-10 |
| Single-attribute items in a table, or multi-attribute look-up data as a bulleted list | Match the format to attribute count: list / description list vs table | R-LIST-11 |
| Single-column table, or a table inside a numbered procedure | Turn a single column into a list; keep tables out of step flow | R-LIST-11 |
| Same enumeration or attribute table duplicated verbatim across a how-to and a reference/explanation page | Define it once with its primary reader; cross-reference from the other topic | R-LIST-12, R-TOPIC-03, R-STRUCT-06 |
| Em-dashes used liberally (more than one per page) | Commas → parens → colon → new sentence | R-GRAM-09 |
| Two hyphens (`--`) as em-dash | The em-dash character `—` | R-GRAM-11 |
| En-dash or hyphen as a body-text aside | Em-dash for asides; en-dash for ranges; hyphen for compounds | R-GRAM-09, R-GRAM-10, R-GRAM-11 |
| Title Case at headings | Sentence case; proper nouns and product names capitalized | R-STRUCT-02 |
| "Refer to" / "Please refer to" as cross-reference verbs | "see" | R-LINK-01 |
| Double quotes around status values ("Passed", "Failed") | Bold for UI-visible status; italics for terms being introduced | R-FMT-01 |
| Underlining for emphasis | Bold, italic, or rewrite | R-FMT-03 |
| ALL CAPS for emphasis in body text | Bold or italic | R-FMT-04 |
| "Click here" or "this link" as link text | Destination name or descriptive phrase | R-LINK-03 |
| `→` or `§` joining page and section in cross-reference link text | "the [Section heading](...) section of Page" | R-LINK-09 |
| "See the section above/below" for a same-page link | Link the section heading by `#anchor`; "earlier/later on this page" if order matters | R-LINK-10 |
| Stacked admonitions (two in a row) | Merge into one or rewrite as inline | R-ADMON-03 |
| Invented admonition types (Info, Heads up, Pro tip) | One of the platform's supported set (for example: Note, Tip, Important, Caution, Warning) | R-ADMON-05 |
| Mixing Diátaxis types in one topic | Split into separate topics linked across types (troubleshooting topics are the documented exception) | R-TOPIC-01, R-TOPIC-03 |
| Troubleshooting page with no triage block | Add a *Confirm this is the right document* section after Symptom | R-TROUBLE-02 |
| Troubleshooting diagnostic step with no result table | Append a `\| Result \| Next step \|` table that routes onward | R-TROUBLE-06 |
| An internal role name (for example, a service-account username) in a troubleshooting page | The customer-facing canonical term from the wiki's `terminology/` | R-TROUBLE-12 |
| Internal KB rule IDs or ticket codes in customer-facing prose | Cite the customer-facing concept instead | R-VOICE-09 |
| "(Tutorial)" / "(Reference)" tags in titles | Topic shape conveys the type | R-TOPIC-02 |
| Forward references in tutorials ("we'll cover this later") | Teach what's needed; cross-reference references after, not mid-flow | R-TOPIC-04 |
| Numbered steps inside an explanation | Move steps to a how-to and link | R-TOPIC-07 |
| Marketing language in release notes | Past-tense verb describing what the release did | R-RELNOTES-19 |
| Invented release-notes section names ("Enhancements", "Defects fixed") | Added / Changed / Deprecated / Removed / Fixed / Security | R-RELNOTES-07 |
| Major.minor versioning (`1.3`) | Full semver (`1.3.0`) | R-RELNOTES-01 |
| Day-precision or numeric dates in release headings | Keep a Changelog format: `## [1.3.0] - 2026-04-15` | R-RELNOTES-05 |
| Defect entries starting with ticket number | Past-tense sentence; ticket in parens at end: `Fixed <thing>. (#1234)` | R-RELNOTES-08, R-RELNOTES-09 |
| "Known issues" inside a Keep-a-Changelog release | Separate Known Issues page; link from the release header | R-RELNOTES-07 |
| Editing the meaning of published release entries | Add a correction note in the next release | R-RELNOTES-22 |
| Deprecation without removal release and migration path | `Deprecated <feature>. <Migration sentence>. Removal planned for <version>.` | R-RELNOTES-12 |
| Breaking changes without a migration path | One-sentence migration in the same entry, or a link | R-RELNOTES-17 |
| Burying action-required guidance inside a bullet | Top-of-release Action required callout | R-RELNOTES-15 |
| Contributor names or commit hashes in release notes | Issue numbers only | R-RELNOTES-20 |
| Per-doc "What's New" / "Changelog" chapters | Single release-notes page | R-RELNOTES-21 |
| Screenshots at 4K or high-DPI scaling (e.g., 200%) | Sufficient resolution; don't upscale a small capture. | R-SHOT-07 |
| Blur as redaction | Flat gray rectangle | R-SHOT-04 |
| Screenshots from production with real customer data | Documentation-only test fixture | R-SHOT-05 |
| Multiple annotation colors in one screenshot | Consistent annotation style; don't rely on color alone; numbered callouts for sequence. | R-SHOT-09 |
| JPEG for UI screenshots | PNG for UI; SVG for diagrams | R-SHOT-08 |
| Screenshots of generic OS dialogs or browser chrome | Crop to the relevant region; reserve for product UI and visually distinctive moments | R-SHOT-03 |
| Alt text starting with "Image of" or "Screenshot of" | Lead with the information conveyed | R-ALT-04 |
| Filename as alt text | Describe what the image shows | R-ALT-02 |
| Omitted alt on decorative images | Empty `alt=""` | R-ALT-03 |
| Long alt text (over 155 chars) | Short alt + `<figcaption>` or paragraph for detail | R-ALT-05 |
| Bold text on its own line faking a heading | Use the heading element at the correct level | R-A11Y-07 |
| Skipping heading levels (H2 → H4) | Sequential levels | R-A11Y-07 |
| Color as sole indicator of status | Icon + word + color | R-A11Y-03 |
| Directional language ("the dialog on the left") | UI-label reference ("the **Source** pane") | R-A11Y-05 |
| Using an internal role name in customer-facing text | The vendor name or the product's canonical user-facing term (see the wiki's `terminology/`) | R-VOICE-05 |
| Referring to the reader as "the customer" | "you" / "your"; a role name for other people; "customer" only as a side-of-boundary qualifier | R-VOICE-10 |
| Hand-numbering steps in source (`**1**  Open…`) | Plain `1. Open…`; let the renderer style numbering | R-PROC-01 |
