# Style rules (generic)

This is the bundled generic style guide. Rules carry stable `R-…-NN` identifiers;
gaps in a sequence mean a rule was dropped by the disposition — do not renumber
survivors. Cite rule IDs in review comments and lint output.

**What this file does not contain:** vendor identity, product names, brand colors,
platform-specific mechanics, or identifier-sweep patterns. Those four concerns are
supplied by override buckets described in `style-guide/README.md` (the vendor,
terminology, platform, and identifier-sweep overrides) and by the wiki's
`terminology/` folder. Voice default across all content: second-person "you" with
imperative mood. The only first-person idiom permitted in customer-facing prose is
"we recommend".

---

## 1. Voice and tone (R-VOICE)

- **R-VOICE-01:** Address the reader in second person (*you*, *your*).
  - **Do:** "After purchase, you receive a confirmation email."
  - **Don't:** "After purchase, the user receives a confirmation email."

- **R-VOICE-02:** Use imperative mood for procedure steps.
  - **Do:** "Right-click the installer and run it as administrator."
  - **Don't:** "The user should right-click the installer file."

- **R-VOICE-03:** Use present tense. Reserve future tense for events that genuinely occur later.

- **R-VOICE-04:** Prefer active voice. Passive is acceptable when the actor is the system or genuinely unimportant.
  - **Do (active):** "Click **Activate** to start activation."
  - **Acceptable (passive, system actor):** "A request file is saved to the default **Downloads** folder."

- **R-VOICE-05:** Speak as the vendor. In customer-facing prose, name the vendor rather than using "we" — the vendor name comes from the Documentation Domain Context (see `style-guide/README.md`). The only permitted first-person idiom is "we recommend". Never refer to an internal role or system name in published text; use the customer-facing concept instead. (Vendor name, internal role names, and role-to-concept mappings are override values, not generic defaults.)

- **R-VOICE-06:** Contractions are appropriate for a friendly, approachable tone and are encouraged in most technical content (following MS/Google defaults). Avoid contractions in admonitions, formal notices, and legal or compliance text where precision matters.

- **R-VOICE-07:** Plain, technical, neutral tone. No exclamation marks, no rhetorical questions, no casual register.

- **R-VOICE-08:** Reserve hedging (*may*, *might*, *can*) for genuine uncertainty, not politeness.
  - **Do:** "This may require a system reboot."
  - **Don't:** "You might want to maybe consider rebooting."

- **R-VOICE-09:** Keep internal source-side identifiers out of published prose. Internal rule IDs and ticket-system codes belong in commits, reviews, and KB references, not in customer-facing text — cite the customer-facing concept instead. The identifier patterns to sweep before publishing are defined in the Documentation Domain Context (identifier-sweep override), not here.

- **R-VOICE-10:** Don't refer to the reader as "the customer". In customer-facing prose the reader is addressed in second person (R-VOICE-01); naming them "the customer" is a vendor-centric, third-person framing of the very person reading the page. Resolve by context:
  - **Reader as a person** → *you* / *your*. **Do:** "After purchase, you receive a confirmation email." **Don't:** "The customer receives a confirmation email."
  - **Reader's organization** → *your organization*, *your team*, *your site*. **Don't:** "the customer's team".
  - **A person in a role** → the role name (R-INCL-04): *the administrator*, *the analyst*, *lab users*. **Don't:** "the customer admin".
  - **The customer's side of a boundary** (where there is genuinely no reader to address) → "customer" is acceptable as a qualifier: *customer network*, *customer data*. Prefer a concrete canonical term where one exists (see the wiki's `terminology/`).

---

## 2. Grammar and mechanics (R-GRAM)

- **R-GRAM-01:** Use the Oxford (serial) comma.

- **R-GRAM-02:** One space after sentence-ending punctuation.

- **R-GRAM-03:** Spell out abbreviations on first use with the abbreviation in parens. After first use, short form alone.
  - **Do:** "Graphical User Interface (GUI)" → later, "GUI"

- **R-GRAM-04:** Common well-known abbreviations may be used unexpanded: *PC*, *URL*, *USB*, *LAN*, *PDF*, *HTTP*, *TCP*, *DNS*, *RAM*, *CPU*, *MAC* (address), *FAQ*. The allow-list of product-specific or domain-specific abbreviations is defined in the wiki's `terminology/` and the terminology override.

