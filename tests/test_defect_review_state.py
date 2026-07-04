import json

import defect_review_state as state


def _isolate(tmp_path, monkeypatch):
    monkeypatch.setenv("STATE_DIR", str(tmp_path / "state"))


def test_get_unknown_key_returns_defaults(tmp_path, monkeypatch):
    _isolate(tmp_path, monkeypatch)
    entry = state.get("OLAC-1")
    assert entry == {"emailed_for_updated": None, "question_rounds": 0, "pending_asks": []}


def test_record_then_get_roundtrip(tmp_path, monkeypatch):
    _isolate(tmp_path, monkeypatch)
    state.record("OLAC-7411", "2026-07-04T09:12:00.000+0000", 1,
                 ["OS + CDS client version"])
    entry = state.get("OLAC-7411")
    assert entry["emailed_for_updated"] == "2026-07-04T09:12:00.000+0000"
    assert entry["question_rounds"] == 1
    assert entry["pending_asks"] == ["OS + CDS client version"]


def test_record_overwrites(tmp_path, monkeypatch):
    _isolate(tmp_path, monkeypatch)
    state.record("OLAC-1", "t1", 1, ["a"])
    state.record("OLAC-1", "t2", 2, [])
    entry = state.get("OLAC-1")
    assert entry["emailed_for_updated"] == "t2"
    assert entry["question_rounds"] == 2
    assert entry["pending_asks"] == []


def test_prune_keeps_only_listed_keys(tmp_path, monkeypatch):
    _isolate(tmp_path, monkeypatch)
    state.record("OLAC-1", "t1", 0, [])
    state.record("OLAC-2", "t2", 0, [])
    state.prune({"OLAC-2"})
    assert state.get("OLAC-1")["emailed_for_updated"] is None
    assert state.get("OLAC-2")["emailed_for_updated"] == "t2"


def test_corrupt_file_treated_as_empty(tmp_path, monkeypatch):
    _isolate(tmp_path, monkeypatch)
    state.record("OLAC-1", "t1", 0, [])
    state._path().write_text("{not json", encoding="utf-8")
    assert state.get("OLAC-1")["emailed_for_updated"] is None
