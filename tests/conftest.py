import os
import sys
import textwrap
import tempfile
from pathlib import Path

# Make scripts/ importable as top-level modules (jira_utils, ingest_state, …).
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))


def pytest_configure(config):
    """Set a fallback WIKI_CONFIG before any test module is collected.

    Several production scripts (ingest_state, jira_utils, lint_wiki) call
    config.project_key() / config.config_dir() at module level. In the plugin
    repo there is no wiki.config.yaml to discover from CWD, so those imports
    would raise FileNotFoundError at collection time.

    We write a minimal CDS2ASV config to a temp file and point $WIKI_CONFIG at
    it. Individual tests that need a different config override $WIKI_CONFIG via
    monkeypatch (config.py does not cache, so the override takes effect
    immediately). The temp dir lives for the whole pytest session and is cleaned
    up automatically on interpreter exit.
    """
    if os.environ.get("WIKI_CONFIG"):
        return  # already set (e.g. by the caller) — do not override

    td = tempfile.mkdtemp(prefix="ts-wiki-test-")
    cfg_path = Path(td) / "wiki.config.yaml"
    cfg_path.write_text(textwrap.dedent(f"""
        project:
          key: CDS2ASV
          name: "Test Services"
          config_dir: {td}/config
        jira:
          base_url: https://agilent.atlassian.net
          jql: |
            project = CDS2ASV AND status = Done
        sources: []
        lint:
          flaggable_nouns: ["Project", "Instruments?", "Results?", "Report", "Cabinet", "Drawer", "Location"]
          brand_nouns: [ASV, CA, QualA]
          era_terms: ['ASV 1\\.0', 'CA era', 'QualA \\d', 'pre-CA', 'pre-QualA']
    """))
    os.environ["WIKI_CONFIG"] = str(cfg_path)
    os.environ.setdefault("STATE_DIR", str(Path(td) / "state"))
