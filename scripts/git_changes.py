"""git_changes.py — thin git wrappers for stateless change detection.

Detection is stateless: the repo's own HEAD is the watermark. A run captures
``before = head_sha`` (HEAD before this run), then ``fetch`` + ``pull_ff`` advance
HEAD to the upstream tip, and ``changed_files(repo, before)`` is the diff
``before..HEAD`` — exactly what the pull brought in. No watermark/state IO here.
"""

import subprocess
from pathlib import Path


def _git(repo: Path, *args: str) -> tuple[int, str]:
    r = subprocess.run(["git", "-C", str(repo), *args],
                       capture_output=True, text=True, timeout=120)
    return r.returncode, r.stdout


def head_sha(repo: Path) -> str:
    code, out = _git(repo, "rev-parse", "HEAD")
    if code != 0:
        raise RuntimeError(f"not a git repo or no HEAD: {repo}")
    return out.strip()


def fetch(repo: Path) -> None:
    """Update remote-tracking refs (no working-tree change). Raises on failure."""
    r = subprocess.run(["git", "-C", str(repo), "fetch"],
                       capture_output=True, text=True, timeout=300)
    if r.returncode != 0:
        raise RuntimeError(f"git fetch failed in {repo}: {r.stderr.strip()}")


def pull_ff(repo: Path) -> None:
    """Fast-forward the current branch to its upstream. Raises (rather than creating
    a merge) if the repo has diverged."""
    r = subprocess.run(["git", "-C", str(repo), "pull", "--ff-only"],
                       capture_output=True, text=True, timeout=300)
    if r.returncode != 0:
        raise RuntimeError(f"git pull --ff-only failed in {repo}: {r.stderr.strip()}")


def incoming_files(repo: Path, subpath: str | None = None) -> list[str]:
    """Repo-relative paths a pull WOULD bring in (diff HEAD..@{u}). Call after
    fetch(); used by --dry-run to preview without pulling."""
    args = ["diff", "--name-only", "HEAD", "@{u}"]
    if subpath:
        args += ["--", subpath]
    code, out = _git(repo, *args)
    return [l for l in out.splitlines() if l] if code == 0 else []


def changed_files(repo: Path, before_sha: str, subpath: str | None = None) -> list[str]:
    """Repo-relative paths changed between ``before_sha`` and HEAD."""
    args = ["diff", "--name-only", before_sha, "HEAD"]
    if subpath:
        args += ["--", subpath]
    code, out = _git(repo, *args)
    return [l for l in out.splitlines() if l] if code == 0 else []


def tracked_files(repo: Path) -> list[str]:
    """Repo-relative paths of every tracked file (git ls-files). Used by --backfill
    to enqueue a repo's existing content; lists tracked files only, so it skips
    .git/ and untracked build artifacts. Raises if the repo can't be read."""
    code, out = _git(repo, "ls-files")
    if code != 0:
        raise RuntimeError(f"git ls-files failed in {repo}")
    return [l for l in out.splitlines() if l]


def diff_text(repo: Path, before_sha: str, subpath: str | None = None) -> str:
    """Full diff between ``before_sha`` and HEAD."""
    args = ["diff", before_sha, "HEAD"]
    if subpath:
        args += ["--", subpath]
    code, out = _git(repo, *args)
    return out if code == 0 else ""