- **R-GRAM-05:** Use *and/or* sparingly; rewrite for clarity.

- **R-GRAM-06:** Short sentences, one idea per sentence. Long sentences are harder to read and expand significantly in translation — keep them concise.

- **R-GRAM-07:** Prefer plain English over Latin abbreviations: "for example" over *e.g.*, "that is" over *i.e.*, "and so on" over *etc.*

- **R-GRAM-08:** Capitalize product, feature, and named-subsystem names. The authoritative capitalization for each term is in the wiki's `terminology/` and the terminology override.

- **R-GRAM-09:** Avoid em-dashes (`—`). Prefer in order: commas, parentheses, colon, new sentence. Use them sparingly, preferring commas, parentheses, or separate sentences. When used, no spaces around it: `captured at startup—is logged`. Never two hyphens (`--`).

- **R-GRAM-10:** Use en-dashes (`–`) for ranges and compound modifiers only: `1–6 instruments`, `pages 23–25`, `2022–2026`. Never as a body-text break.

- **R-GRAM-11:** Use hyphens (`-`) for compound words only: `non-default`, `21-character limit`. Never for ranges or asides.

---

## 3. Page structure (R-STRUCT)

- **R-STRUCT-01:** Every page opens with one orienting paragraph stating what the page covers and who it's for. No hand-coded mini-TOC; let the publishing framework render navigation.

- **R-STRUCT-02:** Use sentence case at all heading levels.
  - **Do:** "Prepare your environment", "Run a sequence", "Configure authentication"
  - **Don't:** "Prepare Your Environment", "Run A Sequence", "CONFIGURE AUTHENTICATION"

  Proper nouns and product names stay capitalized.

- **R-STRUCT-03:** Heading hierarchy: H1 = page title (one per page); H2 = section; H3 = subsection; H4 = inline run-in heading (bold). Don't skip levels.

- **R-STRUCT-04:** Title shape matches topic type (see §4):
  - **Tutorial:** "Getting started with …" / "Your first …"
  - **How-to:** "Run a sequence" / "Restore from backup" (imperative or task-keyed noun phrase)
  - **Reference:** "Supported formats" / "Error codes" / "API reference" (noun phrase, no verb)
  - **Explanation:** "About failover" / "How activation works"

- **R-STRUCT-05:** Open each H2 with 1–3 sentences of orienting prose before any list, table, or procedure. Don't jump straight into a numbered list under a heading.

- **R-STRUCT-06:** Provide cross-references rather than duplicating content (R-LINK).

---

## 4. Topic types — Diátaxis (R-TOPIC)

Every topic is one type. Pick the dominant one and write to it.

| Type | Reader is | Form | Voice |
|---|---|---|---|
| **Tutorial** | Learning by doing | Guided lesson with one complete outcome | Hand-holding; "we"/"you" |
| **How-to** | Solving a specific task | Short goal-oriented procedure | Imperative; no teaching |
| **Reference** | Looking something up | Structured facts (tables, lists) | Neutral, declarative |
| **Explanation** | Understanding why | Discussion of concepts, design, trade-offs | Reflective |

- **R-TOPIC-01:** One Diátaxis type per topic. Don't mix tutorial narration into a reference page or explanation into a how-to.
  - **Do (how-to):** "1. Open the activity log. 2. Filter by user. 3. Export to CSV."
  - **Don't (mixed):** "1. Open the activity log. The activity log is a write-once log signed by a key management service… 2. Filter by user."

- **R-TOPIC-02:** Don't label topics with `(Tutorial)` or `(Reference)` tags in the title. The shape conveys the type.

- **R-TOPIC-03:** Link across types instead of duplicating. How-to references reference; explanation links to how-to.

- **R-TOPIC-04:** Tutorial-specific:
  - One outcome per tutorial.
  - No forward references ("we'll cover this in the admin guide").
  - Show the result of each major step.
  - List prerequisites up front.

- **R-TOPIC-05:** How-to-specific:
  - Title names the task; first sentence states the outcome.
  - Numbered steps only; no explanation paragraphs between steps unless a result must be confirmed.
  - State prerequisites up front.
  - Keep the procedure focused and as short as the task allows.

