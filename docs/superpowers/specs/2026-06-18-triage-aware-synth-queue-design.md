# Triage-Aware Synth Queue — Design

**Date:** 2026-06-18
**Status:** Approved (pending spec review)

## Problem

The synth phase batches up to `DIGEST_BATCH=12` identities into one Sonnet
subagent regardless of source kind, file size, or business value. This mixes a
1000-line service class with a 5-line constants file and a useless CSS file in
one context, where:

- **Attention dilutes.** With 12 distinct items competing for one agent's
  context, later items get skimmed and real business detail is missed.
- **Noise is synthesized anyway.** Files with no business logic (CSS, lock
  files, boilerplate, a useless doc page) still consume a full synth slot.
- **One size fits none.** A fixed batch of 12 is wrong for both a dense user
  guide (should be solo) and a pile of tiny config files (could batch 15+).

Code and prose currently skip the extract phase entirely
(`ingest_state.py:extract_action` returns `"ready"`), so no judgment is ever
applied before synthesis.

## Goals

1. Drop genuinely worthless files before they reach synth.
2. Give the synthesizer homogeneous, right-sized batches so attention isn't
   diluted.
3. Route the genuinely hard files to a stronger model / solo treatment.
4. Require **zero** new user input; degrade gracefully on existing repos.

## Non-goals

- No change to Jira extraction logic beyond emitting one extra flag it can
  already judge.
- No abstract "synthesis weight" scoring — line count stays a transparent,
  debuggable raw number.
- No replacement of the synth agent's raw-file read; the triage note is a
  focus hint, not a substitute.

## Overview

Introduce a **Haiku triage pass** in the extract phase for every code, prose,
and doc item. Each item is read once by Haiku and tagged:

- **`skip`** → dropped entirely (fast-forwarded through both queues, no wiki
  trace).
- **`keep`** → carried to the synth queue with a **line count**, a
  **`dense`/`routine` flag**, and an **optional one-line note**.

Jira already gets an equivalent judgment in its existing Haiku extract
(`business_relevant:`), so this brings code/prose/doc up to parity. The result:
**every item entering the synth queue has passed exactly one Haiku judgment**
that emits the same `(tier, lines, flag)` triple.

The orchestrator then forms **homogeneous-by-kind, size-bounded batches** and
picks the model from the flag rather than from raw size.

## Detailed design

### 1. Triage pass (Haiku, extract phase)

Runs on code, prose, and doc items. Where it reads from differs by kind, but the
output contract is identical.

| Source     | Triage reads          | Emits                                  |
|------------|-----------------------|----------------------------------------|
| jira       | the ticket (existing Haiku extract) | business-relevant + flag |
| code/prose | the raw file directly  | tier + lines + flag + optional note    |
| doc        | the converted markdown (after `extract_docs.py`) | tier + lines + flag + optional note |

Docs are the highest-variance source (a whole user guide vs. a useless page), so
they get the triage pass too — running *after* the existing mechanical
conversion, on the converted markdown. The marginal cost is one Haiku call per
doc; docs are infrequent and the conversion already happened.

Triage output per kept item:

- `tier`: `skip` | `keep`
- `lines`: integer line count of the item the synthesizer will read (raw file
  for code/prose; converted import for doc)
- `flag`: `dense` | `routine` — business-rule density and how many distinct
  concepts the item introduces. **Not** a function of size.
- `note` (optional): one line telling the synthesizer where the business value
  is. A hint, never a replacement for reading the file.

`skip` items are fast-forwarded: the pipeline calls `extracted` then `synthed`
immediately so they never linger in a queue and leave no wiki trace.

### 2. Queue line format

The synth queue line extends from `<identity>` to:

```
<lines>\t<flag>\t<identity>
```

- **Identity is always last**, tab-separated, so `identity = line.split('\t')[-1]`
  is backward-compatible everywhere in `queues.py`.
- A bare `<identity>` line (older code, manual entry) parses as "no metadata" →
  unknown lines, `routine` flag → today's behavior.
- `queues.py` gains a small parse helper returning `(lines | None, flag | None,
  identity)` and `next-synth` emits the full line. `extracted` optionally
  accepts the metadata to embed when moving an item to `.synth`.

