---
name: wiki-defect-review
description: Review a newly submitted Jira defect like a human reviewer — clarify, suggest troubleshooting, judge scope, find duplicates, and summarize with actions — grounded in the wiki. Use for a single ticket (key or pasted text) or headless polling (--auto). Use when the user asks to review, triage, or assess a defect or bug ticket.
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
python -c "import sys; sys.path.insert(0, '${CLAUDE_PLUGIN_ROOT}/scripts'); import config; import json; print(json.dumps(config.defect_review_config()))"
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

1. **Render the ticket:**
   ```bash
   python "${CLAUDE_PLUGIN_ROOT}/scripts/jira_utils.py" <KEY> --print-md
   ```
2. **Screenshots:** download image attachments and READ each one — the error
   often lives only there:
   ```bash
   python "${CLAUDE_PLUGIN_ROOT}/scripts/jira_utils.py" <KEY> --attachments --attachments-ext png,jpg,jpeg,gif --attachments-dir /tmp/defect-review-<KEY>
   ```
   Read every downloaded file with the Read tool.
   Text logs (`.log`, `.txt`) and PDFs: when the manifest shows one at
   ≤ ~200 KB, download it the same way (adjust `--attachments-ext`) and
   read it; note bigger ones from the manifest only.
   Videos and archives (`.zip`, `.7z`, `.tar.*`): NOT viewable — never
   download or unpack; the comment must disclose each one it could not
   examine.
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

- `## Ticket` — the rendered markdown (step 3.1) + one line per screenshot
  finding.
- `## Wiki grounding` — the retrieved pages (titles + the relevant excerpts).
- `## Live duplicate candidates` — the step 3.4 list.
- `## Review state` — `{"question_rounds": <n>, "max_question_rounds": <config>,
  "pending_asks": [...], "mode": "interactive"|"auto"}`.

Tell it the marker string from config. Parse the three output sections:
`### COMMENT (kind: …)`, `### ANALYSIS`, `### STATE`.

**Round-cap rule:** when `question_rounds >= max_question_rounds`, instruct
the brain that kind MUST be `assessment` (verdict with stated assumptions).

## 5. Enforce the contract (mechanical — never skip)

Write the COMMENT section to a temp file, then:

```bash
python "${CLAUDE_PLUGIN_ROOT}/scripts/comment_contract.py" /tmp/defect-review-<KEY>-comment.md --kind <kind> --marker "<marker from config>" --fix-marker
```

Exit 1 → ONE revision pass: re-run the brain with the violations appended
("Revise the comment to fix exactly these violations; change nothing else"),
re-check. Still failing → deliver anyway but append the violations to the
ANALYSIS (never block the pipeline on style), and say so in the run log.

## 6. Deliver

**Interactive:** show the comment and the analysis in conversation. Do not
email, post, or write state. If the user says to send it, follow the
config `mode` exactly as below.

**`--auto --dry-run`:** print per ticket: key, kind, would-`notify`/would-`post`,
the comment text. No delivery, no state writes.

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

**`--auto`, `mode: post`:** post directly, then optional FYI:

```bash
python "${CLAUDE_PLUGIN_ROOT}/scripts/jira_utils.py" <KEY> --post-comment --body-file /tmp/defect-review-<KEY>-comment.md
```

If `also_notify: true`, send the notify email too (same layout, subject
prefix `[defect-review posted]`).

Delivery failed (non-zero exit) → report the error, do NOT write state for
that ticket (it retries next poll), continue with the next ticket, and exit
non-zero at the end so the wrapper flags the run.

## 7. Record state (auto mode only, after successful delivery)

```bash
python -c "
import sys; sys.path.insert(0, '${CLAUDE_PLUGIN_ROOT}/scripts')
import defect_review_state as s
s.record('<KEY>', '<updated from the scan JSON>', <question_rounds from STATE>, <pending_asks from STATE>)
"
```

`mode: post` note: the marker comment now carries the dedupe; state still
records rounds + pending asks.

## 8. Report

End every run with a one-line-per-ticket summary:

```
OLAC-7411  ask (round 2/3)   emailed rehman@…      2 pending asks
OLAC-7423  assessment        posted                dupe of OLAC-7101
```

Server setup (wrapper script, cron, prerequisites, rollout):
`${CLAUDE_PLUGIN_ROOT}/skills/wiki-defect-review/references/server-setup.md`.
