---
name: wiki-defect-review
description: Review a newly submitted Jira defect like a first-line reviewer — clarify the issue, collect impact/frequency/workarounds from the submitter, judge scope, find duplicates, and propose a disposition — grounded in the wiki. Use for a single ticket (key or pasted text) or headless polling (--auto). Use when the user asks to review, triage, or assess a defect or bug ticket.
---

# Wiki Defect Review

Review defect tickets against the wiki. Two modes, one brain
(`${CLAUDE_PLUGIN_ROOT}/prompts/defect-review-prompt.md`):

**Args:** `[<JIRA-KEY> | --auto [--dry-run]]` — or no args with pasted ticket
text in the conversation.

- `<JIRA-KEY>` — interactive spot review of one ticket (e.g. `OLAC-7411`).
- *(pasted text)* — interactive review of ticket content the user pasted;
  skip the fetch, state, and delivery steps (analysis only).
- `--auto` — headless polling mode (server cron). Reviews every candidate
  the scanner emits and delivers per the configured mode.
- `--auto --dry-run` — same scan and review, but prints every would-deliver
  decision instead of delivering; writes no state. Run this first on a new
  server.

**Model floor: Opus or better.** Smaller models produce noticeably weaker
reviews on real tickets. Headless runs pin the model in the wrapper; for an
interactive review on a smaller session model, tell the user their comment
draft may be below par and suggest re-running on Opus.

---

## 1. Guardrails

```
test -f wiki.config.yaml && test -d wiki/
```

Missing either → **stop**: "This skill requires a domain-expert wiki repo
(`wiki.config.yaml` + `wiki/`). Run `/wiki-init` first."

Read the config gate:

```bash
python "${CLAUDE_PLUGIN_ROOT}/scripts/defect_review_config.py"
```

In `--auto` mode, `enabled: false` → print "defect_review disabled for this
wiki" and stop cleanly (exit 0 — the wrapper iterates many wikis).
Interactive mode proceeds even when disabled (spot reviews are always
allowed). `mode` selects delivery in step 6. NEVER run `qmd update`,
`qmd embed`, or `git pull` anywhere in this skill — on the server both the
checkout and the index belong to the content service (read-only contract).

## 2. Collect candidates

**Interactive with KEY:** the single ticket, `question_rounds`/`pending_asks`
from state:

```bash
python "${CLAUDE_PLUGIN_ROOT}/scripts/defect_review_scan.py" --no-prune 2>/dev/null | grep '"<KEY>"' || true
```

If the ticket is not in the scan output (already reviewed, wrong status),
review it anyway — interactive mode never refuses — with
`question_rounds: 0, pending_asks: []`.

**Interactive with pasted text:** no candidates step; go to step 3 with the
pasted content as the ticket.

**`--auto`:** every JSON line from:

```bash
python "${CLAUDE_PLUGIN_ROOT}/scripts/defect_review_scan.py"
```

With `--dry-run`, add `--no-prune` to that command — pruning writes the
state file, and dry-run must write no state at all.

Empty output → log "no reviewable candidates" and exit 0. Echo the skip
lines (stderr) into the run log — they are the audit trail.

## 3. Assemble the review input (per ticket)

1. **Render the ticket** (full thread — you must see your own prior review
   comments, which the default rendering stubs out for ingest):
   ```bash
   python "${CLAUDE_PLUGIN_ROOT}/scripts/jira_utils.py" <KEY> --print-md --include-bot-comments
   ```
