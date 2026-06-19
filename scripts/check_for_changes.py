#!/usr/bin/env python3
"""
check_for_changes.py — Detect changes in Jira and external git source repos.

Enqueues candidates into per-source queue files (config_dir/state/<source>.extract)
via queues.enqueue() (idempotent — repeated runs do not duplicate entries).

Usage:
    python scripts/check_for_changes.py           # check all sources
    python scripts/check_for_changes.py --jira    # Jira only
    python scripts/check_for_changes.py --code    # external git source repos only
    python scripts/check_for_changes.py --dry-run # preview counts; no pull/queue/state writes
    python scripts/check_for_changes.py --force PATH|DIR|KEY [...]  # enqueue explicitly (dirs expand recursively)
    python scripts/check_for_changes.py --backfill REPO|PATH [...]  # enqueue all of a repo's tracked files
    python scripts/check_for_changes.py --help    # show this help and exit

Flags combine: source selectors (--jira/--code) restrict what is checked; with
none given, all sources are checked. --dry-run fetches but does not pull and writes
nothing. --force enqueues specific identities (the way raw/ drops and ad-hoc files
are ingested — raw/ is NOT auto-detected) and skips the normal scan. --backfill takes
git source repos (by configured name or path) and enqueues every tracked file in each
(git ls-files) — the one-shot way to ingest a repo's existing content the first time,
without the incremental detection that would otherwise see nothing on an up-to-date repo.

Git source repos (stateless — HEAD is the watermark):
    For each EXTERNAL repo in config `sources` (NOT raw/, which lives in the wiki
    repo and is never pulled):
      1. before = current HEAD
      2. git fetch; git pull --ff-only  (HEAD advances to the upstream tip)
      3. Enqueue the files the pull brought in (diff before..HEAD)
    Re-running with no new commits is a no-op (empty diff). raw/ and ad-hoc files
    are ingested explicitly via --force.

Jira:
    1. Query for issues updated since the per-project cursor (config_dir/state/jira-cursor.json)
    2. Content-hash deduplicate against existing digests
    3. Enqueue changed Jira KEYs into the jira .extract queue
    4. Advance the cursor (at detection)
"""

import sys
import re
from datetime import date
from pathlib import Path

from jira_utils import (
    build_issue_md,
    fetch_issues,
    resolve_epic_link_field,
    require_credentials,
    content_hash,
)
import config
import git_changes
import ignore
import jira_cursor
import queues
import sources

# ─────────────────────────────────────────────
# CONFIG
# ─────────────────────────────────────────────

_HASH_RE = re.compile(r"^content_hash\s*:\s*(\S+)\s*$", re.MULTILINE)


def _imports_jira_dir() -> Path:
    return config.wiki_root() / "raw" / "imports" / "jira"

JQL_BASE = config.jira_jql()


def import_content_hash(key: str) -> str | None:
    """Read the stored content_hash from raw/imports/jira/<KEY>.md, or None."""
    p = _imports_jira_dir() / f"{key}.md"
    if not p.is_file():
        return None
    m = _HASH_RE.search(p.read_text(encoding="utf-8"))
    return m.group(1) if m else None


# ─────────────────────────────────────────────
# JIRA ENUMERATION
# ─────────────────────────────────────────────

def build_jql(last_run_date: str | None) -> str:
    jql = JQL_BASE
    if last_run_date:
        jql += f" AND Updated >= {last_run_date}"
    jql += " ORDER BY Updated ASC"
    return jql


def enumerate_jira_candidates() -> list[str]:
    """Jira KEYs needing (re)extraction, sorted by resolution date. Read-only on
    state. Content-hash dedup against existing imports."""
    require_credentials()
    epic_link_field = resolve_epic_link_field()
    last_run_date = jira_cursor.get(config.project_key())
    issues = fetch_issues(build_jql(last_run_date), epic_link_field)
    issues.sort(key=lambda i: (i.get("fields", {}) or {}).get("resolutiondate") or "")
    keys = []
    for issue in issues:
        key = issue.get("key", "")
        live = content_hash(build_issue_md(issue, epic_link_field))
        if import_content_hash(key) == live:
            continue            # unchanged since last extract
        keys.append(key)
    return keys


# ─────────────────────────────────────────────
# GIT CHANGE DETECTION
# ─────────────────────────────────────────────

def scan_git_candidates() -> list[tuple[str, list[str]]]:
    """Stateless detection for each EXTERNAL source repo: fetch + ff-pull, then the
    files the pull brought in (diff before..HEAD). Returns (source_name, [abs paths]).
    HEAD is the watermark — no state is read or written. A repo that fails (not a git
    repo, fetch/pull error, diverged) is warned-and-skipped so it can't block others."""
    out = []
    for repo_path, name in sources.detect_repos():
        if not (repo_path / ".git").is_dir():
            print(f"  Warning: {repo_path} is not a git repo — skipping.")
            continue
        try:
            before = git_changes.head_sha(repo_path)
            git_changes.fetch(repo_path)
            git_changes.pull_ff(repo_path)
            files = git_changes.changed_files(repo_path, before)
        except RuntimeError as e:
            print(f"  Warning: {name}: {e} — skipping.", file=sys.stderr)
            continue
        abs_paths = [str(repo_path / f) for f in files if (repo_path / f).exists()]
        if not abs_paths:
            print(f"  {name}: up to date.")
            continue
        print(f"  {name}: {len(abs_paths)} file(s)")
        out.append((name, abs_paths))
    return out


# ─────────────────────────────────────────────
# RUN
# ─────────────────────────────────────────────

