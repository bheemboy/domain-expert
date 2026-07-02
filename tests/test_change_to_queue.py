# tests/test_change_to_queue.py
import textwrap
from datetime import date
from pathlib import Path


def _cfg(tmp_path, monkeypatch, repos=(), docs_location=None):
    cfg = tmp_path / "wiki.config.yaml"
    repo_lines = "".join(f"\n        - {r}" for r in repos)  # 8-space indent = dedent baseline
    docs_block = (
        f"\n        docs:\n          location: {docs_location}" if docs_location else ""
    )
    cfg.write_text(textwrap.dedent(f"""
        project:
          key: TESTPROJ
          name: "T"
          config_dir: {tmp_path}/state
        jira:
          base_url: https://example.atlassian.net
          jql: |
            project = TESTPROJ
        sources:{repo_lines}{docs_block}
    """))
    monkeypatch.setenv("WIKI_CONFIG", str(cfg))
    monkeypatch.setenv("STATE_DIR", str(tmp_path / "state"))


def test_enqueue_git_source_changes_are_idempotent(tmp_path, monkeypatch):
    """Two detection passes with no new commits in between must not duplicate lines.
    (scan_git_candidates is stubbed; statelessness comes from HEAD advancing on pull,
    which the stub models by returning files only on the first pass.)"""
    repo = tmp_path / "asv"
    repo.mkdir()
    _cfg(tmp_path, monkeypatch, [str(repo)])
    import queues, sources, check_for_changes as cfc

    name = sources.clean_name(repo)
    changed = [str(repo / "a.py"), str(repo / "b.py")]
    calls = {"n": 0}

    def fake_scan():
        # First pass sees the new commit's files; after pull, HEAD advances, so a
        # second pass with no new commits returns nothing.
        calls["n"] += 1
        return [(name, changed)] if calls["n"] == 1 else []

    monkeypatch.setattr(cfc, "scan_git_candidates", fake_scan)
    monkeypatch.setattr(cfc, "enumerate_jira_candidates", lambda: [])

    cfc.run(check_jira=False, check_git=True)
    cfc.run(check_jira=False, check_git=True)   # nothing new -> no dupes

    assert queues.read(queues.extract_file(name)) == changed


def test_expand_identities_folder_recurses(tmp_path, monkeypatch):
    repo = tmp_path / "asv"
    (repo / "sub").mkdir(parents=True)
    (repo / "a.py").write_text("x")
    (repo / "sub" / "b.md").write_text("y")
    _cfg(tmp_path, monkeypatch, [str(repo)])
    import check_for_changes as cfc

    # A directory expands to every file beneath it (resolved, recursive, sorted).
    out = cfc._expand_identities([str(repo)])
    assert out == [str((repo / "a.py").resolve()), str((repo / "sub" / "b.md").resolve())]


def _git_init(repo: Path) -> None:
    import subprocess
    for args in (["init", "-q"], ["add", "-A"],
                 ["-c", "user.email=t@t", "-c", "user.name=t", "commit", "-q", "-m", "x"]):
        subprocess.run(["git", "-C", str(repo), *args], check=True,
                       capture_output=True, text=True)


def test_backfill_enqueues_tracked_files_only(tmp_path, monkeypatch):
    """--backfill expands a repo to its git-tracked files (absolute), skipping
    untracked artifacts and never recursing into .git/."""
    repo = tmp_path / "asv"
    (repo / "sub").mkdir(parents=True)
    (repo / "a.py").write_text("x")
    (repo / "sub" / "b.md").write_text("y")
    _git_init(repo)
    (repo / "untracked.tmp").write_text("z")     # not committed -> excluded
    _cfg(tmp_path, monkeypatch, [str(repo)])
    import check_for_changes as cfc, sources

    name = sources.clean_name(repo)
    expected = [str((repo / "a.py").resolve()), str((repo / "sub" / "b.md").resolve())]
    # By configured source name and by path resolve to the same tracked-file set.
    kept, _ = cfc._backfill_identities([name]); assert sorted(kept) == sorted(expected)
    kept, _ = cfc._backfill_identities([str(repo)]); assert sorted(kept) == sorted(expected)


def test_backfill_rejects_non_repo(tmp_path, monkeypatch):
    import pytest
    _cfg(tmp_path, monkeypatch, [])
    import check_for_changes as cfc

    with pytest.raises(ValueError):
        cfc._backfill_identities([str(tmp_path / "not-a-repo")])


