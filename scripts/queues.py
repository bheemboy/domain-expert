# scripts/queues.py
"""queues.py — per-source two-phase work queues for the ingest pipeline.

For each source (see sources.py) there are two files under the state dir:
    <source>.extract   identities awaiting extraction (or re-extraction)
    <source>.synth     identities extracted, awaiting synthesis
An identity (a Jira KEY, or an absolute file path) lives in exactly one file; its
location IS its state. No timestamps, no in-line markers. This module is the only
writer to these files.
"""

import sys
from pathlib import Path

import config
import sources


def extract_file(source: str) -> Path:
    return config.state_dir() / f"{source}.extract"


def synth_file(source: str) -> Path:
    return config.state_dir() / f"{source}.synth"


def read(path: Path) -> list[str]:
    if not path.is_file():
        return []
    return [ln.strip() for ln in path.read_text(encoding="utf-8").splitlines() if ln.strip()]


def _write(path: Path, lines: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if lines:
        path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    elif path.is_file():
        path.unlink()   # empty queue file -> removed, so the dir shows only live work


def in_extract(source: str, identity: str) -> bool:
    return identity in read(extract_file(source))


def in_synth(source: str, identity: str) -> bool:
    return identity in read(synth_file(source))


def _remove(path: Path, identity: str) -> None:
    lines = [ln for ln in read(path) if ln != identity]
    _write(path, lines)


def _append(path: Path, identity: str) -> None:
    lines = read(path)
    if identity not in lines:
        lines.append(identity)
    _write(path, lines)


def enqueue(source: str, identity: str) -> None:
    """check_for_changes reconcile: ensure the identity is pending extraction.
    Already in .extract -> no-op; in .synth (changed again) -> bump back to
    .extract; otherwise append to .extract."""
    if in_extract(source, identity):
        return
    if in_synth(source, identity):
        _remove(synth_file(source), identity)
    _append(extract_file(source), identity)


def move_to_synth(source: str, identity: str) -> None:
    """Extract succeeded: identity moves .extract -> .synth."""
    _remove(extract_file(source), identity)
    _append(synth_file(source), identity)


def _remove_synth(source: str, identity: str) -> None:
    """Low-level: drop an identity from .synth WITHOUT advancing the watermark.
    Callers should use synthed(), which is the complete post-synthesis operation."""
    _remove(synth_file(source), identity)


def source_empty(source: str) -> bool:
    return not read(extract_file(source)) and not read(synth_file(source))


def _next(file_fn, n: int) -> list[tuple[str, str]]:
    out: list[tuple[str, str]] = []
    for source in sources.source_order():
        for identity in read(file_fn(source)):
            out.append((source, identity))
            if len(out) >= n:
                return out
    return out


def next_extract(n: int) -> list[tuple[str, str]]:
    return _next(extract_file, n)


def next_synth(n: int) -> list[tuple[str, str]]:
    return _next(synth_file, n)


def synthed(source: str, identity: str) -> None:
    """Synth completed an identity: remove it from the synth queue. No watermark to
    advance — git detection is stateless and the Jira cursor advanced at detection."""
    _remove_synth(source, identity)


def status() -> str:
    pe = ps = 0
    per: list[str] = []
    for source in sources.source_order():
        e, s = len(read(extract_file(source))), len(read(synth_file(source)))
        pe += e
        ps += s
        if e or s:
            per.append(f"{source}(e={e},s={s})")
    return (f"pending_extract={pe} pending_synth={ps}"
            + (" | " + " ".join(per) if per else ""))


def main() -> None:
    a = sys.argv[1:]
    if not a:
        print(__doc__)
        sys.exit(2)
    cmd = a[0]
    if cmd == "next-extract":
        for src, ident in next_extract(int(a[1]) if len(a) > 1 else 1):
            print(f"{src}\t{ident}")
        sys.exit(0)
    if cmd == "next-synth":
        for src, ident in next_synth(int(a[1]) if len(a) > 1 else 1):
            print(f"{src}\t{ident}")
        sys.exit(0)
    if cmd == "enqueue":          # enqueue <identity>  (source derived)
        ident = a[1]
        try:
            enqueue(sources.source_of(ident), ident)
        except ValueError as e:
            print(f"ERROR: {e}", file=sys.stderr)
            sys.exit(2)
        sys.exit(0)
    if cmd == "extracted":        # extracted <source> <identity>
        move_to_synth(a[1], a[2])
        sys.exit(0)
    if cmd == "synthed":          # synthed <source> <identity>
        synthed(a[1], a[2])
        sys.exit(0)
    if cmd == "status":
        print(status())
        sys.exit(0)
    print(f"unknown command: {cmd}", file=sys.stderr)
    sys.exit(2)


if __name__ == "__main__":
    main()
