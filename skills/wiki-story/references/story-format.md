# Story Format

## Contents
- Story structure
- Acceptance Criteria (A/C)
- Design Notes (D/N)
- QA Notes (Q/N)
- Voice and tone
- Common mistakes

---

## Story Structure

Write each story in this order:

1. **Title** — Concise, imperative or descriptive. No "As a user" framing in the title. Tags in brackets where appropriate: `[SPIKE]`, `[Tech]`, sub-story numbers like `1.`, `2.`, `3.`
2. **Description** — **Mandatory.** Format: **"As a [persona], I want [capability] so that [benefit]."** Follow with 1–2 sentences of additional context if needed. Optional **Background** section when the story benefits from explaining the problem space or business rationale.
3. **A/C** — Numbered list. Each item testable, binary, user-facing. Present tense, declarative. Sub-items use indented numbering: `1.1`, `1.2`.
4. **D/N** — Numbered list. Critical design aspects. Negotiable. Omit for simple stories when obvious.
5. **Q/N** — Numbered list. Test guidance: impacted use cases, scenarios, workflows. Omit for simple stories when obvious.

---

## Acceptance Criteria (A/C)

A/C describes what the target persona or system must be able to do or observe once the story is complete. Non-negotiable. Defines "done."

**The A/C test:** Can a QA engineer or the target persona verify this as an end user, without reading the code or knowing the implementation? If no — it is a D/N item, not A/C.

**A/C items answer:**
- What can the target persona do?
- What does the target persona see?
- What happens from the target persona's perspective when X occurs?
- What must never happen from the target persona's perspective?
- What benefits or value the target persona expects to get?
- What are the edge cases as the target persona would experience them?
- What other side effects are expected — such as activity log entries getting created?
- What are the limitations — what the system does NOT do, boundary conditions, capacity limits?
- What are the constraints — non-negotiable design requirements (e.g., "must match existing Users page layout", "must use standard error format")?

Note: Limitations and constraints are often implicit in other A/C items. Make them explicit only when non-obvious, frequently misunderstood, or critical to success.

**A/C items do NOT:**
- Name scripts, flags, files, endpoints, or internal mechanisms
- Describe how the system achieves the outcome
- Use language like "the script calls...", "the flag is cleared...", "the endpoint returns..."
- Describe flexible error handling patterns or logging behavior — those are D/N

| Good A/C | Bad A/C (actually D/N) |
|----------|------------------------|
| "After reset and reboot, the device re-registers with its existing portal record automatically and becomes available for use without any setup-code entry." | "The script calls `wait_for_setup_code` and then reboots." |
| "Reset completes successfully even when the device has no network connection." | "Back up items to a timestamped backup directory before clearing." |
| "Activity log records: item added, replaced, and removed — with item name and acting user." | "The reset flag must be cleared so a second reboot does not re-trigger reset." |

---

## Design Notes (D/N)

D/N describes how to design it. Flexible — engineers can change or add to them after discussion with the PO or team. If D/N details are altered during implementation, the engineer must update the ticket before moving it to QA/Review.

**D/N items answer:**
- What specific UI changes to make?
- What specific UI behaviors to develop?
- In what order should operations happen?
- What specific wording for error messages or log entries?
- What consistency patterns to follow from existing UI? (If consistency is non-negotiable and defines "done", put it in A/C instead.)

**D/N appropriately includes:**
- Design guidelines and UI mockups
- Specific messages to be used
- Error handling patterns and logging behavior

---

## QA Notes (Q/N)

Q/N describes how to test the A/Cs. Guidance and reminders for QA.

**Q/N items answer:**
- Which customer use cases, scenarios, or workflows are most important to test?
- Which are low priority?
- What high-level actions does QA take to verify the story's intent?
- Which pre-existing functionality might be affected and should be regression-tested? (No corresponding A/C required.)

**Q/N length:** Keep concise. When a story has many A/C items but testing is straightforward, a short Q/N summarizing key scenarios is preferred over restating every A/C as a test step. Reserve detail for non-obvious scenarios that require specific setup.

**Q/N items do NOT:**
- Test D/N items directly (e.g. "confirm the flag file is cleared")
- Duplicate A/C wording without adding specifics like environments, workflows, or test steps
- Test behaviors untestable without code access

| Good Q/N | Bad Q/N |
|----------|---------|
| "Verify the new version appears in the catalog with the correct version and release date." | "Confirm the reset flag is cleared so a second reboot does not re-trigger reset." |
| "On a registered device, run the reset without removing it from the portal. Confirm it re-registers automatically after reboot and becomes available without setup-code entry." | *(rewrite as: "Reboot the device a second time after reset — confirm it does not reset again.")* |

---

## Voice and Tone

Direct and functional. No marketing language. Written for an internal engineering/QA audience. Domain abbreviations are used freely — use the project's standard abbreviations. Passive voice is common. Sentences are short and list-like even within prose.

---

## Common Mistakes

**1. "Wait for X" as an A/C**
If an A/C describes the system waiting for something, ask *why* — then write the A/C from the user's perspective: "After reboot, the device cannot be used until it is registered again."

**2. Restriction framing instead of capability framing**
Prefer "the user can register the device again from scratch" over "the device cannot be used until it is registered." Exception: Restriction framing is acceptable for security invariants, access denials, or hard system guards (e.g., "A user is locked out after 5 failed password attempts").

**3. "As it does today" in A/Cs**
This phrase belongs in D/N or the Description, not in A/C. A/Cs describe the desired end state, not continuity of existing behavior.

**4. Testing the absence of something**
Q/N items that test that something does *not* happen are valid but should be paired with a positive test that confirms the correct thing *does* happen.

**5. Tasks or components disguised as stories**
"As a developer, I want a database migration" is a task, not a story. A story requires a target persona with a visible change in behavior. Developer is not a target persona. Combine infrastructure items until each delivers direct user value.

**6. Splitting by architectural layer**
"Story 1: backend API endpoint" + "Story 2: device-side script" + "Story 3: UI update" is a horizontal split. Each piece is untestable and delivers no user value independently. Recombine into a single vertical slice, then use splitting patterns to find a thinner slice if still too big.

**7. Embedding rationale inside an A/C statement**
A/C states *what* is observable. If a constraint or rationale is already implied by the domain term used (e.g., "deleted" implies all deletion prerequisites), do not repeat it in the statement. When non-obvious rationale genuinely helps the reader, add it as a `Note:` on a separate line after the A/C item — not woven into the statement itself.

**8. Restating consequences that are logically implied**
If one A/C already says "the row is removed from the page," do not add "and any selections for it are cleared" — removal makes the selection unrepresentable. Only state a consequence explicitly if QA must verify it through a separate, independent observation (e.g., checking a database record that has no UI representation). Ask: *can this be verified independently of the stated outcome?* If not, omit it.