def test_expand_identities_keeps_keys_and_files(tmp_path, monkeypatch):
    f = tmp_path / "f.pdf"
    f.write_text("x")
    _cfg(tmp_path, monkeypatch, [])
    import check_for_changes as cfc

    assert cfc._expand_identities(["TESTPROJ-7"]) == ["TESTPROJ-7"]      # KEY untouched
    assert cfc._expand_identities([str(f)]) == [str(f.resolve())]         # file -> absolute


def test_run_jira_enqueues_and_advances_cursor(tmp_path, monkeypatch):
    """The Jira side of run(): keys land in jira.extract and the cursor advances at
    detection (no pending target — that machinery is gone)."""
    _cfg(tmp_path, monkeypatch, [])
    import queues, jira_cursor, check_for_changes as cfc

    monkeypatch.setattr(cfc, "enumerate_jira_candidates",
                        lambda: ["TESTPROJ-1", "TESTPROJ-2"])

    cfc.run(check_jira=True, check_git=False)

    assert queues.read(queues.extract_file("jira")) == ["TESTPROJ-1", "TESTPROJ-2"]
    assert jira_cursor.get("TESTPROJ") == date.today().isoformat()


def test_full_flow_git_run_drain(tmp_path, monkeypatch):
    """End-to-end: run() enqueues a git file; extract+synth drain it; no watermark
    state is touched (HEAD is the watermark, advanced by the pull inside scan)."""
    repo = tmp_path / "asv"
    repo.mkdir()
    _cfg(tmp_path, monkeypatch, [str(repo)])
    import queues, sources, jira_cursor, check_for_changes as cfc

    name = sources.clean_name(repo)
    f = str(repo / "a.py")
    monkeypatch.setattr(cfc, "scan_git_candidates", lambda: [(name, [f])])
    monkeypatch.setattr(cfc, "enumerate_jira_candidates", lambda: [])

    cfc.run(check_jira=False, check_git=True)
    assert queues.next_extract(10) == [(name, f)]

    queues.move_to_synth(name, f)                # extract phase
    assert queues.next_synth(10) == [(name, None, None, f)]

    queues.synthed(name, f)                      # synth phase
    assert queues.source_empty(name)
    # State holds only the jira cursor; git left no trace.
    assert jira_cursor.get("TESTPROJ") is None


def test_backfill_filters_ignored_tracked_files(tmp_path, monkeypatch):
    repo = tmp_path / "asv"
    (repo / ".git").mkdir(parents=True)
    _cfg(tmp_path, monkeypatch, repos=[str(repo)])

    import importlib, check_for_changes, git_changes
    importlib.reload(check_for_changes)

    tracked = [
        "src/app/user.py",
        "local_modules/@agilent/common/bundles/x.umd.min.js",
        "assets/logo.svg",
        "src/app/billing.ts",
    ]
    monkeypatch.setattr(git_changes, "tracked_files", lambda _repo: tracked)
    monkeypatch.setattr(check_for_changes.git_changes, "tracked_files", lambda _repo: tracked)

    kept, ignored = check_for_changes._backfill_identities([str(repo)])
    kept_rel = sorted(str(Path(p).relative_to(repo)) for p in kept)
    assert kept_rel == ["src/app/billing.ts", "src/app/user.py"]
    # the min.js and svg were dropped by default rules
    assert ignored.get("**/*.min.js") == 1
    assert ignored.get("**/*.svg") == 1


def test_detection_filters_ignored_changed_files(tmp_path, monkeypatch):
    repo = tmp_path / "asv"
    (repo / ".git").mkdir(parents=True)
    (repo / "src").mkdir(parents=True)
    (repo / "src" / "user.py").write_text("x = 1\n")
    (repo / "logo.svg").write_text("<svg/>\n")
    _cfg(tmp_path, monkeypatch, repos=[str(repo)])

    import importlib, check_for_changes, sources, git_changes
    importlib.reload(check_for_changes)

    monkeypatch.setattr(check_for_changes.sources, "detect_repos",
                        lambda: [(repo, "asv")])
    monkeypatch.setattr(check_for_changes.git_changes, "head_sha", lambda _r: "old")
    monkeypatch.setattr(check_for_changes.git_changes, "fetch", lambda _r: None)
    monkeypatch.setattr(check_for_changes.git_changes, "pull_ff", lambda _r: None)
    monkeypatch.setattr(check_for_changes.git_changes, "changed_files",
                        lambda _r, _b: ["src/user.py", "logo.svg"])

    out = check_for_changes.scan_git_candidates()
    assert len(out) == 1
    name, paths = out[0]
    assert name == "asv"
    assert [Path(p).name for p in paths] == ["user.py"]  # svg filtered out