2. **Attachments:** download and unpack everything viewable (the script
   enforces the caps — 50 MB per file, 250 MB unpacked per archive — and
   prints a manifest of every extracted file):
   ```bash
   python "${CLAUDE_PLUGIN_ROOT}/scripts/jira_utils.py" <KEY> --attachments --unpack --attachments-ext png,jpg,jpeg,gif,pdf,log,txt,zip,tar,tgz,gz,bz2,xz --attachments-dir /tmp/defect-review-<KEY>
   ```
   - **Images:** READ each one — the error often lives only there.
   - **PDFs:** Read paginated (`pages` arg); first pages plus any page the
     ticket points at.
   - **Text logs ≤ 200 KB:** read whole. Bigger: targeted only — grep the
     ticket's key nouns and error markers; pull only passages relevant to
     the reported issue; never summarize a whole log.
   - **Archives (`.zip`, `.tar.*`):** unpacked one nested level deep (an
     archive inside an archive is extracted; anything deeper stays packed
     and must be disclosed like a `.7z`). Triage from the printed
     manifest — never read files in unpacked order. Select only files
     plausibly tied to the reported failure: name match to the ticket's
     key nouns or component, error/crash logs over routine ones, mtime
     near the failure time when known. Install/setup logs and config
     dumps are noise unless the defect is about install/config.
     **Scan-then-read:** for a homogeneous report or log set, a subagent
     may mechanically scan the ENTIRE set (grep, status tallies) to
     support all-pass or absence claims — scans are not capped. Hard
     budget: at most 5 files READ into context per archive (each nested
     archive counts as its own archive); a scan's anomalies get first
     claim on those reads. Each selected file — or one homogeneous set —
     goes to a **dedicated subagent** (Agent tool, `general-purpose`):
     give it the ticket summary, the key nouns, and the path(s); it
     applies the log rules above (scanning the whole set first when one
     was given) and returns only relevant excerpts plus a one-line
     interpretation (≤10 lines). Never read archive contents in the main
     context.
   - **`.7z`, videos, other binaries:** not viewable — the comment must
     disclose each one it could not examine.
3. **Wiki grounding:** follow the canonical gate in
   `${CLAUDE_PLUGIN_ROOT}/prompts/qmd-first-gate.md` (including its unified
   server-index step 4 when `$WIKI_INDEX_ROOT` is set). Search 2–3 key nouns
   from the ticket summary over the wiki collection; open the top hits. Also
   search the raw collection for similar ingested tickets.
4. **Live duplicate candidates:** recent tickets not yet ingested:
   ```bash
   python "${CLAUDE_PLUGIN_ROOT}/scripts/jira_utils.py" --jql "project = <project.key> AND <issuetype clause> AND created >= -30d ORDER BY created DESC"
   ```
   `<issuetype clause>` = the same issue-type condition used in the config's
   `candidate_jql` (e.g. `issuetype = Defect`) — never assume `Bug`; issue
   type names vary per Jira project. Keep it light: key, summary, status
   per candidate.

## 4. Run the brain

Fill `${CLAUDE_PLUGIN_ROOT}/prompts/defect-review-prompt.md`:

- `## Ticket` — the rendered markdown (step 3.1) + one line per attachment
  finding (screenshots, PDFs, log excerpts, archive-subagent findings). The
  metadata table's **Reporter** row is the brain's greeting source for ask
  comments; do not strip it.
- `## Wiki grounding` — the retrieved pages (titles + the relevant excerpts).
- `## Live duplicate candidates` — the step 3.4 list.
- `## Review state` — `{"question_rounds": <n>, "max_question_rounds": <config>,
  "pending_asks": [...], "mode": "interactive"|"auto",
  "prior_disposition_code": <from the scan JSON, null when absent>,
  "prior_disposition": <from the scan JSON, null when absent>}`.

Parse the three output sections: `### COMMENT (kind: …)`, `### ANALYSIS`,
`### STATE`. Kind is `ask`, `assessment`, or `silent` (empty COMMENT body
— step 4a). The brain writes the comment body only — the typed header
(`<marker> — <label>`) is composed mechanically in step 5.

**Round-cap rule:** when `question_rounds >= max_question_rounds` AND
`prior_disposition_code` is null, instruct the brain that kind must not
be `ask` — an assessment with stated assumptions, or silent when every
consequential input is already posed in-thread. After an assessment has
been delivered the cap no longer applies — the brain's significance test
governs any further ask.

## 4a. Silent branch (kind: silent — never skip the floor check)

The brain stays silent when nothing significant and new moves the ticket
toward a disposition: the thread is waiting on an already-posed ask, the
newest activity is an operator or courtesy comment, or a reply leaves
the standing assessment unchanged.

- **Empty-thread floor (deterministic — never trust the brain on this):**
  the step 3.1 rendering shows NO comments at all → silence is invalid.
  Re-run the brain ONCE with: "This ticket has no comments, so nothing
  can have been already asked — silent is not available. Output all
  three sections again with kind ask or assessment (the round-cap rule
  still applies)." Then continue the normal pipeline (step 4b onward)
  with what it returns; never re-run the floor check.
- Valid silence skips steps 4b (challenge), 5 (contract), 5b (critic),
  and 6 (delivery) entirely — no comment, no email, no Jira write.
- The ANALYSIS must open by naming what the review is waiting on. Echo
  that line into the run log (auto) or show the ANALYSIS in conversation
  and state that no comment is warranted (interactive). In `--dry-run`,
  print `would stay silent` plus that line.
