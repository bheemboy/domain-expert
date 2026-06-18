# tests/test_queues.py
import os
import subprocess
import textwrap
from pathlib import Path

import pytest

import config


def _cfg(tmp_path, monkeypatch, repos=()):
    cfg = tmp_path / "wiki.config.yaml"
    repo_lines = "".join(f"\n        - {r}" for r in repos)  # 8-space indent = dedent baseline
    cfg.write_text(textwrap.dedent(f"""
        project:
          key: TESTPROJ
          name: "T"
          config_dir: {tmp_path}/state
        jira:
          base_url: https://example.atlassian.net
          jql: |
            project = TESTPROJ
        sources:{repo_lines}
    """))
    monkeypatch.setenv("WIKI_CONFIG", str(cfg))


def test_queue_paths(tmp_path, monkeypatch):
    _cfg(tmp_path, monkeypatch)
    monkeypatch.setenv("STATE_DIR", str(tmp_path / "state"))
    import queues
    assert queues.extract_file("jira").name == "jira.extract"
    assert queues.synth_file("jira").name == "jira.synth"


def test_membership_and_read(tmp_path, monkeypatch):
    _cfg(tmp_path, monkeypatch)
    monkeypatch.setenv("STATE_DIR", str(tmp_path / "state"))
    import queues
    assert queues.read(queues.extract_file("jira")) == []
    assert not queues.in_extract("jira", "TESTPROJ-1")
    queues._write(queues.extract_file("jira"), ["TESTPROJ-1", "TESTPROJ-2"])
    assert queues.read(queues.extract_file("jira")) == ["TESTPROJ-1", "TESTPROJ-2"]
    assert queues.in_extract("jira", "TESTPROJ-1")
    assert not queues.in_synth("jira", "TESTPROJ-1")


def _q(tmp_path, monkeypatch, repos=()):
    _cfg(tmp_path, monkeypatch, repos)
    monkeypatch.setenv("STATE_DIR", str(tmp_path / "state"))
    import queues
    return queues


def test_enqueue_appends_when_absent(tmp_path, monkeypatch):
    q = _q(tmp_path, monkeypatch)
    q.enqueue("jira", "TESTPROJ-1")
    q.enqueue("jira", "TESTPROJ-2")
    assert q.read(q.extract_file("jira")) == ["TESTPROJ-1", "TESTPROJ-2"]


def test_enqueue_idempotent_when_already_in_extract(tmp_path, monkeypatch):
    q = _q(tmp_path, monkeypatch)
    q.enqueue("jira", "TESTPROJ-1")
    q.enqueue("jira", "TESTPROJ-1")
    assert q.read(q.extract_file("jira")) == ["TESTPROJ-1"]


def test_enqueue_bumps_back_from_synth(tmp_path, monkeypatch):
    q = _q(tmp_path, monkeypatch)
    q._write(q.synth_file("jira"), ["TESTPROJ-1"])
    q.enqueue("jira", "TESTPROJ-1")            # changed again -> needs re-extract
    assert q.read(q.synth_file("jira")) == []
    assert q.read(q.extract_file("jira")) == ["TESTPROJ-1"]


def test_move_to_synth(tmp_path, monkeypatch):
    q = _q(tmp_path, monkeypatch)
    q.enqueue("jira", "TESTPROJ-1")
    q.move_to_synth("jira", "TESTPROJ-1")
    assert q.read(q.extract_file("jira")) == []
    assert q.read(q.synth_file("jira")) == ["TESTPROJ-1"]


def test_remove_synth(tmp_path, monkeypatch):
    q = _q(tmp_path, monkeypatch)
    q._write(q.synth_file("jira"), ["TESTPROJ-1", "TESTPROJ-2"])
    q._remove_synth("jira", "TESTPROJ-1")
    assert q.read(q.synth_file("jira")) == ["TESTPROJ-2"]


def test_source_empty(tmp_path, monkeypatch):
    q = _q(tmp_path, monkeypatch)
    assert q.source_empty("jira")
    q.enqueue("jira", "TESTPROJ-1")
    assert not q.source_empty("jira")


def test_next_extract_priority_order_and_budget(tmp_path, monkeypatch):
    repo = tmp_path / "asv"
    repo.mkdir()
    q = _q(tmp_path, monkeypatch, [str(repo)])
    q._write(q.extract_file("jira"), ["TESTPROJ-1", "TESTPROJ-2"])
    q._write(q.extract_file("raw"), ["/abs/raw/a.md"])
    q._write(q.extract_file("asv"), ["/abs/asv/x.py"])
    # priority: jira, raw, asv. Budget 3 -> first 3 across that order.
    assert q.next_extract(3) == [
        ("jira", "TESTPROJ-1"),
        ("jira", "TESTPROJ-2"),
        ("raw", "/abs/raw/a.md"),
    ]


def test_next_synth_priority_order(tmp_path, monkeypatch):
    repo = tmp_path / "asv"
    repo.mkdir()
    q = _q(tmp_path, monkeypatch, [str(repo)])
    q._write(q.synth_file("raw"), ["/abs/raw/a.md"])
    q._write(q.synth_file("jira"), ["TESTPROJ-9"])
    assert q.next_synth(10) == [("jira", "TESTPROJ-9"), ("raw", "/abs/raw/a.md")]


def test_next_extract_empty(tmp_path, monkeypatch):
    q = _q(tmp_path, monkeypatch)
    assert q.next_extract(5) == []


def test_synthed_removes_from_synth_queue(tmp_path, monkeypatch):
    q = _q(tmp_path, monkeypatch)
    q._write(q.synth_file("jira"), ["TESTPROJ-1", "TESTPROJ-2"])
    q.synthed("jira", "TESTPROJ-1")
    assert q.read(q.synth_file("jira")) == ["TESTPROJ-2"]


def test_synthed_last_item_empties_source(tmp_path, monkeypatch):
    q = _q(tmp_path, monkeypatch)
    q._write(q.synth_file("jira"), ["TESTPROJ-1"])
    q.synthed("jira", "TESTPROJ-1")
    assert q.source_empty("jira")


def _cli(tmp_path, *args):
    return subprocess.run(
        ["python", str(Path(config.__file__).resolve().parent / "queues.py"), *args],
        capture_output=True, text=True,
        env={**os.environ,
             "WIKI_CONFIG": str(tmp_path / "wiki.config.yaml"),
             "STATE_DIR": str(tmp_path / "state")},
    )


def test_cli_next_extract_prints_tab_separated(tmp_path, monkeypatch):
    q = _q(tmp_path, monkeypatch)
    q.enqueue("jira", "TESTPROJ-1")
    r = _cli(tmp_path, "next-extract", "5")
    assert r.returncode == 0, r.stderr
    assert r.stdout.splitlines() == ["jira\tTESTPROJ-1"]


def test_cli_status(tmp_path, monkeypatch):
    q = _q(tmp_path, monkeypatch)
    q.enqueue("jira", "TESTPROJ-1")
    q._write(q.synth_file("jira"), ["TESTPROJ-2"])
    r = _cli(tmp_path, "status")
    assert r.returncode == 0, r.stderr
    assert "pending_extract=1" in r.stdout
    assert "pending_synth=1" in r.stdout