def test_force_folder_expansion_is_unfiltered(tmp_path, monkeypatch):
    repo = tmp_path / "asv"
    (repo / "src").mkdir(parents=True)
    (repo / "src" / "user.py").write_text("x=1\n")
    (repo / "src" / "x.min.js").write_text("//min\n")
    (repo / "src" / "diagram.png").write_text("png\n")
    _cfg(tmp_path, monkeypatch, repos=[str(repo)])

    import importlib, check_for_changes
    importlib.reload(check_for_changes)

    # folder expansion under --force keeps EVERYTHING (explicit intent wins)
    expanded = check_for_changes._expand_identities([str(repo / "src")])
    names = sorted(Path(p).name for p in expanded)
    assert names == ["diagram.png", "user.py", "x.min.js"]

    # a single named ignored file remains exempt (regression guard)
    named = check_for_changes._expand_identities([str(repo / "src" / "x.min.js")])
    assert [Path(p).name for p in named] == ["x.min.js"]


def test_enqueue_identities_forced_marks_each(tmp_path, monkeypatch):
    repo = tmp_path / "asv"
    (repo / ".git").mkdir(parents=True)
    f = repo / "src" / "diagram.png"
    f.parent.mkdir(parents=True)
    f.write_text("png\n")
    _cfg(tmp_path, monkeypatch, repos=[str(repo)])
    monkeypatch.setenv("STATE_DIR", str(tmp_path / "state"))
    import importlib, check_for_changes, queues
    importlib.reload(check_for_changes)

    ident = str(f.resolve())
    check_for_changes._enqueue_identities([ident], dry_run=False, verb="force-enqueue", forced=True)
    assert queues.is_forced(ident)


def test_enqueue_identities_forced_dry_run_does_not_mark(tmp_path, monkeypatch):
    repo = tmp_path / "asv"
    (repo / ".git").mkdir(parents=True)
    f = repo / "src" / "diagram.png"
    f.parent.mkdir(parents=True)
    f.write_text("png\n")
    _cfg(tmp_path, monkeypatch, repos=[str(repo)])
    monkeypatch.setenv("STATE_DIR", str(tmp_path / "state"))
    import importlib, check_for_changes, queues
    importlib.reload(check_for_changes)

    ident = str(f.resolve())
    check_for_changes._enqueue_identities([ident], dry_run=True, verb="force-enqueue", forced=True)
    assert not queues.is_forced(ident)


def test_enqueue_identities_reports_ignored_summary(tmp_path, monkeypatch, capsys):
    repo = tmp_path / "asv"
    (repo / ".git").mkdir(parents=True)
    _cfg(tmp_path, monkeypatch, repos=[str(repo)])
    import importlib, check_for_changes
    importlib.reload(check_for_changes)

    ids = [str((repo / "src" / "user.py"))]
    check_for_changes._enqueue_identities(
        ids, dry_run=True, verb="enqueue",
        ignored={"**/*.min.js": 3, "**/*.svg": 1})
    out = capsys.readouterr().out
    assert "would enqueue 1" in out
    assert "ignored 4" in out
    assert "**/*.min.js" in out  # by-rule breakdown present


def test_detection_excludes_docs_under_source(tmp_path, monkeypatch):
    repo = tmp_path / "asv"
    (repo / ".git").mkdir(parents=True)
    (repo / "src").mkdir(parents=True)
    (repo / "src" / "user.py").write_text("x = 1\n")
    docs = repo / "Documentation"
    docs.mkdir()
    (docs / "guide.md").write_text("# guide\n")
    _cfg(tmp_path, monkeypatch, repos=[str(repo)], docs_location=str(docs))

    import importlib, check_for_changes, git_changes
    importlib.reload(check_for_changes)

    monkeypatch.setattr(check_for_changes.sources, "detect_repos",
                        lambda: [(repo, "asv")])
    monkeypatch.setattr(check_for_changes.git_changes, "head_sha", lambda _r: "old")
    monkeypatch.setattr(check_for_changes.git_changes, "fetch", lambda _r: None)
    monkeypatch.setattr(check_for_changes.git_changes, "pull_ff", lambda _r: None)
    monkeypatch.setattr(check_for_changes.git_changes, "changed_files",
                        lambda _r, _b: ["src/user.py", "Documentation/guide.md"])

    out = check_for_changes.scan_git_candidates()
    assert len(out) == 1
    name, paths = out[0]
    assert name == "asv"
    assert [Path(p).name for p in paths] == ["user.py"]  # Documentation/guide.md excluded


