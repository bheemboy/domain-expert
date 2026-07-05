"""defect_review_scan.py — deterministic candidate scan for /wiki-defect-review --auto.

Fetches this wiki's candidate JQL (config `defect_review.candidate_jql`,
wrapped with the project key), applies the three no-LLM filters, prunes stale
state, and prints one JSON object per reviewable ticket to stdout:

  {"key": ..., "summary": ..., "updated": ..., "question_rounds": n, "pending_asks": [...]}

Skip reasons go to stderr, one line each:
  cool-down      — activity within the last 10 minutes (still settling)
  bot-spoke-last — latest comment starts with the marker (waiting on submitter)
  email-pending  — draft already emailed for this exact `updated`

The 10-minute cool-down is enforced HERE, in code, on the fetched `updated`
field — not in the JQL. One cool-down-free fetch serves both candidate
selection and correct pruning (a JQL cool-down would hide still-settling
tickets from the fetch and prune their state by mistake). The knob stays
code-owned and independent of the poll cadence.
"""

import argparse
import json
import sys
from datetime import datetime, timedelta, timezone

import config
import defect_review_state as state
import jira_utils

COOLDOWN_MINUTES = 10


def candidate_jql() -> str:
    cfg = config.defect_review_config()
    base = (cfg.get("candidate_jql") or "").strip()
    if not base:
        raise SystemExit("defect_review.candidate_jql is not set in wiki.config.yaml")
    return f"project = {config.project_key()} AND ({base})"


def _parse_updated(iso: str) -> datetime:
    return datetime.strptime(iso, "%Y-%m-%dT%H:%M:%S.%f%z")


def in_cooldown(updated_iso: str, now: datetime) -> bool:
    return _parse_updated(updated_iso) > now - timedelta(minutes=COOLDOWN_MINUTES)


def last_comment_is_marked(issue: dict, marker: str) -> bool:
    comments = ((issue.get("fields") or {}).get("comment") or {}).get("comments", [])
    if not comments:
        return False
    body = jira_utils.adf_to_md(comments[-1].get("body"))
    return body.lstrip().startswith(marker)


def skip_reason(issue: dict, marker: str, entry: dict, now: datetime):
    """None = reviewable; otherwise the skip reason string."""
    updated = (issue.get("fields") or {}).get("updated") or ""
    if updated and in_cooldown(updated, now):
        return "cool-down"
    if last_comment_is_marked(issue, marker):
        return "bot-spoke-last"
    if updated and entry.get("emailed_for_updated") == updated:
        return "email-pending"
    return None


def main():
    ap = argparse.ArgumentParser(
        description="Print reviewable defect candidates as JSON lines (stdout); skips to stderr.")
    ap.add_argument("--no-prune", action="store_true",
                    help="Inspect without pruning state entries for departed tickets.")
    args = ap.parse_args()

    cfg = config.defect_review_config()
    if not cfg["enabled"]:
        print("defect_review.enabled is false — nothing to scan.", file=sys.stderr)
        return
    jira_utils.require_credentials()

    issues = jira_utils.fetch_issues(candidate_jql())
    if not args.no_prune:
        state.prune({i.get("key") for i in issues})

    now = datetime.now(timezone.utc)
    for issue in issues:
        key = issue.get("key", "")
        entry = state.get(key)
        reason = skip_reason(issue, cfg["marker"], entry, now)
        if reason:
            print(f"skip {key}: {reason}", file=sys.stderr)
            continue
        f = issue.get("fields") or {}
        print(json.dumps({
            "key": key,
            "summary": f.get("summary", ""),
            "updated": f.get("updated", ""),
            "question_rounds": entry.get("question_rounds", 0),
            "pending_asks": entry.get("pending_asks", []),
        }, ensure_ascii=False))


if __name__ == "__main__":
    main()