- **R-TOPIC-06:** Reference-specific:
  - Tables, lists, and definition lists dominate. One intro paragraph per page or per H2.
  - Alphabetical within a category unless severity/lifecycle order is more useful.
  - Every entry has the same shape (same columns, same fields).
  - Don't address the reader in second person; state facts.

- **R-TOPIC-07:** Explanation-specific:
  - Lead with the concept, not a task. "Failover protects against server hardware loss," not "To enable failover, …".
  - State trade-offs and alternatives.
  - No numbered steps. Steps belong in a how-to.

---

## 5. Procedures (R-PROC)

- **R-PROC-01:** Use numbered steps for procedures. Author plain `1.` / `2.` / `3.`; let the publishing system render numbering.

- **R-PROC-02:** One action per step. If a step has a result worth confirming, write the result as a follow-up sentence below the action, not as a separate numbered step.
  - **Do:**
    ```
    4. Click **Download** for your entitlement.
       The download portal opens.
    ```

- **R-PROC-03:** Start each step with an imperative verb: *Open*, *Click*, *Select*, *Navigate to*, *Run*, *Enter*, *Right-click*, *Make sure that*.

- **R-PROC-04:** For sub-steps, use a nested list. Avoid deep nesting; restructure the procedure if you find yourself nesting more than two levels.

- **R-PROC-05:** State prerequisites in a bullet list under a bold **Prerequisites** lead-in, before step 1. Phrase each bullet as a complete sentence. Common openers:
  - **`You must have ...`** — a role, permission, or capability the reader holds.
  - **`You need ...`** — an artifact, piece of information, or credential the reader must bring.
  - **`The <thing> must ...`** — a required state of the system, device, or component the procedure acts on.
  - **`*(Optional)* You need ...`** — prefix the bullet with the italicized `*(Optional)*` token when the prerequisite is not strictly required.

  Put any subordinate clarification in a trailing parenthetical. Avoid opener fragments like "Knowledge of …" or attribute-style noun bullets — they are inconsistent with the patterns above.

- **R-PROC-06:** Use a "To do X:" lead-in before a procedure when the goal isn't already obvious from the heading.
  - **Do:** "To create an account:"

- **R-PROC-07:** Bold UI labels quoted in steps: **Next**, **Sign In**, **Installation** tab. System output strings appear in plain prose or in quotes.

- **R-PROC-08:** For multi-system procedures, use a bold inline label to identify which system the step applies to: **On the server**, **On the client machines**. Don't promote these labels to H3.

- **R-PROC-09:** When a procedure has alternate paths, label each block with a bold lead-in: **To export as PDF:** … **To export as CSV:** …

- **R-PROC-10:** Include screenshots for visually distinctive UI moments (installer wizards, confirmation dialogs, custom UI). Don't screenshot trivial OS dialogs or menu paths that read cleanly in text.

- **R-PROC-11:** Prefer device-neutral "Select" for menu items, list items, check boxes, and tabs. Use "Click" for buttons, links, and clickable affordances. Both "Select" and "Click" are acceptable; follow the Microsoft Writing Style Guide convention for the control type. "Choose" is acceptable when it reads naturally — do not ban it outright.

---

## 6. Formatting: text emphasis, UI (R-FMT)

- **R-FMT-01:** **Bold** is for on-screen UI text and for term-list run-in headings (R-LIST-10), and nothing else. On-screen UI text covers:
  - UI element names: **Next**, **Sign In**, **Installation** tab
  - Specific keys and combos: **Enter**, **Ctrl+Alt+Del**
  - Status values the user sees on screen

  File names, paths, commands, tokens are **not** bold — use monospace (§7).

- **R-FMT-02:** *Italics* is for:
  - Titles of other documents
  - File-object names being discussed conceptually (the *activation request* file)
  - Terms being introduced (the *injection sequence* is …)
  - Variable placeholders in prose (the *hostname* of the server)

- **R-FMT-03:** No underlining for emphasis. Underline is reserved for hyperlinks.

- **R-FMT-04:** No ALL CAPS for emphasis. ALL CAPS in monospace is conventional for environment-variable names that your platform or language ecosystem defines as uppercase by convention — use the form your platform documents.