- In auto mode, go to step 7 and record state exactly as after a delivery, with two
  substitutions: `--updated` carries the PRIOR `emailed_for_updated`
  (read it with `defect_review_state.py get <KEY>`; omit the flag when
  null — no email went out this round), and the disposition flags carry
  the scan JSON's prior values forward (omit both when null), as for an
  ask. `--last-human-comment` from the scan JSON is what keeps the
  scanner quiet until the next human comment. With `--dry-run`, write no
  state (as always).

## 4b. Challenge pass (assessments only — never skip)

`kind: ask` skips this step. Dispatch a **fresh subagent** (Agent tool,
`general-purpose`) whose entire prompt is
`${CLAUDE_PLUGIN_ROOT}/prompts/defect-review-challenger-prompt.md` with
ONLY these sections filled:

- `## Ticket` — the step 3.1 rendering.
- `## Draft assessment comment` — the brain's COMMENT from step 4.

Give it nothing else — its independence is the point.

- `CHALLENGES: none` → proceed to step 5.
- Numbered challenges → re-run the brain ONCE with them appended: "A
  skeptical reviewer raised these challenges. Resolve each from your
  grounding — a challenge you cannot resolve becomes a Caveats line, or
  ask material if it could change the disposition; apply the security
  discretion rule to anything newly discovered — and output all three
  sections again." One challenger run, one revision, never a loop.
- Append the challenges and their resolutions to the ANALYSIS under a
  `Challenge:` heading — audit trail, like the critic's verdict.

## 5. Enforce the contract (mechanical, structure only — never skip for a drafted comment)

Write the COMMENT section to a temp file, then:

```bash
python "${CLAUDE_PLUGIN_ROOT}/scripts/comment_contract.py" /tmp/defect-review-<KEY>-comment.md --kind <kind> --marker "<marker from config>" --fix-marker --updated '<updated from the scan JSON>'
```

`--fix-marker` composes the typed header in place — `<marker> — needs more
information` (ask) or `<marker> — disposition proposal` (assessment), the
freshness line (`_Reflects the ticket as of …_`, assessments with
`--updated`), and the AI disclaimer line (`_AI-generated: statements in
this comment may be inaccurate_`, every kind) — replacing anything the
brain wrote there. Omit `--updated` for pasted-text
reviews (no ticket timestamp exists).

Exit 1 → ONE revision pass: re-run the brain with the violations appended
("Revise the comment to fix exactly these violations; change nothing else"),
re-check. Still failing → deliver anyway but append the violations to the
ANALYSIS (never block the pipeline on style), and say so in the run log.

## 5b. Critic pass (unbiased — never skip for a drafted comment)

Dispatch a **fresh subagent** (Agent tool, `general-purpose`) whose entire
prompt is `${CLAUDE_PLUGIN_ROOT}/prompts/defect-review-critic-prompt.md`
with ONLY these sections filled:

- `## Ticket` — the same rendered markdown from step 3.1.
- `## Draft comment` — the contract-checked draft from step 5.

Give the critic nothing else — no ANALYSIS, no wiki grounding, no duplicate
candidates, none of your reasoning. Its independence is the point.

Parse the critic's output:

