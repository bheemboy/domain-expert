# Story Sizing, Splitting, and Checklists

## Contents
- What "small enough" means
- INVEST checklist
- Pre-submission checklist
- Splitting patterns
- Evaluating competing splits
- Issue types

---

## What "Small Enough" Means

A well-sized story:
- Can be developed, tested, and demoed independently
- Represents the smallest coherent slice of user value — not a task list
- Can be completed within a sprint
- Is a **vertical slice** — cuts across all layers (backend API, device/client logic, UI) needed to produce an observable change for the user

**Signs a story is too big:**
- It contains multiple independent user flows
- It requires significant changes in functionality or workflows
- Its Q/N section requires setup that depends on unimplemented work

**Signs a story is too small:**
- It is a single string change or config value (exception: when it is standalone, not part of a larger set)
- It has no testable A/C beyond "the string is updated"
- It could be absorbed into a related story with no loss of clarity

---

## INVEST Checklist

- **Independent** — Can be prioritized without being blocked by another story. Exception: stories in a set that build on one another.
- **Negotiable** — Leaves room for the team to discuss how to build it. Implementation details belong in D/N, not A/C.
- **Valuable** — Delivers a visible change in behavior for a user. If not, it may be a task masquerading as a story.
- **Estimable** — The team knows enough to size it. If not, break out a spike first.
- **Small** — 6–10 stories of this size can fit in a sprint.
- **Testable** — QA can verify it is done.

Different attributes matter at different times. Going into sprint planning, Small, Estimable, and Testable are most critical. Further out, Independent, Negotiable, and Valuable matter more. All six should be satisfied before a story enters a sprint.

---

## Pre-Submission Checklist

**INVEST**
- [ ] The story can be prioritized without being blocked by other stories (Independent)
- [ ] Implementation details are in D/N, leaving room for team discussion (Negotiable)
- [ ] The story describes a user-visible change in behavior (Valuable)
- [ ] The team can estimate the story (Estimable) — if not, break out a spike
- [ ] 6–10 stories of this size fit in a sprint (Small)
- [ ] QA can verify it is done (Testable)

**Vertical Slice**
- [ ] The story is not a horizontal slice (not just an API, script, or UI change alone)
- [ ] The story can be demoed end-to-end independently

**A/C**
- [ ] Every A/C is verifiable by QA without code access or shell access
- [ ] Post-reset / post-event state is described from the user's perspective
- [ ] Capability framing used ("user can...") rather than restriction framing ("cannot be used until...")

**D/N**
- [ ] Every implementation or design specific detail from A/C drafts has been moved here
- [ ] Ordered operation sequences are listed where order matters
- [ ] Idempotency behavior is described where the script or operation may be re-run
- [ ] Describes flexible user requirements such as logging, error handling, or specific messages

**Q/N**
- [ ] Q/N items describe observable outcomes, not internal state
- [ ] Negative tests ("confirm X does not happen") are paired with positive tests
- [ ] Guidance is included for any A/C whose test approach is non-obvious

**Splitting (if the story is too big)**
- [ ] Tried at least 2–3 splitting patterns before choosing one
- [ ] Each resulting story is a vertical slice with its own testable A/Cs
- [ ] The split chosen either exposes deprioritizable work or produces equally-sized stories
- [ ] No resulting story is a horizontal layer slice

---

## Story Splitting

### The Meta-Pattern: Find the Complexity, Reduce the Variations

1. **Find the core complexity** — What part is most likely to surprise you or require learning? Often the part that depends on user behavior, new integrations, or external dependencies.
2. **Identify the variations** — What are there many of? Business rules, user types, device/entity states, connectivity scenarios, data shapes.
3. **Reduce all variations to one** — Find a single, complete slice through the complex part. That is your first story.

### Splitting Patterns

**Pattern 1: Workflow Steps**
Build the simplest end-to-end path first, then add intermediate steps and special cases in follow-ups. Do not split one step at a time from beginning to end — the value is usually in the beginning and end together.

*Example:* "Reset completes and the device re-registers" first. "Reset backs up user data before clearing" as follow-up.

**Pattern 2: Operations (CRUD)**
If a story says "manage" or covers multiple operations, split by operation.

*Example:* "Manage device settings" → "View device settings," "Edit device settings," "Reset device settings."

**Pattern 3: Business Rule Variations**
If a story behaves differently under different business rules, each rule can be its own story.

*Example:* Reset behavior differs for activated vs. non-activated devices — that is two stories.

**Pattern 4: Variations in Data**
If complexity comes from handling different data shapes or types, start with the simplest data variant.

*Example:* "Apply a single OS update to a device" before "Apply a batch of OS updates to multiple devices."

**Pattern 5: Simple / Complex**
When a story keeps growing, ask: "What is the simplest version of this?" Capture that as its own story. Move every variation into follow-ups.

*Example:* "Reset with network connectivity" before "Reset without network connectivity."

**Pattern 6: Defer Performance (or Other Non-Functional Requirements)**
Split into "make it work" then "make it fast / secure / scalable."

*Example:* Ship server-to-device sync slow first, then optimize in a follow-up.

**Pattern 7: Major Effort**
When one variation requires building infrastructure that makes the rest trivial, split into "first variation (builds infrastructure)" and "remaining variations (given infrastructure exists)."

*Example:* "Apply driver update for one driver type" builds the mechanism. "Apply driver updates for all supported driver types" extends it.

**Pattern 8: Break Out a Spike**
When the team cannot estimate because the implementation is unclear. Spikes are time-boxed — the A/Cs are **questions answered**. Write the build story once you know enough. Use as a last resort after trying other patterns.

### Evaluating Competing Splits

Prefer the split that:
1. **Lets the PO deprioritize or throw away a story.** A split that reveals a low-value slice exposes waste early.
2. **Produces more equally-sized stories.** Four roughly equal stories give the PO more flexibility than one large and one tiny.

---

## Issue Types

- **Features** — Highest-level grouping. Major product capabilities or investment areas (e.g., "Software Update Management"). Broad and long-lived.
- **Epics** — Mid-level groupings that break a Feature into a cohesive deliverable chunk. Maps to a specific, time-bounded set of work.
- **Stories** — Individual units of user-facing work. Belong to Epics. Represent specific implementable features or investigations (spikes). Spikes are time-boxed and added to the sprint when someone is working on them.

The hierarchy follows SAFe conventions: `Feature → Epic → Story` (with Defects cutting across all levels).

---

## After Writing All Stories

1. **Apply the INVEST checklist** to each story. Flag any story that fails.
2. **If a story is too large**, suggest a split using one of the patterns above. Name the pattern used.
3. **Note any use cases** the stories collectively miss.
4. **Note any stories** that feel like horizontal slices and should be recombined.