- **R-FMT-05:** Menu navigation paths use bold names separated by `>` with single spaces.
  - **Do:** "Navigate to **Administration > Licenses**."

- **R-FMT-06:** When referring to a UI control by both type and name: type lowercase, name in bold. "the **Next** button", "the **Installation** tab". For files, file name in monospace: "the `installer.exe` file".

- **R-FMT-07:** Use double quotes for short quoted system text (messages, labels, values). Use straight quotes in source; whether the renderer converts to smart quotes depends on the publishing platform.

---

## 7. Code, commands, syntax (R-CODE)

Use monospace for all code, commands, file paths, file names, tokens, and constants.

- **R-CODE-01:** Inline commands and flags in `monospace`: `netstat -aon`, `services.msc`.

- **R-CODE-02:** Multi-line command syntax in a fenced code block.
  - **Do:**
    ````
    ```
    installer.exe --silent --norestart PRODUCT=example LICENSE_ACCEPTED=true
    HOST=<hostname> ADMIN_KEY=<username>
    ```
    ````

- **R-CODE-03:** File names and extensions in `monospace`: `installer.exe`, `config.xml`, `.json`, `.yaml`.

- **R-CODE-04:** File paths in `monospace`: use the path style of the target OS or platform. Example: `/etc/app/config.yaml` (Unix) or `C:\App\Config` (Windows).

- **R-CODE-05:** Placeholders in syntax use angle brackets inside the monospace block: `<hostname>`, `<password>`. Define each placeholder immediately below the block in a `where:` definition list.
  - **Do:**
    ```
    where:
      <hostname> is the hostname of the server
      <username> is the user name used to connect
    ```

  In running prose (not a code block), use italics without angle brackets: "Enter the *hostname* of your server."

- **R-CODE-06:** Environment variables in `monospace` with their delimiters as your platform defines them. For example, shell variables in `$VAR` or `${VAR}` form. Use the casing the platform documents for the variable.

- **R-CODE-07:** Return codes and error constants in `monospace`. Use the casing the platform or specification defines for those constants.

- **R-CODE-08:** No shell prompts (`$`, `>`, `PS>`) in command examples unless the prompt is the point. Show clean command strings.

- **R-CODE-09:** URLs in body text are hyperlinks, not code. URLs in syntax patterns (for example, `https://<server>/api/v1/...`) go in monospace.

---

## 8. Links and cross-references (R-LINK)

- **R-LINK-01:** Prefer "see" for all cross-references. Capitalize **See** only at sentence start. "Refer to" is acceptable when the context calls for it, but avoid "please refer to".

- **R-LINK-02:** Use descriptive link text. Link the differentiator word, not the whole phrase.
  - **Do:** "Complete the table [manually](...)."
  - **Don't:** "[Click here](...) to learn more."

- **R-LINK-03:** Never use "click here" or "this link" as link text.

- **R-LINK-04:** URLs in body text are clickable. Show the full URL only when the link target is meaningful out of context (for example, a registration portal).

- **R-LINK-05:** End each procedural page with a `## See also` section listing related pages with one-line descriptions. The conventional heading is "See also"; alternative headings such as "Related topics" or "Further reading" are acceptable when they fit the content better.

- **R-LINK-09:** To cross-reference a section within another page, spell the relationship out: use the section's own heading wording as the link text and name the containing page in the surrounding prose. Where the page is clear from context, linking the section heading alone is sufficient.
  - **Do:** "See the [Internet requirements](../reference/system-requirements#internet-requirements) section of System Requirements."
  - **Do (page obvious from context):** "Complete the steps in [Remove a user](../howto/account/manage-users#remove-a-user)."
  - **Don't:** join page and section with a separator symbol in the link text: `[System Requirements → Internet Requirements]`, `[System Requirements §Networking]`, or `[System Requirements > Internet Requirements]`. `→` and `§` have no defined meaning here, and `>` is reserved for UI menu paths (R-FMT-05).
  - Match the link text to the target's actual heading (sentence case per R-STRUCT-02), not a title-cased paraphrase. This follows the Google developer documentation style guide, which spells the section-of-page relationship out rather than using a separator glyph.

