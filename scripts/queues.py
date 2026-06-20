# scripts/queues.py
"""queues.py — per-source two-phase work queues for the ingest pipeline.

For each source (see sources.py) there are two files under the state dir:
    <source>.extract   identities awaiting extraction (or re-extraction)
    <source>.synth     identities extracted, awaiting synthesis
An identity (a Jira KEY, or an absolute file path) lives in exactly one file; its
location IS its state. No timestamps, no in-line markers. This module is the only
writer to these files.
"""

import hashlib
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


def _identity(line: str) -> str:
    """The identity is the last tab-separated field; any metadata (lines, flag) is an
    optional prefix. A bare line with no tab is its own identity — backward compatible."""
    return line.rsplit("\t", 1)[-1]


def parse_synth_line(line: str) -> tuple[int | None, str | None, str]:
    """(lines, flag, identity) for a synth line `<lines>\\t<flag>\\t<identity>`.
    A bare identity, or partial/garbled metadata, yields None for the missing fields."""
    parts = line.split("\t")
    identity = parts[-1]
    lines = flag = None
    if len(parts) >= 3:
        try:
            lines = int(parts[-3])
        except ValueError:
            lines = None
        flag = parts[-2] or None
    return lines, flag, identity


def in_extract(source: str, identity: str) -> bool:
    return identity in [_identity(ln) for ln in read(extract_file(source))]


def in_synth(source: str, identity: str) -> bool:
    return identity in [_identity(ln) for ln in read(synth_file(source))]


def _remove(path: Path, identity: str) -> None:
    _write(path, [ln for ln in read(path) if _identity(ln) != identity])


def _append(path: Path, line: str) -> None:
    ident = _identity(line)
    lines = read(path)
    if ident not in [_identity(ln) for ln in lines]:
        lines.append(line)
    _write(path, lines)


def enqueue(source: str, identity: str) -> None:
    """check_for_changes reconcile: ensure the identity is pending extraction.
    Already in .extract -> no-op; in .synth (changed again) -> bump back to
    .extract; otherwise append to .extract."""
    if in_extract(source, identity):
        return
    if in_synth(source, identity):
        _remove(synth_file(source), identity)
        clear_note(identity)   # stale triage hint must not survive a re-detect
    _append(extract_file(source), identity)


def move_to_synth(source: str, identity: str,
                  lines: int | None = None, flag: str | None = None) -> None:
    """Extract/triage succeeded: identity moves .extract -> .synth. When lines/flag are
    given, the synth line carries a `<lines>\\t<flag>\\t<identity>` metadata prefix the
    orchestrator uses for batching; otherwise it is written bare (current behavior)."""
    _remove(extract_file(source), identity)
    if lines is None and flag is None:
        synth_line = identity
    else:
        synth_line = f"{lines if lines is not None else ''}\t{flag or ''}\t{identity}"
    _append(synth_file(source), synth_line)
    clear_forced(identity)


def drop(source: str, identity: str) -> None:
    """Triage SKIP: discard an item from extraction without synthesizing it. Removes it
    from .extract and clears any note; it never reaches .synth and leaves no wiki trace."""
    _remove(extract_file(source), identity)
    clear_note(identity)
    clear_forced(identity)


def note_file(identity: str) -> Path:
    """State-dir side-car holding the triage note for an identity (keyed by a hash so a
    file-path identity is filesystem-safe)."""
    h = hashlib.sha1(identity.encode("utf-8")).hexdigest()[:16]
    return config.state_dir() / "notes" / f"{h}.txt"


def write_note(identity: str, text: str) -> None:
    if not text or not text.strip():
        return
    p = note_file(identity)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(text.strip() + "\n", encoding="utf-8")


def read_note(identity: str) -> str:
    p = note_file(identity)
    return p.read_text(encoding="utf-8").strip() if p.is_file() else ""


def clear_note(identity: str) -> None:
    p = note_file(identity)
    if p.is_file():
        p.unlink()


def forced_file(identity: str) -> Path:
    """State-dir side-car flag marking an identity as explicitly force-enqueued (keyed by
    a hash so a file-path identity is filesystem-safe). Its presence makes triage no-skip."""
    h = hashlib.sha1(identity.encode("utf-8")).hexdigest()[:16]
    return config.state_dir() / "forced" / f"{h}.flag"


def mark_forced(identity: str) -> None:
    p = forced_file(identity)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text("1\n", encoding="utf-8")


def is_forced(identity: str) -> bool:
    return forced_file(identity).is_file()


def clear_forced(identity: str) -> None:
    p = forced_file(identity)
    if p.is_file():
        p.unlink()


def _remove_synth(source: str, identity: str) -> None:
    """Low-level: drop an identity from .synth WITHOUT advancing the watermark.
    Callers should use synthed(), which is the complete post-synthesis operation."""
    _remove(synth_file(source), identity)


def source_empty(source: str) -> bool:
    return not read(extract_file(source)) and not read(synth_file(source))


def _next(file_fn, n: int) -> list[tuple[str, str]]:
    out: list[tuple[str, str]] = []
    for source in sources.source_order():
        for line in read(file_fn(source)):
            out.append((source, line))
            if len(out) >= n:
                return out
    return out


def next_extract(n: int) -> list[tuple[str, str]]:
    return [(src, _identity(line)) for src, line in _next(extract_file, n)]


def next_synth(n: int) -> list[tuple[str, int | None, str | None, str]]:
    return [(src, *parse_synth_line(line)) for src, line in _next(synth_file, n)]


def synthed(source: str, identity: str) -> None:
    """Synth completed an identity: remove it from the synth queue and clear its note."""
    _remove_synth(source, identity)
    clear_note(identity)


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
        for src, lines, flag, ident in next_synth(int(a[1]) if len(a) > 1 else 1):
            print(f"{src}\t{lines if lines is not None else ''}\t{flag or ''}\t{ident}")
        sys.exit(0)
    if cmd == "enqueue":          # enqueue <identity>  (source derived)
        ident = a[1]
        try:
            enqueue(sources.source_of(ident), ident)
        except ValueError as e:
            print(f"ERROR: {e}", file=sys.stderr)
            sys.exit(2)
        sys.exit(0)
    if cmd == "extracted":        # extracted <source> <identity> [--lines N] [--flag F]
        rest = a[1:]
        lines = flag = None
        pos: list[str] = []
        i = 0
        while i < len(rest):
            if rest[i] == "--lines":
                lines = int(rest[i + 1]); i += 2
            elif rest[i] == "--flag":
                flag = rest[i + 1]; i += 2
            else:
                pos.append(rest[i]); i += 1
        move_to_synth(pos[0], pos[1], lines=lines, flag=flag)
        sys.exit(0)
    if cmd == "drop":             # drop <source> <identity>
        drop(a[1], a[2])
        sys.exit(0)
    if cmd == "write-note":       # write-note <identity> <text...>
        write_note(a[1], " ".join(a[2:]))
        sys.exit(0)
    if cmd == "read-note":        # read-note <identity>
        print(read_note(a[1]))
        sys.exit(0)
    if cmd == "mark-forced":      # mark-forced <identity>
        mark_forced(a[1])
        sys.exit(0)
    if cmd == "is-forced":        # is-forced <identity>  -> prints 1/0
        print("1" if is_forced(a[1]) else "0")
        sys.exit(0)
    if cmd == "clear-forced":     # clear-forced <identity>
        clear_forced(a[1])
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