- `VERDICT: pass` → proceed to step 6.
- `VERDICT: revise` + numbered edits → re-run the brain ONCE ("Apply
  exactly these edits; change nothing else"), then re-run the step 5
  checker on the result. Deliver whatever comes out — one critic run, one
  revision, never a loop, never block the pipeline.

Either way, append the critic's verdict and edits to the ANALYSIS under a
`Critic:` heading — it is part of the audit trail (email body, run log).

## 6. Deliver

**Interactive:** show the comment and the analysis in conversation. Do not
email, post, or write state. If the user says to send it, follow the
config `mode` exactly as below.

**`--auto --dry-run`:** print per ticket: key, kind,
would-`notify`/would-`post`/would-`update` (run `--list-comments` to decide
post vs update — it is read-only), would-post a disposition-change notice or
not, and the comment text. No delivery, no state writes.

**`--auto`, `mode: draft`:** email the draft via the notify API:

```bash
python "${CLAUDE_PLUGIN_ROOT}/scripts/jira_utils.py" <KEY> --notify --subject "[defect-review] <KEY>: <kind>" --body-file /tmp/defect-review-<KEY>-email.md --to "<notify_user from config>"
```

Email body layout (build the file exactly in this order):

```
PASTE-READY COMMENT (include the marker line when pasting):

<the comment>

----------------------------------------------------------------------
ANALYSIS (not for posting):

<the analysis>
```

**`--auto`, `mode: post`:** comments converse; the assessment is one living
comment, edited in place.

- `kind: ask` — post a new comment (a conversation needs a thread):
  ```bash
  python "${CLAUDE_PLUGIN_ROOT}/scripts/jira_utils.py" <KEY> --post-comment --body-file /tmp/defect-review-<KEY>-comment.md
  ```
- `kind: assessment` — find the living assessment comment, then update it:
  ```bash
  python "${CLAUDE_PLUGIN_ROOT}/scripts/jira_utils.py" <KEY> --list-comments
  ```
  The bot comment whose preview starts with `<marker> — disposition
  proposal` is the one to edit:
  ```bash
  python "${CLAUDE_PLUGIN_ROOT}/scripts/jira_utils.py" <KEY> --update-comment <id> --body-file /tmp/defect-review-<KEY>-comment.md
  ```
  No such comment (first assessment, legacy untyped comment, or a human
  deleted it) → fall back to `--post-comment` as for an ask.
- **Disposition-change notice** — only after a `kind: assessment`
  delivery, never for an ask (an ask's null `disposition_code` is not a
  change). Comment edits do not notify watchers, so when the STATE
  `disposition_code` differs from a non-null `prior_disposition_code`,
  additionally post one comment built mechanically (no brain, no
  contract/critic pass), exactly:
  ```
  <marker> — assessment revised
  Previous assessment revised. "<prior_disposition>" → "<disposition>"
  ```
  Same code, different wording → no notice; the in-place edit happens
  without one.

If `also_notify: true`, send the notify email too (same layout, subject
prefix `[defect-review posted]`).

**Security withheld detail:** when the security discretion rule kept
discovered detail out of the comment (the ANALYSIS carries it), send the
notify email (subject prefix `[defect-review security]`, body = the
ANALYSIS) even when `also_notify` is false, so the review team gets the
full picture. Jira's notify API refuses to email the requesting account
(recipients-empty 400): when `notify_user` is the bot's own account, put
the ANALYSIS in the run log instead and say so in the step 8 report
line. The comment itself never claims a delivery either way.

Primary delivery failed — the ask post, the assessment update/post, or the
draft-mode email (non-zero exit) → report the error, do NOT write state
for that ticket (it retries next poll), continue with the next ticket, and
exit non-zero at the end so the wrapper flags the run. A secondary write
failing after the primary comment landed — the disposition-change notice
or an `also_notify` email → still record state in step 7: the comment is
on the ticket, and skipping state would both block the retry
(bot-spoke-last hides the ticket) and desync rounds/disposition from
reality. Report the secondary failure and exit non-zero.

## 7. Record state (auto mode only, after successful delivery or a valid silent review)

```bash
python "${CLAUDE_PLUGIN_ROOT}/scripts/defect_review_state.py" record <KEY> \
  --updated '<updated from the scan JSON>' \
  --rounds <question_rounds from STATE> \
  --pending-asks '<pending_asks from STATE, as a JSON list>' \
  --last-human-comment '<last_human_comment from the scan JSON; omit the flag when null>' \
  --disposition-code '<disposition_code>' --disposition '<disposition>'
```

Disposition args: from STATE when kind=assessment; when kind=ask, carry the
scan JSON's prior values forward unchanged (omit both flags when null).
`last_human_comment` is the post-mode repeat guard — the scanner skips the
ticket until a newer non-bot comment appears.

## 8. Report

End every run with a one-line-per-ticket summary:

```
OLAC-7411  ask (round 2/3)   emailed rehman@…      2 pending asks
OLAC-7423  assessment        posted                dupe of OLAC-7101
OLAC-7398  assessment        updated in place      disposition unchanged
OLAC-7401  assessment        updated + notice      accept-for-fix → duplicate
OLAC-7415  silent            no action             waiting on round-1 asks
```

Then delete every reviewed ticket's working files —
`rm -rf /tmp/defect-review-<KEY>*` (downloads, unpacked archives, comment
and email temp files). Attachments are working files, never kept artifacts.

Server setup (wrapper script, cron, prerequisites, rollout):
`${CLAUDE_PLUGIN_ROOT}/skills/wiki-defect-review/references/server-setup.md`.