- **R-LINK-10:** To link to another section of the *same* page, use the section's heading wording as the link text with a bare `#anchor` target. Do not add positional language ("the section above", "see below"); name the section instead (R-LOC-01). Add "earlier on this page" or "later on this page" only when reading order genuinely matters.
  - **Do:** "The only on-device credentials are the rotated administrative accounts described under [Attack surface](#attack-surface)."
  - **Do (order matters):** "Apply the controls described later on this page under [Shared responsibility](#shared-responsibility)."
  - **Don't:** "See the section above." / "As shown below." / "the [Attack surface](#attack-surface) section above".

Platform-specific internal-link form (extension, slug) follows the active platform profile — see the platform profile.

---

## 9. Admonitions (R-ADMON)

Use the admonition set defined by the active publishing platform (see the platform profile in the Documentation Domain Context). The table below shows common types; not all platforms support every type.

| Label | Use when | Severity |
|---|---|---|
| **Note** | Supplementary info, easy-to-miss behavior, not consequential. | Low |
| **Tip** | Optional best practice or shortcut. Skip if there's no tip-worthy content. | Low |
| **Important** | Critical info the reader must follow. Non-following leads to confusion or rework. | Medium |
| **Caution** | Potential data loss, security impact, compliance breach, irreversible config change. | High |
| **Warning** | Risk of physical harm to people or hardware damage. | Highest |

- **R-ADMON-01:** Use sentence-case labels (Note, Tip, Important, Caution, Warning). Not ALL CAPS.

- **R-ADMON-02:** Caution and Warning text uses imperative phrasing focused on action and consequence. State what *not* to do and what happens if the reader does it. Keep admonition text concise — 1–3 sentences is a useful target.
  - **Do:** "**Caution:** Removing this setting without a backup may result in data loss. Verify that you have a current backup before continuing."
  - **Don't:** "**Caution:** Be careful with this setting."

- **R-ADMON-03:** Don't stack admonitions. Two in a row means one or both should be inline prose. Merge or rewrite.

- **R-ADMON-04:** Place an admonition adjacent to the step or sentence it qualifies. Every admonition earns its visual interrupt.

- **R-ADMON-05:** Don't invent admonition types beyond those the platform profile defines. Use the admonition types from the active platform profile. Custom labels (Info, Best Practice, Heads up, Pro tip, Did you know, See also as an admonition, or product-specific labels) are not part of a generic admonition set.

- **R-ADMON-06:** Prefer inline paragraphs over admonition blocks. Use an admonition only when the consequence of missing the content is irreversible or surprising.

---

## 10. Lists and tables (R-LIST)

- **R-LIST-01:** Bulleted lists use a consistent marker in source (for example, `-`). Use a consistent indent for sub-bullets; follow your publishing platform's convention.

- **R-LIST-02:** List items must be parallel in structure. All start with the same part of speech.
  - **Do (all noun phrases):**
    - Acquisition
    - Data analysis and reporting
    - Shared services

- **R-LIST-03:** Capitalize the first word of each bullet. Sentence case for descriptive bullets; preserve product/feature names exactly.

- **R-LIST-04:** Terminal punctuation:
  - Full sentences end with a period.
  - Fragment bullets have no terminal punctuation.
  - Be consistent within a single list.

- **R-LIST-05:** Definition-style list: inline `term: definition` with the term in bold or italics.
  - **Do:** "*Data security:* physical protection of data by limiting access to the system."
  - For a *bulleted* list of label-plus-description items (a term list), use the run-in-heading form in R-LIST-10 (bold label, period in plain text), not italics, for consistency with the Google and Microsoft style guides.

- **R-LIST-06:** Tables use a short caption above. Header row is the first row. Header cells use sentence-case noun phrases ("Code", "Return value", "Meaning"). Right-align numeric columns.

- **R-LIST-08:** Don't bullet a single item. Write a sentence.

- **R-LIST-09:** Lists nested deeper than two levels almost always benefit from being broken into sub-headings or sub-procedures.