def run(check_jira: bool = True, check_git: bool = True) -> None:
    if check_jira:
        try:
            keys = enumerate_jira_candidates()
            for key in keys:
                queues.enqueue("jira", key)
            if keys:
                jira_cursor.advance(config.project_key(), date.today().isoformat())
            print(f"jira: enqueued {len(keys)}")
        except Exception as e:
            print(f"WARNING: jira detection failed, skipping jira — {e}", file=sys.stderr)
    if check_git:
        total = 0
        for name, paths in scan_git_candidates():
            for p in paths:
                queues.enqueue(name, p)
            total += len(paths)
        print(f"git: enqueued {total}")


# ─────────────────────────────────────────────
# MAIN
# ─────────────────────────────────────────────

def _expand_identities(args: list[str]) -> list[str]:
    """Expand --force args into concrete identities: a Jira KEY stays as-is; a
    directory expands to every file beneath it (recursive); a file path stays as-is.
    Paths are resolved to absolute so source_of can map them."""
    out: list[str] = []
    for a in args:
        if sources.is_jira_key(a):
            out.append(a)
            continue
        p = Path(a)
        if p.is_dir():
            out.extend(str(f.resolve()) for f in sorted(p.rglob("*")) if f.is_file())
        elif p.exists():
            out.append(str(p.resolve()))
        else:
            out.append(a)   # not on disk — let source_of raise a clear error
    return out


def _backfill_identities(args: list[str]) -> tuple[list[str], dict[str, int]]:
    """Expand --backfill repo args into every tracked file (absolute path), with
    ignore-glob filtering applied to the repo-relative path. Each arg is a configured
    source name (e.g. 'asv') or a path to a git repo. Returns (kept_abs_paths,
    ignored_by_rule). Uses git ls-files, so it lists tracked files only and never
    recurses into .git/ or build artifacts."""
    by_name = {name: path for path, name in sources.detect_repos()}
    globs = config.ignore_globs()
    kept_abs: list[str] = []
    ignored_total: dict[str, int] = {}
    for a in args:
        repo = by_name.get(a) or Path(a).resolve()
        if not (repo / ".git").is_dir():
            raise ValueError(
                f"--backfill: {a!r} is not a configured source name or a git repo")
        rels = list(git_changes.tracked_files(repo))
        kept, ignored = ignore.partition(rels, globs)
        kept_abs.extend(str((repo / f).resolve()) for f in kept)
        for g, c in ignored.items():
            ignored_total[g] = ignored_total.get(g, 0) + c
    return kept_abs, ignored_total


def _enqueue_identities(identities: list[str], dry_run: bool, verb: str) -> None:
    """Map each identity to its source and enqueue it (unless dry-run); print a count.
    Shared by --force and --backfill."""
    n = 0
    for identity in identities:
        try:
            source = sources.source_of(identity)
        except ValueError as e:
            print(f"ERROR: {e}", file=sys.stderr)
            sys.exit(2)
        if not dry_run:
            queues.enqueue(source, identity)
        n += 1
    done = f"would {verb}" if dry_run else f"{verb}d"
    print(f"{done} {n} identit{'y' if n == 1 else 'ies'}")


def main():
    if "--help" in sys.argv[1:] or "-h" in sys.argv[1:]:
        print(__doc__.strip())
        return

    flags = [a for a in sys.argv[1:] if a.startswith("--")]
    args = [a for a in sys.argv[1:] if not a.startswith("--")]

    known_flags = {"--jira", "--code", "--dry-run", "--force", "--backfill"}
    unknown = [f for f in flags if f not in known_flags]
    if unknown:
        print(f"ERROR: unknown flag(s): {' '.join(unknown)}", file=sys.stderr)
        sys.exit(2)

    dry_run = "--dry-run" in flags

    # --force: explicitly enqueue given KEYs / files / folders (folders expand to all
    # files beneath them). This is how raw/ drops and ad-hoc files are ingested.
    if "--force" in flags:
        if not args:
            print("ERROR: --force requires at least one KEY, path, or folder", file=sys.stderr)
            sys.exit(2)
        _enqueue_identities(_expand_identities(args), dry_run, "force-enqueue")
        return

    # --backfill: enqueue every tracked file of the given git source repo(s), named by
    # configured source name or path. The first-time "ingest a whole repo" command.
    if "--backfill" in flags:
        if not args:
            print("ERROR: --backfill requires at least one source name or repo path",
                  file=sys.stderr)
            sys.exit(2)
        try:
            identities = _backfill_identities(args)
        except (ValueError, RuntimeError) as e:
            print(f"ERROR: {e}", file=sys.stderr)
            sys.exit(2)
        _enqueue_identities(identities, dry_run, "enqueue")
        return

    explicit_select = any(f in flags for f in ["--code", "--jira"])
    check_jira = "--jira" in flags or not explicit_select
    check_git = "--code" in flags or not explicit_select

    if dry_run:
        print("=" * 60)
        print("DRY RUN MODE — No changes will be made")
        print("=" * 60)
        if check_jira:
            try:
                keys = enumerate_jira_candidates()
                print(f"jira: would enqueue {len(keys)} key(s)")
            except Exception as e:
                print(f"jira: error during enumeration — {e}")
        if check_git:
            total = nsrc = 0
            for repo_path, name in sources.detect_repos():
                if not (repo_path / ".git").is_dir():
                    continue
                try:
                    git_changes.fetch(repo_path)               # read-only-ish; no pull
                    incoming = git_changes.incoming_files(repo_path)
                except RuntimeError as e:
                    print(f"git: {name}: {e}")
                    continue
                if incoming:
                    nsrc += 1
                    total += len(incoming)
            print(f"git: would enqueue {total} file(s) across {nsrc} source(s)")
        print("=" * 60)
        return

    run(check_jira=check_jira, check_git=check_git)


if __name__ == "__main__":
    main()
