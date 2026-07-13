"""Drift locks for the plugin manifests. marketplace.json sat at 0.14.1
while plugin.json shipped 0.15.x–0.17.0 — the listing showed a stale
version for months. The two files must carry the same version."""
import json
from pathlib import Path

MANIFESTS = Path(__file__).resolve().parent.parent / ".claude-plugin"


def test_marketplace_version_matches_plugin_version():
    plugin = json.loads((MANIFESTS / "plugin.json").read_text(encoding="utf-8"))
    marketplace = json.loads(
        (MANIFESTS / "marketplace.json").read_text(encoding="utf-8"))
    entries = [p for p in marketplace["plugins"] if p["name"] == plugin["name"]]
    assert len(entries) == 1
    assert entries[0]["version"] == plugin["version"], (
        "bump marketplace.json together with plugin.json")
