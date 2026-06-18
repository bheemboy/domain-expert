"""jira_cursor.py — the Jira detection-cursor store.

One JSON file jira-cursor.json maps project key → last-detected date:
  { "PROJ": "2026-06-14" }

Jira is keyed per project, so multiple Jira projects track independent cursors.
This is the only non-queue runtime state; it lives alongside the per-source work
queues in the state dir (config_dir/state/). Git detection is stateless (the repo's
own HEAD is the watermark — see check_for_changes.py), so no git state lives here.
"""

import json
from pathlib import Path

import config

_FILENAME = "jira-cursor.json"


def _path() -> Path:
    return config.state_dir() / _FILENAME


def _load() -> dict:
    """Project-key → date map. Pure: never writes. Missing/corrupt → empty."""
    p = _path()
    if not p.is_file():
        return {}
    try:
        return json.loads(p.read_text(encoding="utf-8")) or {}
    except json.JSONDecodeError:
        return {}


def get(project_key: str) -> str | None:
    return _load().get(project_key)


def advance(project_key: str, date_str: str) -> None:
    """Set the detection cursor for a project to date_str (persisted)."""
    data = _load()
    data[project_key] = date_str
    p = _path()
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n", encoding="utf-8")
