"""comment_contract.py — mechanical enforcement of the comment contract.

The LLM drafts; this module verifies. Prompts drift, so budgets and structure
are never left to the prompt alone. Two kinds:

  ask        — submitter-facing: ≤3 numbered asks; ≤1 procedure of ≤5 sub-steps
               whose last step is a report-back line; ~150 words (~300 with a
               procedure).
  assessment — review-team-facing: ~400 words, organized sections.

Word budgets carry 10% grace: the ~150/300/400 budgets are targets, the hard
ceilings here are target × 1.1. The marker is enforced mechanically too:
every delivered comment starts with the configured marker string.
"""

import argparse
import re
import sys
from pathlib import Path

ASK_WORDS = 165          # 150 + 10% grace
ASK_PROC_WORDS = 330     # 300 + 10% grace
ASSESS_WORDS = 440       # 400 + 10% grace
MAX_ASKS = 3
MAX_PROC_STEPS = 5
DEFAULT_MARKER = "🤖 Automated defect review —"

_ASK_LINE_RE = re.compile(r"^\d+[.)]\s+")
_SUBSTEP_RE = re.compile(r"^\s{2,}(?:\d+[.)]|-)\s+")
_REPORT_RE = re.compile(r"(?i)\b(report|attach|send|reply|tell|paste)\b")


def word_count(text: str) -> int:
    return len(re.findall(r"\S+", text))


def split_asks(text: str) -> list:
    """Top-level numbered asks, each with its following indented lines."""
    lines = text.split("\n")
    asks, current = [], None
    for line in lines:
        if _ASK_LINE_RE.match(line):
            if current is not None:
                asks.append("\n".join(current))
            current = [line]
        elif current is not None and (_SUBSTEP_RE.match(line) or not line.strip()):
            current.append(line)
        elif current is not None and line.strip():
            current.append(line)
    if current is not None:
        asks.append("\n".join(current))
    return asks


def procedure_steps(ask: str) -> list:
    return [ln for ln in ask.split("\n") if _SUBSTEP_RE.match(ln)]


def check(text: str, kind: str, marker: str = DEFAULT_MARKER) -> list:
    """Return violations (empty list = compliant). kind: 'ask' | 'assessment'."""
    if kind not in ("ask", "assessment"):
        raise ValueError(f"kind must be 'ask' or 'assessment', got {kind!r}")
    violations = []
    if not text.lstrip().startswith(marker):
        violations.append("marker: comment must start with the bot marker line")
    if kind == "assessment":
        wc = word_count(text)
        if wc > ASSESS_WORDS:
            violations.append(
                f"words: {wc} exceeds the assessment ceiling {ASSESS_WORDS}")
        return violations

    asks = split_asks(text)
    if len(asks) > MAX_ASKS:
        violations.append(f"asks: {len(asks)} numbered asks exceed the max {MAX_ASKS}")
    procedures = [a for a in asks if len(procedure_steps(a)) >= 2]
    if len(procedures) > 1:
        violations.append(
            f"procedures: {len(procedures)} procedure blocks — at most one procedure per comment")
    for proc in procedures:
        steps = procedure_steps(proc)
        if len(steps) > MAX_PROC_STEPS:
            violations.append(
                f"sub-steps: procedure has {len(steps)} sub-steps, max {MAX_PROC_STEPS}")
        if not _REPORT_RE.search(steps[-1]):
            violations.append(
                "report-back: the procedure's last sub-step must say what to "
                "observe and what to send (report/attach/send/…)")
    ceiling = ASK_PROC_WORDS if procedures else ASK_WORDS
    wc = word_count(text)
    if wc > ceiling:
        violations.append(f"words: {wc} exceeds the ask ceiling {ceiling}")
    return violations


def ensure_marker(text: str, marker: str) -> str:
    """Prepend the marker line when absent. Idempotent."""
    if text.lstrip().startswith(marker):
        return text
    return f"{marker}\n\n{text}"


def main():
    ap = argparse.ArgumentParser(description="Check a draft comment against the contract.")
    ap.add_argument("file", help="Path to the draft comment (markdown).")
    ap.add_argument("--kind", required=True, choices=("ask", "assessment"))
    ap.add_argument("--marker", default=DEFAULT_MARKER)
    ap.add_argument("--fix-marker", action="store_true",
                    help="Prepend the marker in place when missing, before checking.")
    args = ap.parse_args()

    path = Path(args.file)
    text = path.read_text(encoding="utf-8")
    if args.fix_marker:
        fixed = ensure_marker(text, args.marker)
        if fixed != text:
            path.write_text(fixed, encoding="utf-8")
            text = fixed
    violations = check(text, args.kind, args.marker)
    for v in violations:
        print(v)
    sys.exit(1 if violations else 0)


if __name__ == "__main__":
    main()
