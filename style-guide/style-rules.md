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
