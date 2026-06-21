# Wiki lint tiers: delta + full, one engine — design

Date: 2026-06-21
Status: proposed (for review)

## 1. Problem

The wiki lint has two tiers today:

- **Mechanical** (`scripts/lint_wiki.py`) — deterministic, exhaustive, cheap. Sound.
- **Semantic** (one Opus subagent via the canonical `lint-prompt.md`) — run in two
  contexts that do the *same* whole-wiki pass: the `/wiki-ingest` synth gate (every 20
  synths + once at end) and standalone `/wiki-lint`.

The semantic tier has one structural flaw. Real wikis built with this plugin are already
large enough that a single subagent cannot read them whole:

| wiki | content pages (excl. `log.md`) | content lines |
|---|---|---|
| ts-wiki | 58 | 16,827 |
| cid-wiki | 61 | 11,774 |

~12–17k lines is ~250–500k tokens. So the "whole-wiki" semantic pass does **not** read
the whole wiki — it samples summary pages + retrieves. It *pretends* to cover everything
while actually spot-checking. The every-20 cadence is a cost hack around that expense, and
it delays catching drift by up to 20 sources.

This matches the failure mode Karpathy's pattern warns about ("confident-but-stale
memory") and the scaling answer his thread converges on: **lint changed nodes + their
neighbors on ingest (high frequency); run a full whole-wiki audit rarely (on demand)**.
Confirmed against the gist and its comment thread
(<https://gist.github.com/karpathy/442a6bf555914893e9891c11519de94f>); see §6.

## 2. Goals / non-goals

**Goals**
- Replace "whole-wiki sampled" semantic lint with **exhaustive** semantic lint over a
  bounded page set, so the lint never pretends to have read what it didn't.
- Two semantic scopes sharing **one** engine and **one** prompt:
  - **delta** — pages changed since the last lint + their 1-hop neighbors.
  - **full** — the whole wiki, sharded so every page is actually read.
- Derive the "changed since last lint" set from `log.md` (the existing chronological
  record) — no new state file, no git plumbing.
- Keep the mechanical tier and the surface-don't-auto-fix-judgment policy unchanged.

**Non-goals**
- No new skill. `wiki-deeplint` is folded into `/wiki-lint --full`.
- No change to the 7 semantic passes themselves (they are scope-independent).
- No handling of out-of-pipeline hand-edits. Per the maintained-wiki model (Karpathy:
  the LLM writes everything; humans curate/question), every wiki change flows through
  synth, so the `synth | … | pages:` log lines are a complete change record.

## 3. Design

### 3.1 One engine, two scopes

A single semantic auditor (the canonical `lint-prompt.md` passes) parameterized by a
**page set** and a **scope label**. The mechanical `lint_wiki.py` runs first in every
mode (cheap, exhaustive, structural).

| Mode | Invocation | Page set | Sharded? | Log line |
|---|---|---|---|---|
| mechanical | `/wiki-lint mechanical` | all (structural only) | n/a | none (existing) |
| **delta** | `/wiki-lint` (default) **and** synth gate | changed-since-last-lint + 1-hop neighbors | only if set is large | `lint` |
| **full** | `/wiki-lint --full` | whole wiki | yes | `lint --full` |

Delta is **one operation triggered two ways** — automatically by synth (every N batches +
once at end of run) and manually. Both advance the watermark, because both genuinely audit
their full scope. After a clean ingest run, a manual `/wiki-lint` finds nothing new — the
signal that the wiki is current.

`--full` is the rare backstop for *latent* drift: contradictions between pages that have
not changed since the last lint, which delta never revisits by construction.

### 3.2 The shared, parameterized prompt

There is exactly one prompt body (the 7 passes + auto-fix rules + return contract). It is
**not** duplicated per mode — duplication is the drift bug we just removed (the ingest copy
had silently lost pass 7). The prompt gains a `## Scope` slot the caller fills, mirroring
the existing `<paste lint_wiki.py output here>` slot:

```
## Scope
<one of>
  delta:      Audit ONLY these pages + the listed 1-hop neighbors: <page list>.
              Append a `lint | <auto|manual>` line to log.md.
  full:       You are shard <i> of <n>. Audit ONLY these pages: <shard list>.
              (A synthesis pass reconciles across shards; see below.)
              The synthesis agent appends one `lint --full | manual` line to log.md.
```

Passes that are inherently global (summary-page consistency; concept-split) are evaluated
*within the provided scope* in delta mode: check whether the changed pages affect the
summary pages, not a full summary-vs-everything reconciliation. In full mode they run
across shards via the synthesis pass.

**Prompt location:** move the canonical prompt from `skills/wiki-lint/lint-prompt.md` to a
neutral `prompts/lint-prompt.md` at the plugin root, since it is now a first-class engine
shared by two skills rather than the gate borrowing wiki-lint's behavior. Both skills
reference `${CLAUDE_PLUGIN_ROOT}/prompts/lint-prompt.md`.

### 3.3 Scope resolution is deterministic (Python), not LLM judgment

The mechanical/deterministic half computes the page set; the subagent only does the
semantic audit. This matches the existing split (deterministic tier vs model tier).

Extend `scripts/lint_wiki.py` (or a sibling helper) with a non-LLM **scope resolver**:

- **changed-since-last-lint**: read `wiki/log.md`; find the last line matching
  `^## \[[^]]*\] lint` (this matches `lint` and `lint --full`, but **not** `synth-lint`
  were it ever used — see §3.4); union the `pages:` lists from every `synth` line *after*
  it (by append position, **not** date — see Risks). Output = changed page slugs.
- **1-hop neighbors**: from the wikilink graph the script already builds, expand the
  changed set with inbound + outbound `[[links]]` (one hop). Output = delta page set.
- **shard partition** (full mode): partition all content pages folder-aware with a line
  budget (default ~3,500 lines/shard; the dominant `concepts/` folder splits, small
  folders merge). Reuse the raw-line-count currency already used by `synth_tuning`.

The skill calls the resolver, passes the resulting page set into the prompt's Scope slot,
spawns the subagent(s), and on completion appends the `lint` log line.

### 3.4 Watermark and log vocabulary

`log.md` is the watermark — its last deliberate `lint` line. No `state/` file, no git SHA.
This keeps a single chronological source of truth, faithful to the pattern.

Log lines (schema §6):

```
## [date] lint | auto   | scope: 14 pages since last lint + neighbors | <findings>
## [date] lint | manual | scope: 23 pages since last lint + neighbors | <findings>
## [date] lint --full | manual | scope: 59 pages, 5 shards | <findings>
```

All three match `^## \[…\] lint`, so all three advance the watermark. The `auto|manual`
field is **traceability only** (which lints were part of an ingest run vs human-invoked);
it does not affect the watermark. A distinct `synth-lint` prefix is **not** needed: because
synth runs the full delta (not a narrow per-batch lint), its lint legitimately covers
everything since the last lint and so should advance the watermark like any other.

### 3.5 Cadence

- **During ingest:** synth runs delta every N synth batches (default N=20, matching
  today's gate) + once at end of run. Each delta is naturally bounded — it covers only the
  batches since the previous lint advanced the watermark. If a delta is ever large (huge
  backlog ingested without an intervening lint), it shards like full.
- **Manual:** `/wiki-lint` (delta) any time; `/wiki-lint --full` rarely (before relying on
  the wiki, before a release, periodically).

## 4. Changes by file

- `prompts/lint-prompt.md` *(moved from `skills/wiki-lint/`)* — add the `## Scope` slot;
  note in-scope evaluation of global passes; full-mode shard + synthesis instructions.
- `scripts/lint_wiki.py` (or sibling helper) — add the deterministic scope resolver:
  changed-since-last-lint (log parse), 1-hop neighbor expansion, full-mode shard
  partition. Pure stdlib, unit-tested.
- `skills/wiki-lint/SKILL.md` — default = delta; add `--full`; keep `mechanical`; describe
  scope resolution, sharding + synthesis for full, and the `lint`/`lint --full` log lines.
- `skills/wiki-ingest/SKILL.md` — replace the every-20 whole-wiki gate with the delta lint
  (every N + end of run), writing `lint | auto`. Reference the moved prompt path.
- `schema/CLAUDE.md.tmpl` — §5 lint policy (delta vs full, scope, log-as-watermark); §6
  log vocabulary (`lint | auto|manual`, `lint --full`).
- `README.md` — command table: revise the `/wiki-lint` row (now **delta** by default, not
  "full health check"), add a `/wiki-lint --full` row (exhaustive whole-wiki audit, run
  rarely), and keep `/wiki-lint mechanical`. Update the ingest/lint description so the
  every-20 whole-wiki gate reads as the per-run delta gate, and adjust the qmd-refresh note
  (line ~67) if its wording implies whole-wiki lint.
- `.claude-plugin/plugin.json` and `marketplace.json` — version bump (kept in sync).
- `tests/` — cover the scope resolver (log parse picks last `lint` by position not date;
  neighbor expansion; shard partition by line budget).

## 5. Risks / mitigations

- **Log date disorder.** `cid-wiki/log.md` has non-monotonic dates (06-21 lines after
  06-22). The LLM sometimes writes wrong dates. → Key the watermark on **append position**
  (last matching line in file order), never on the date string. The log stays reliably
  append-ordered because synth is the single writer.
- **Synth must log accurate `pages:` lines.** The delta scope trusts this. → Not a new
  assumption; the system already trusts synth to maintain the wiki and log correctly. The
  mechanical tier (orphans, index drift) still catches many structural slips regardless.
- **Neighbor horizon too shallow.** A change could create a contradiction 2 hops away. →
  1-hop is the documented default (matches the thread's "immediate neighbors"); `--full`
  is the periodic catch-all for anything the horizon misses.
- **Large delta after a long un-linted backlog.** → Delta shards using the same partition
  logic as full; cadence (every N) keeps normal deltas small.

## 6. Alignment check (Karpathy)

Confirmed against the gist and thread:
- High-frequency scoped lint of changed pages + immediate neighbors on ingest. ✓ (delta)
- Rare whole-wiki audit, on demand / periodic. ✓ (`--full`)
- `log.md` as the chronological record used to track what changed. ✓ (watermark)
- Findings surfaced, not auto-resolved for judgment calls. ✓ (unchanged policy)

## 7. Decisions resolved (for the record)

- One skill with a flag, not a separate `wiki-deeplint`.
- One shared parameterized prompt, not a per-mode copy.
- Delta = synth-triggered **and** manual (same operation); both advance the watermark.
- No distinct `synth-lint` prefix; `auto|manual` annotation for traceability only.
- Watermark from `log.md` append position; no git cursor, no new state file.
- 1-hop neighbor horizon; full audit as the latent-drift backstop.
