# Troubleshooting topics (R-TROUBLE)

Load when authoring or reviewing a troubleshooting page. Troubleshooting is a
**recognized hybrid topic type** that may combine instructional content (recovery
procedures) with reference content (symptom and error catalogs). This is not a
house exception: **DITA 1.3** defines a dedicated `troubleshooting` topic type
structured as `condition → cause → remedy`, supporting multiple fallback
cause–remedy pairs and a `responsibleParty` element. The **Microsoft KB** pattern
(*Symptoms → Cause → Resolution*, optionally *Workaround* and *More information*)
follows the same structure. Both are long-established industry standards; cite
them when justifying the shape to reviewers.

---

## Topic selection

- **R-TROUBLE-01:** Use this topic type when a page exists to help a reader
  diagnose and recover from a specific failure mode, not to teach a task. If the
  reader already knows what they want to do (for example, "Activate a license"),
  the page is a how-to, not troubleshooting.

---

## Page structure

- **R-TROUBLE-02:** A troubleshooting page follows the Symptom / Cause /
  Resolution core (aligned to DITA 1.3 and the Microsoft KB pattern). Required
  sections:

  1. **Symptom** — what the reader observes: UI message, error code, log line,
     or behavioral change.
  2. **Confirm this is the right document** — a quick triage block (one or two
     checks or commands) that routes the reader elsewhere if the symptom matches
     a different page.
  3. **Affected services** — what is and is not working while this failure
     persists.
  4. **Prerequisites** — what the reader needs before starting diagnostic steps
     (access, permissions, tools).
  5. **Diagnostic steps** — numbered investigation steps, each producing output
     that routes the reader to a resolution or to a related page.
  6. **Resolution** — corrective action(s), grouped by cause when more than one
     is possible.
  7. **Related documents** — see-also links and any escalation path.

- **R-TROUBLE-03:** Optional sections:

  - **Background** — between *Affected services* and *Prerequisites*, only when
    the reader needs a short mental model to interpret diagnostic output. Keep to
    one or two paragraphs; deeper conceptual material belongs in an explanation
    topic.
  - **Root cause** — between *Symptom* and *Confirm this is the right document*,
    only when multiple sub-symptoms share one underlying cause and naming it up
    front helps the reader decide quickly.

- **R-TROUBLE-04:** Troubleshooting is a recognized hybrid topic type (grounded
  in DITA 1.3 and the Microsoft KB pattern) that may combine instructional and
  reference content within a single page. This is standard practice for the
  topic type, not an exception to a single-type rule.

---

## Symptom section

- **R-TROUBLE-05:** In the Symptom section:
  - Lead with the observable, not the inferred cause.
  - Quote literal UI strings, log lines, and error messages in monospace.
  - For multi-symptom pages, use a bulleted list of observables rather than a
    paragraph.

---

## Diagnostic steps

- **R-TROUBLE-06:** In the Diagnostic steps section:
  - Use imperative voice and numbered steps (consistent with how-to procedure
    style).
  - Every step that produces output ends with a result table indicating next
    actions:

    | Result | Next step |
    | ------ | --------- |
    | ...    | ...       |

  - Each row routes the reader to the next diagnostic step, to a Resolution
    sub-section on the same page, or to a related page.
  - Show the exact command or query in a fenced code block immediately before
    the result table. A branching table is recommended for steps with discrete
    outcomes; it is optional for steps with a single expected output.

---

## Resolution section

- **R-TROUBLE-07:** In the Resolution section:
  - When the page covers more than one possible cause, use H3 sub-sections, one
    per cause. Diagnostic-step result tables link to the relevant sub-section by
    anchor.
  - List corrective actions as bullets or short numbered steps within each
    sub-section.
  - State who performs the action when it is not obviously the reader — for
    example, "Request that your IT team …" This maps to DITA 1.3's
    `responsibleParty` element: make the actor explicit whenever the reader is
    not the one acting.

---

## Metadata block

- **R-TROUBLE-08:** A troubleshooting page may include an optional metadata
  block immediately under the H1, listing any combination of **Product**,
  **Audience**, and **Support reference**. This block surfaces ownership and
  routing information for support staff and is appropriate for troubleshooting
  pages. It is not required. Keep it concise; avoid support-organization-specific
  fields that do not generalize to your publishing context. Example shape:

  ```
  **Product:** <product name>
  **Audience:** <intended audience>
  **Support reference:** <ticket ID or KB number>
  ```

---

## Page identification

- **R-TROUBLE-09:** Each troubleshooting page is identified by its
  sentence-case title (for example, `TCP port 443 blocked`). The title appears
  unmodified in both the `title:` frontmatter and the H1. No ID prefix or code
  is added to the title. The slug is the canonical reference for support tickets,
  error messages, and inbound links.

- **R-TROUBLE-10:** Pages under a troubleshooting folder use a semantic slug
  that reflects the subject of the page, for example
  `troubleshooting/tcp-port-443-blocked`. The filename mirrors the slug stem
  (`tcp-port-443-blocked.md`). Choose a slug for clarity; slugs can be renamed
  without invalidating a record because there is no immutable ID separate from
  the slug. Platform-specific slug prefix conventions (such as a category prefix
  scheme) belong in the platform profile, not here.

---

## Cross-links

- **R-TROUBLE-11:** Cross-links to troubleshooting pages use the page title as
  link text with no added prefix, no bold, and no surrounding punctuation
  structure: `[TCP port 443 blocked](/troubleshooting/tcp-port-443-blocked)`.
  Apply descriptive link text (WCAG 2.4.4): the link text must convey
  destination and purpose without relying on surrounding context. Avoid coupling
  a link to adjacent em-dashes or other punctuation that separates it visually
  from its label.

---

## Terminology

- **R-TROUBLE-12:** Customer-facing terminology applies to troubleshooting pages
  even when the audience includes support staff or internal roles. The vocabulary
  of the page follows the customer-facing terminology defined in the wiki's
  `terminology/` folder, not internal role names, system identifiers, or
  support-org jargon. The audience of a page can be broader than customer-only;
  the vocabulary cannot.

---

## Triage and tool pages

- **R-TROUBLE-13:** A page inside a troubleshooting folder may exist solely to
  route the reader to the right failure-mode page — for example, a page
  describing a diagnostic tool whose output determines which specific
  troubleshooting page applies. These pages follow the standard troubleshooting
  structure with two adjustments:

  - The **Symptom** section describes a class of failures (for example,
    "connectivity is degraded but no specific error string is available"), not a
    single observable.
  - The **Resolution** section defers to the linked failure-mode pages and may
    be a short paragraph stating this.

  Use triage pages sparingly. Most troubleshooting pages must still address a
  specific failure mode (R-TROUBLE-01). Cross-links from triage pages use the
  R-TROUBLE-11 form.

---

## Placeholder convention in code blocks

- **R-TROUBLE-14:** When a command target depends on which endpoint is failing
  (the reader supplies the value), use an angle-bracket placeholder such as
  `<hostname>`. Include a comment above the command explaining what to substitute
  and providing a representative example:

  ```bash
  # Replace <hostname> with the failing endpoint for your environment.
  # Example: api.example.com

  nc -zv <hostname> 443
  ```

  When the failing endpoint is fixed by the page's diagnostic scope — the same
  target for every reader on that page — use the concrete value instead of a
  placeholder.
