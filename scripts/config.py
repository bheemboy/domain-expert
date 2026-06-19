"""config.py — single source of project identity for all scripts.

Reads wiki.config.yaml (repo root, or $WIKI_CONFIG) and exposes typed
accessors. No caching: the file is tiny and re-reading keeps tests isolated.
"""

import copy
import os
from pathlib import Path

import yaml

def config_path() -> Path:
    """Path to the consumer repo's wiki.config.yaml.

    $WIKI_CONFIG wins (one-off override / tests). Otherwise walk up from the
    working directory to the nearest dir containing wiki.config.yaml, so the
    scripts work from anywhere inside a wiki repo regardless of where the code
    itself lives (e.g. installed as a plugin elsewhere on disk).
    """
    override = os.environ.get("WIKI_CONFIG")
    if override:
        return Path(override)
    cur = Path.cwd().resolve()
    for d in (cur, *cur.parents):
        cand = d / "wiki.config.yaml"
        if cand.is_file():
            return cand
    raise FileNotFoundError(
        f"not inside a wiki repo: no wiki.config.yaml found from {cur} upward. "
        "Run /wiki-init to scaffold one, cd into a wiki repo, or set $WIKI_CONFIG."
    )


def wiki_root() -> Path:
    """The consumer wiki repo root (dir holding wiki.config.yaml)."""
    return config_path().resolve().parent


def load() -> dict:
    path = config_path()
    if not path.is_file():
        raise FileNotFoundError(f"wiki config not found: {path}")
    return yaml.safe_load(path.read_text(encoding="utf-8")) or {}


def project_key() -> str:
    return load()["project"]["key"]


def project_name() -> str:
    return load()["project"]["name"]


def config_dir() -> Path:
    return Path(load()["project"]["config_dir"]).expanduser()


def state_dir() -> Path:
    """Machine-local runtime-state dir: per-source work queues + the Jira cursor
    (jira-cursor.json). Lives under the per-project config_dir (alongside, but
    separate from, the durable jira.token secret), created on first access since
    it lives outside the repo. Override with $STATE_DIR (used by tests)."""
    d = Path(os.environ.get("STATE_DIR") or (config_dir() / "state"))
    d.mkdir(parents=True, exist_ok=True)
    return d


def jira_base_url() -> str:
    return load()["jira"]["base_url"]


def jira_jql() -> str:
    return load()["jira"]["jql"].strip()


def source_repos() -> list[Path]:
    return [Path(p).expanduser() for p in (load().get("sources") or [])]


def lint_config() -> dict:
    return load().get("lint") or {}


_SYNTH_TUNING_DEFAULTS = {
    "jira": {"small_lines": 150, "solo_lines": 400, "small_batch": 15, "mid_batch": 6},
    "doc":  {"small_lines": 250, "solo_lines": 700, "small_batch": 15, "mid_batch": 4},
    "code": {"small_lines": 400, "solo_lines": 1500, "small_batch": 15, "mid_batch": 3},
    "default_batch": 12,
}


def synth_tuning() -> dict:
    """Per-kind synth batching cutoffs. Code-baked defaults, optionally overridden by
    a `synth_tuning:` block in wiki.config.yaml. Absent keys fall back to defaults, so
    a config with no block (or no key) reproduces today's behavior. The `code` bucket
    covers both `code` and `prose` kinds."""
    merged = copy.deepcopy(_SYNTH_TUNING_DEFAULTS)
    override = load().get("synth_tuning") or {}
    for kind, vals in override.items():
        if isinstance(vals, dict) and isinstance(merged.get(kind), dict):
            merged[kind].update(vals)
        else:
            merged[kind] = vals
    return merged


# Built-in ignore globs: universally junk for a domain wiki — vendored trees,
# build/minified output, generated TS lib artifacts, lockfiles, binary assets,
# styling, and certs. Consumer repos extend these via an `ignore:` list (e.g. a
# committed compiled lib like `ac_portal/local_modules/**`). Matched over the
# repo-relative POSIX path; see ignore.py for semantics.
_IGNORE_DEFAULTS = [
    "**/node_modules/**",
    "**/vendor/**",
    "**/*.min.js",
    "**/*.min.css",
    "**/*.map",
    "**/*.bundle.js",
    "**/*.d.ts",
    "**/*.metadata.json",
    "**/*.lock",
    "**/package-lock.json",
    "**/yarn.lock",
    "**/pnpm-lock.yaml",
    "**/poetry.lock",
    "**/*.svg", "**/*.png", "**/*.jpg", "**/*.jpeg", "**/*.gif", "**/*.ico",
    "**/*.ttf", "**/*.otf", "**/*.woff", "**/*.woff2", "**/*.eot",
    "**/*.wav", "**/*.mp3", "**/*.mp4",
    "**/*.scss", "**/*.css", "**/*.less", "**/*.sass",
    "**/*.pem",
]


def ignore_globs() -> list[str]:
    """Enqueue-time ignore globs: baked defaults (_IGNORE_DEFAULTS) followed by the
    consumer repo's `ignore:` list, de-duplicated with defaults kept first. A config
    with no `ignore:` block reproduces just the defaults."""
    user = load().get("ignore") or []
    seen: set[str] = set()
    out: list[str] = []
    for g in [*_IGNORE_DEFAULTS, *user]:
        if g not in seen:
            seen.add(g)
            out.append(g)
    return out