### 3. Orchestrator batching

Two independent decisions, driven by two different signals:

- **Batch size** keys off `lines` (the attention story — keep distinct-item
  count per context manageable).
- **Model** keys off `flag` (`dense` → Opus solo), *not* raw size, because size
  is a poor proxy for reconciliation difficulty.

**Homogeneous-by-kind batches.** The synth queue is already walked in source
order (`jira → raw → repos`), so consecutive items are mostly the same kind. The
orchestrator **never lets a batch cross a kind boundary**: it pulls a contiguous
run of one kind and sizes it by that kind's cutoffs. This directly removes the
"mixing all kinds confuses the agent" problem and makes per-kind cutoffs
meaningful (the whole batch shares one yardstick).

**Per-kind cutoffs.** Line count means something different per kind (dense Jira
prose vs. boilerplate-inflated code), so cutoffs differ by kind. Starting
defaults (tunable — see §4):

| Kind       | small-batch (lines) | solo cutoff (lines) |
|------------|---------------------|---------------------|
| jira       | < 150               | 400+                |
| doc        | < 250               | 700+                |
| code/prose | < 400               | 1500+               |

Within a kind, routing roughly:

| Item                        | Batch        | Model  |
|-----------------------------|--------------|--------|
| no metadata (unknown lines) | 12 (today)   | Sonnet |
| under small-batch cutoff    | up to 15     | Sonnet |
| small-batch .. solo cutoff  | up to 3–8    | Sonnet |
| at/above solo cutoff        | solo         | Sonnet |
| flagged `dense` (any size)  | solo         | Opus   |

The serialization invariant is unchanged: **exactly one synth subagent in
flight, ever.** Only batch composition and model choice change.

### 4. Configuration & defaults

- Cutoffs and batch sizes ship as **defaults in `config.py`**, alongside
  `DIGEST_BATCH`.
- `config.py` reads an **optional** `synth_tuning:` block from
  `wiki.config.yaml`; any absent key falls back to the code default.
- **The user never has to provide anything.** Defaults work out of the box.
- `wiki-init` writes a **commented-out** `synth_tuning:` block into new configs —
  inert, but documents the knobs in-place with one-line comments. Existing repos
  don't get it unless re-initialized, and don't need it.
- Knob names are self-describing (`code_solo_lines`, `jira_small_batch`) rather
  than opaque numbers.

### 5. Synth prompt changes

- The note, when present, is passed to the synth subagent as a focus hint.
- The synth agent **always reads the raw file** (the note never replaces the
  read).
- `dense` items routed to Opus use the same `synth-prompt.md`; only the model
  differs.

## Migration

Migration does not exist as a step — absence equals defaults, everywhere:

- **Config:** existing `wiki.config.yaml` has no `synth_tuning:` → defaults used.
- **Queue:** existing bare `<identity>` lines parse as no-metadata → today's
  `DIGEST_BATCH=12` Sonnet behavior.
- **Extract action:** code/prose currently `ready`; once triage lands they route
  through Haiku first. In-flight items already in `.synth` from a prior run
  simply lack metadata and fall back to default batching.

Both the config and the queue format degrade to current behavior by
construction. No script, no rewrite.

## Affected components

- `scripts/ingest_state.py` — `extract_action` routes code/prose/doc through a
  triage action instead of `ready`; new `classify` handling as needed.
- `scripts/queues.py` — metadata-aware line parse/emit; `extracted` carries
  metadata; `next-synth` emits full line.
- `scripts/config.py` — `synth_tuning:` defaults + optional override read.
- `skills/wiki-ingest/SKILL.md` — extract phase gains the triage step;
  orchestrator batching logic (homogeneous-by-kind, per-kind cutoffs,
  flag-driven model).
- `skills/wiki-ingest/synth-prompt.md` — accept and use the optional note.
- New triage prompt (Haiku) under `skills/wiki-ingest/`.
- `skills/wiki-init/` — commented `synth_tuning:` block in scaffolded config.

## Open questions

None blocking. Threshold numbers are starting guesses, expected to be tuned
empirically after observing real synth output — which is exactly why they're
config-overridable.
