"""defect_review_state.py — per-ticket review state for /wiki-defect-review.

One JSON file defect-review.json (state dir, sibling of jira-cursor.json) maps
ticket key → entry:

  { "OLAC-7411": { "emailed_for_updated": "2026-07-04T09:12:00.000+0000",
                   "question_rounds": 1,
                   "pending_asks": ["OS + CDS client version"],
                   "last_human_comment": "2026-07-04T08:55:00.000+0000",
                   "disposition_code": "accept-for-fix",
                   "disposition": "Accept for a fix" } }

Semantics: `emailed_for_updated` is the ticket's `updated` value
when the last draft email went out — the repeat-email guard (same value next
poll → stay silent). `question_rounds` counts clarifying-question rounds
toward the cap. `pending_asks` holds deferred asks (short summaries) that the
next round re-evaluates, never replays verbatim. `last_human_comment` is the
timestamp of the newest non-bot comment the last review covered (the post-mode
repeat guard): a recorded null means "reviewed, no human comments yet", while
a MISSING field (legacy entry) merges to the sentinel "unknown" and forces one
migration re-review — get() must never conflate the two. `disposition_code` /
`disposition` are the last delivered assessment's proposed disposition
(machine code + short display phrase); a null code means no assessment has
been delivered. Machine-local and untracked; loss is benign — worst case one
duplicate email or one redundant in-place edit per pending ticket.
"""

import json
from pathlib import Path

import config

_FILENAME = "defect-review.json"
_DEFAULTS = {"emailed_for_updated": None, "question_rounds": 0,
             "pending_asks": [], "last_human_comment": "unknown",
             "disposition_code": None, "disposition": None}


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
           pending_asks: list, last_human_comment: str | None = None,
           disposition_code: str | None = None,
           disposition: str | None = None) -> None:
    """Overwrite the entry for `key` (persisted). All fields are written
    explicitly, so a recorded entry never merges to the 'unknown' sentinel."""
    data = _load()
    data[key] = {
        "emailed_for_updated": emailed_for_updated,
        "question_rounds": question_rounds,
        "pending_asks": list(pending_asks),
        "last_human_comment": last_human_comment,
        "disposition_code": disposition_code,
        "disposition": disposition,
    }
    _save(data)


def prune(keep: set) -> None:
    """Drop entries for tickets no longer in the candidate set."""
    data = _load()
    pruned = {k: v for k, v in data.items() if k in keep}
    if pruned != data:
        _save(pruned)


if __name__ == "__main__":
    # CLI so headless runs can allowlist per-script commands instead of
    # arbitrary `python -c` code.
    import argparse

    parser = argparse.ArgumentParser(description="Per-ticket review state.")
    sub = parser.add_subparsers(dest="cmd", required=True)
    p_rec = sub.add_parser("record", help="Overwrite the entry for KEY.")
    p_rec.add_argument("key")
    p_rec.add_argument("--updated", default=None,
                       help="Ticket `updated` value the delivery covered.")
    p_rec.add_argument("--rounds", type=int, default=0,
                       help="Clarifying-question rounds so far.")
    p_rec.add_argument("--pending-asks", default="[]",
                       help="JSON list of deferred asks.")
    p_rec.add_argument("--last-human-comment", default=None,
                       help="Timestamp of the newest non-bot comment this "
                            "review covered (omit = none existed).")
    p_rec.add_argument("--disposition-code", default=None,
                       help="Machine code of the delivered assessment's "
                            "proposed disposition (omit when kind=ask).")
    p_rec.add_argument("--disposition", default=None,
                       help="Short display phrase of the proposed disposition.")
    p_get = sub.add_parser("get", help="Print the entry for KEY (defaults merged).")
    p_get.add_argument("key")
    args = parser.parse_args()
    if args.cmd == "record":
        record(args.key, args.updated, args.rounds, json.loads(args.pending_asks),
               last_human_comment=args.last_human_comment,
               disposition_code=args.disposition_code,
               disposition=args.disposition)
    else:
        print(json.dumps(get(args.key)))
