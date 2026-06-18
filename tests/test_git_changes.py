import subprocess
from pathlib import Path

import pytest

import git_changes


def _run(repo, *args):
    subprocess.run(["git", "-C", str(repo), *args], check=True,
                   capture_output=True, text=True)


def _init_repo(tmp_path, name="repo") -> Path:
    repo = tmp_path / name
    repo.mkdir()
    _run(repo, "init", "-q")
    _run(repo, "config", "user.email", "t@t")
    _run(repo, "config", "user.name", "t")
    return repo


def _commit(repo, name, content) -> str:
    (repo / name).write_text(content)
    _run(repo, "add", name)
    _run(repo, "commit", "-q", "-m", f"touch {name}")
    out = subprocess.run(["git", "-C", str(repo), "rev-parse", "HEAD"],
                         capture_output=True, text=True).stdout.strip()
    return out


def _clone(origin: Path, work: Path) -> None:
    subprocess.run(["git", "clone", "-q", str(origin), str(work)],
                   check=True, capture_output=True, text=True)
    _run(work, "config", "user.email", "t@t")
    _run(work, "config", "user.name", "t")


def test_head_sha(tmp_path):
    repo = _init_repo(tmp_path)
    sha = _commit(repo, "a.txt", "1")
    assert git_changes.head_sha(repo) == sha


def test_changed_files_between_commits(tmp_path):
    repo = _init_repo(tmp_path)
    first = _commit(repo, "a.txt", "1")
    _commit(repo, "b.txt", "2")
    assert git_changes.changed_files(repo, first) == ["b.txt"]


def test_changed_files_subpath_filter(tmp_path):
    repo = _init_repo(tmp_path)
    (repo / "raw").mkdir()
    first = _commit(repo, "raw/keep.txt", "x")
    (repo / "raw" / "doc.txt").write_text("y")
    (repo / "code.py").write_text("z")
    _run(repo, "add", "-A")
    _run(repo, "commit", "-q", "-m", "two files")
    assert git_changes.changed_files(repo, first, subpath="raw") == ["raw/doc.txt"]


def test_diff_text_contains_changed_path(tmp_path):
    repo = _init_repo(tmp_path)
    first = _commit(repo, "a.txt", "1")
    _commit(repo, "b.txt", "2")
    assert "b.txt" in git_changes.diff_text(repo, first)


def test_fetch_pull_ff_advances_head_and_reports_changes(tmp_path):
    origin = _init_repo(tmp_path, "origin")
    _commit(origin, "a.txt", "1")
    work = tmp_path / "work"
    _clone(origin, work)

    _commit(origin, "b.txt", "2")            # new upstream commit

    before = git_changes.head_sha(work)
    git_changes.fetch(work)
    git_changes.pull_ff(work)                 # HEAD advances to upstream tip

    assert git_changes.head_sha(work) != before
    assert git_changes.changed_files(work, before) == ["b.txt"]


def test_incoming_files_previews_without_pull(tmp_path):
    origin = _init_repo(tmp_path, "origin")
    _commit(origin, "a.txt", "1")
    work = tmp_path / "work"
    _clone(origin, work)
    _commit(origin, "b.txt", "2")

    head_before = git_changes.head_sha(work)
    git_changes.fetch(work)
    assert git_changes.incoming_files(work) == ["b.txt"]   # previews
    assert git_changes.head_sha(work) == head_before        # but did NOT pull
    git_changes.pull_ff(work)
    assert git_changes.incoming_files(work) == []           # nothing left after pull


def test_pull_ff_noop_when_up_to_date(tmp_path):
    origin = _init_repo(tmp_path, "origin")
    _commit(origin, "a.txt", "1")
    work = tmp_path / "work"
    _clone(origin, work)

    before = git_changes.head_sha(work)
    git_changes.fetch(work)
    git_changes.pull_ff(work)                 # nothing new -> no-op, no raise
    assert git_changes.head_sha(work) == before
    assert git_changes.changed_files(work, before) == []


def test_pull_ff_raises_on_divergence(tmp_path):
    origin = _init_repo(tmp_path, "origin")
    _commit(origin, "a.txt", "1")
    work = tmp_path / "work"
    _clone(origin, work)

    _commit(origin, "b.txt", "2")            # upstream advances
    _commit(work, "c.txt", "3")              # local advances differently -> diverged

    git_changes.fetch(work)
    with pytest.raises(RuntimeError):
        git_changes.pull_ff(work)
