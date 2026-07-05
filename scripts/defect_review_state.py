"""defect_review_state.py — per-ticket review state for /wiki-defect-review.

One JSON file defect-review.json (state dir, sibling of jira-cursor.json) maps
ticket key → entry:

  { "OLAC-7411": { "emailed_for_updated": "2026-07-04T09:12:00.000+0000",
                   "question_rounds": 1,
                   "pending_asks": ["OS + CDS client version"] } }

Semantics: `emailed_for_updated` is the ticket's `updated` value
when the last draft email went out — the repeat-email guard (same value next
poll → stay silent). `question_rounds` counts clarifying-question rounds
toward the cap. `pending_asks` holds deferred asks (short summaries) that the
next round re-evaluates, never replays verbatim. Machine-local and untracked;
loss is benign — worst case one duplicate email per pending ticket.
"""

import json
from pathlib import Path

import config

_FILENAME = "defect-review.json"
_DEFAULTS = {"emailed_for_updated": None, "question_rounds": 0, "pending_asks": []}


def _path() -> Path:
    return config.state_dir() / _FILENAME


def _load() -> dict:
    """Key → entry map. Pure: never writes. Missing/corrupt → empty."""
    p = _path()
    if not p.is_file():
        return {}
    try:
        return json.loads(p.read_text(encoding="utf-8")) or {}
    except json.JSONDecodeError:
        return {}


def _save(data: dict) -> None:
    p = _path()
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(data, indent=2, sort_keys=True, ensure_ascii=False) + "\n",
                 encoding="utf-8")


def get(key: str) -> dict:
    """Entry for `key` with defaults merged; unknown key → all defaults."""
    entry = dict(_DEFAULTS)
    entry.update(_load().get(key) or {})
    return entry


def record(key: str, emailed_for_updated: str | None, question_rounds: int,
           pending_asks: list) -> None:
    """Overwrite the entry for `key` (persisted)."""
    data = _load()
    data[key] = {
        "emailed_for_updated": emailed_for_updated,
        "question_rounds": question_rounds,
        "pending_asks": list(pending_asks),
    }
    _save(data)


def prune(keep: set) -> None:
    """Drop entries for tickets no longer in the candidate set."""
    data = _load()
    pruned = {k: v for k, v in data.items() if k in keep}
    if pruned != data:
        _save(pruned)
