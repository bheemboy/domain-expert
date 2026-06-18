# scripts/sources.py
"""sources.py — source identity & ordering for the queue-based pipeline.

A "source" is one of: ``jira``, ``raw`` (this repo's raw/ folder), or a git repo
listed in wiki.config.yaml ``sources:`` (named by clean_name). This module maps
between identities (a Jira KEY or an absolute file path), source names, and git
watermark keys, and defines the fixed priority order (jira -> raw -> repos).
"""

import re
from pathlib import Path

import config


def _key_re() -> re.Pattern:
    """Jira-key regex, compiled lazily so the project key is read at call time
    (not import time) — keeps the module import-safe and test-isolated, matching
    config.py's no-caching contract."""
    return re.compile(rf"{re.escape(config.project_key())}-\d+", re.IGNORECASE)


def clean_name(repo_path: Path) -> str:
    """Repo path -> manifest-safe source name.

    Assumes repos live under <home>/projects/work/; falls back to the basename.

    /home/u/projects/work/asv          -> asv
    /home/u/projects/work/DEV/ac_docs  -> DEV-ac_docs
    """
    path_str = str(repo_path)
    if "/projects/work/" in path_str:
        return path_str.split("/projects/work/", 1)[1].replace("/", "-")
    return repo_path.name


def git_sources() -> list[tuple[Path, str | None, str]]:
    """(repo_path, subpath, source_name) for every source whose identities are paths,
    in priority order AFTER jira: raw first, then each config repo in listed order.
    Used for identity↔source mapping (source_of) and ordering — NOT for detection
    (raw/ is not auto-detected; see detect_repos)."""
    out: list[tuple[Path, str | None, str]] = [(config.wiki_root(), "raw", "raw")]
    for p in config.source_repos():
        out.append((p, None, clean_name(p)))
    return out


def detect_repos() -> list[tuple[Path, str]]:
    """(repo_path, source_name) for the EXTERNAL git repos that check_for_changes
    fetches/pulls. Excludes raw/ (in the wiki repo, never pulled — ingested explicitly)."""
    return [(p, clean_name(p)) for p in config.source_repos()]


def source_order() -> list[str]:
    """Fixed priority: jira, raw, then config repos in listed order."""
    return ["jira"] + [name for _, _, name in git_sources()]


def is_jira_key(identity: str) -> bool:
    return bool(_key_re().fullmatch(identity.strip()))


def source_of(identity: str) -> str:
    """Map an identity to its source name. Jira KEY -> 'jira'; an absolute path under
    a git source root -> that source's name (raw wins, being most specific). Raises
    ValueError for anything else."""
    if is_jira_key(identity):
        return "jira"
    p = Path(identity)
    if not p.is_absolute():
        raise ValueError(f"identity is neither a Jira key nor an absolute path: {identity!r}")
    pr = p.resolve()
    # Most-specific root first: raw/ is under wiki_root(), so check it before repos
    # and before wiki_root() itself. git_sources() already lists raw first.
    for repo_path, subpath, name in git_sources():
        root = (repo_path / subpath) if subpath else repo_path
        try:
            pr.relative_to(root.resolve())
            return name
        except ValueError:
            continue
    raise ValueError(f"path under no known source root: {identity!r}")




def _match_root(path: str) -> Path | None:
    """The configured source-repo root (or wiki_root()) that contains an absolute
    path, or None."""
    p = Path(path)
    if not p.is_absolute():
        return None
    pr = p.resolve()
    roots = [Path(r).resolve() for r in config.source_repos()] + [config.wiki_root().resolve()]
    for root in roots:
        try:
            pr.relative_to(root)
            return root
        except ValueError:
            continue
    return None


def repo_root_of(path: str) -> Path:
    """Repo root a file lives under (for doc extraction); the file's parent if it
    isn't under any configured root."""
    root = _match_root(path)
    return root if root is not None else Path(path).resolve().parent


def repo_relative(path: str) -> str:
    """Repo-relative POSIX path used for stable doc keys."""
    p = Path(path)
    if not p.is_absolute():
        return p.as_posix().lstrip("/")
    root = _match_root(path)
    if root is not None:
        return p.resolve().relative_to(root).as_posix()
    return p.name