- **R-LIST-10:** Term lists (run-in headings). For a bulleted list whose items are a short label followed by an explanation, bold the label in sentence case, then put the separating period in **plain text** (outside the bold), then a capitalized description that ends with a period whether it is a fragment or a full sentence. Keep one style across the whole list.
  - **Do:** "**Outbound-initiated**. The client joins the tunnel by an outbound TLS connection."
  - **Don't (bolded period):** "**Outbound-initiated.** The client joins…"
  - **Don't (italic label):** "*Outbound-initiated.* The client joins…"
  - This bold use is an explicit exception to R-FMT-01 and to the italics-for-emphasis default (R-FMT-02). It follows the Google developer documentation style guide (bold run-in headings, ended with a period or colon, consistently) and the Microsoft Writing Style Guide (term lists: bold term, period in plain text). Standardize on the period form. A colon is an acceptable alternative only if used consistently across the list; when a colon is used, lowercase the description, per Google.

- **R-LIST-11:** Choose between a table, a bulleted list, a numbered list, and a description list by how many attributes each item carries and what the reader does with them:
  - **Numbered list** — items whose sequence matters: ordered steps, phases, ranked priorities (see R-PROC).
  - **Bulleted list** — an unordered collection of single-attribute items the reader skims rather than compares: options, examples, named classes. Don't bullet a single item (R-LIST-08).
  - **Description / term list** — *paired* data: each item is one label plus one description or definition. Use the bold run-in form in R-LIST-10.
  - **Table** — each item has **two or more attributes** the reader scans, compares, or looks up (for example, a value with a type and a description). Give it at least two columns and a complete lead-in sentence (R-LIST-06).

  Don't force single-attribute items into a table, and don't lay out multi-attribute, look-up data as a bulleted list. Don't use a table to lay out a page, for a single column (turn it into a list), or inside a numbered procedure. For label-plus-one-description data, the choice between a two-column reference table and a run-in term list (R-LIST-10) is a judgment call: prefer the table when the reader looks values up by scanning a column, the term list when it reads better inline. This follows the Google developer documentation style guide ("a table when each item is three or more pieces of related data; a description list for paired data; a list for a simple collection or a sequence") and the Microsoft Writing Style Guide (use a table when items share the same kinds of information and there is more than one piece of information per item).

- **R-LIST-12:** Put a structured catalog with its primary reader, and define it once. Decide which topic's audience actually needs an enumeration or attribute table, place the authoritative copy there, and cross-reference it from other topics instead of duplicating it (R-TOPIC-03, R-STRUCT-06).
  - A reviewer-facing *coverage summary* and a user-facing *value enumeration* are different content for different readers; presenting both is not duplication. Re-stating the same enumeration verbatim in two topics is.
  - This mirrors Diátaxis: reference is information-oriented and consistent, and links to how-to and explanation rather than absorbing or repeating them.

---

## 11. Numbers, dates, units, versions (R-NUM)

- **R-NUM-01:** Numerals for all measurements, sizes, counts of UI elements, durations, quantities. Don't spell out.
  - **Do:** "8 GB RAM", "3.0 GHz", "60 days", "15 characters", "1–6 items"

- **R-NUM-02:** Space between numeral and unit: `8 GB`, `3.0 GHz`. Exceptions: percent signs (`5%`), degree symbols.

- **R-NUM-03:** Spell out small numbers (one through nine) only when used as ordinary words ("one server"), not measurements.

- **R-NUM-04:** Software versions follow the versioning scheme the product defines (for example, semantic versioning `MAJOR.MINOR.PATCH`). First mention: include the product name and version together. Short form thereafter: just the version string. Follow your product's versioning documentation for the canonical format.

- **R-NUM-05:** Dates in ISO 8601: `2026-05-20`. Never `5/20/26` or `May 20, 2026` in tables/metadata. In running prose, "May 2026" is acceptable.

- **R-NUM-06:** Numbered ranges use en-dash: `1–6 items`, `pages 23–25`. Never hyphen for ranges.

- **R-NUM-07:** File sizes use uppercase byte units: `MB`, `GB`, `TB`. Never `mb` or `Mb` (megabits).

- **R-NUM-08:** Trademark symbols (® and ™) in running text: follow MS/Google guidance, which drops them from running text once the mark is established. In formal legal or compliance contexts, follow the trademark holder's requirements. Do not routinely append ® or ™ in body prose; use them where legally required or on first use in formal contexts.

- **R-NUM-09:** Preserve source format for phone numbers, doc numbers, and identifiers.