def test_backfill_excludes_docs_under_source(tmp_path, monkeypatch):
    repo = tmp_path / "asv"
    (repo / ".git").mkdir(parents=True)
    docs = repo / "Documentation"
    docs.mkdir()
    _cfg(tmp_path, monkeypatch, repos=[str(repo)], docs_location=str(docs))

    import importlib, check_for_changes, git_changes
    importlib.reload(check_for_changes)

    tracked = ["src/app/user.py", "Documentation/guide.md", "Documentation/sub/p.mdx"]
    monkeypatch.setattr(git_changes, "tracked_files", lambda _repo: tracked)
    monkeypatch.setattr(check_for_changes.git_changes, "tracked_files", lambda _repo: tracked)

    kept, ignored = check_for_changes._backfill_identities([str(repo)])
    kept_rel = sorted(str(Path(p).relative_to(repo)) for p in kept)
    assert kept_rel == ["src/app/user.py"]
    assert ignored.get("Documentation/**") == 2


def test_dry_run_applies_ignore_and_docs_exclusion(tmp_path, monkeypatch, capsys):
    import sys
    repo = tmp_path / "asv"
    (repo / ".git").mkdir(parents=True)
    docs = repo / "Documentation"
    docs.mkdir()
    _cfg(tmp_path, monkeypatch, repos=[str(repo)], docs_location=str(docs))

    import importlib, check_for_changes
    importlib.reload(check_for_changes)

    monkeypatch.setattr(check_for_changes.sources, "detect_repos",
                        lambda: [(repo, "asv")])
    monkeypatch.setattr(check_for_changes.git_changes, "fetch", lambda _r: None)
    monkeypatch.setattr(check_for_changes.git_changes, "incoming_files",
                        lambda _r: ["src/user.py", "logo.svg", "Documentation/guide.md"])
    monkeypatch.setattr(check_for_changes, "enumerate_jira_candidates", lambda: [])
    monkeypatch.setattr(sys, "argv", ["check_for_changes.py", "--dry-run"])

    check_for_changes.main()
    out = capsys.readouterr().out
    assert "would enqueue 1 file(s) across 1 source(s)" in out  # only src/user.py kept
    assert "ignored 2 file(s) by rule" in out  # logo.svg + Documentation/guide.md


def test_force_over_docs_under_source_still_enqueues(tmp_path, monkeypatch):
    """Spec §6: the explicit path form (--force) bypasses the docs auto-exclusion,
    so a docs: location nested in a source can still be deliberately seeded."""
    repo = tmp_path / "asv"
    (repo / ".git").mkdir(parents=True)
    docs = repo / "Documentation"
    docs.mkdir()
    (docs / "guide.md").write_text("# guide\n")
    _cfg(tmp_path, monkeypatch, repos=[str(repo)], docs_location=str(docs))

    import importlib, check_for_changes
    importlib.reload(check_for_changes)

    expanded = check_for_changes._expand_identities([str(docs)])
    assert [Path(p).name for p in expanded] == ["guide.md"]


def test_expand_identities_skips_import_files(tmp_path, monkeypatch):
    """Force-enqueueing a folder must not enqueue extract-owned imports: the
    in-place .md next to a binary doc under raw/ is the doc's import, not an
    independent source — enqueueing both double-ingests every document."""
    _cfg(tmp_path, monkeypatch, [])
    monkeypatch.setenv("IMPORTS_DIR", str(tmp_path / "raw" / "imports"))
    import check_for_changes as cfc

    pdfs = tmp_path / "raw" / "pdfs"
    pdfs.mkdir(parents=True)
    (pdfs / "a.pdf").write_bytes(b"x")
    (pdfs / "a.md").write_text("import of a.pdf")
    (pdfs / "b.pdf").write_bytes(b"x")

    out = cfc._expand_identities([str(pdfs)])
    assert out == [str((pdfs / "a.pdf").resolve()), str((pdfs / "b.pdf").resolve())]

    # naming an import file explicitly skips it too
    assert cfc._expand_identities([str(pdfs / "a.md")]) == []
