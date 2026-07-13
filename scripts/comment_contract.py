"""comment_contract.py — mechanical enforcement of the comment contract.

The LLM drafts; this module verifies. Prompts drift, so budgets and structure
are never left to the prompt alone. Two kinds:

  ask        — conversational: ONE block greeting the addressee (reporter or
               any thread participant); ≤3 numbered asks (contiguous 1..N);
               ≤1 procedure of ≤5 sub-steps whose last step is a report-back
               line; ~150 words (~300 with a procedure).
  assessment — team-facing: exactly one reviewers block, enough to decide a
               disposition and nothing else (no developer block); a
               '**Proposed disposition**' line is required and must be the
               last section; ~250 words.

Structure: typed header (`<marker> — <label>`, code-composed via
ensure_header, never LLM-written), an optional freshness line for
assessments, a `---` rule, then audience blocks separated by `---`.
Each block opens with one of: `Hello <name>,` / `**Notes for defect
reviewers**`. Only structure is checked here —
value, relevance, and plain-English judgment belong to the critic pass.
Word budgets carry 10% grace (ceiling = target × 1.1) and measure the
audience blocks only — the code-composed header and freshness line are
not charged against the LLM's budget.
"""

import argparse
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

ASK_WORDS = 165          # 150 + 10% grace
ASK_PROC_WORDS = 330     # 300 + 10% grace
ASSESS_WORDS = 275       # 250 + 10% grace
MAX_ASKS = 3
MAX_PROC_STEPS = 5
DEFAULT_MARKER = "🤖 Automated defect review"

# Comment-type labels, appended to the marker as `<marker> — <label>`. The
# header is code-composed (ensure_header); the LLM never writes it. "revised"
# is the disposition-flip notice — built by the skill, never checked here.
LABELS = {
    "ask": "needs more information",
    "assessment": "disposition proposal",
    "revised": "assessment revised",
}

DISCLAIMER = "_AI-generated: statements in this comment may be inaccurate_"

_RULE_LINE_RE = re.compile(r"^-{3,}\s*$")
_FRESHNESS_RE = re.compile(r"^_Reflects the ticket as of .+_$")
_DISCLAIMER_RE = re.compile(r"^_AI-generated:.*_$")
_HELLO_RE = re.compile(r"^Hello\b[^,\n]*,\s*$")
_REVIEWERS_HEADER = "**Notes for defect reviewers**"
_DEVELOPER_HEADER = "**Notes for developer**"

_DISPOSITION_RE = re.compile(r"^\*\*Proposed disposition")
_OTHER_SECTIONS = ("Issue summary", "Frequency", "Impact",
                   "Potential workaround", "Evidence", "Likely related",
                   "Possible fix directions", "Caveats")

_ASK_LINE_RE = re.compile(r"^\d+[.)]\s+")
_SUBSTEP_RE = re.compile(r"^\s{2,}(?:\d+[.)]|-)\s+")
_REPORT_RE = re.compile(r"(?i)\b(report|attach|send|reply|tell|paste)\b")


def _split_blocks(text: str, marker: str, kind: str = ""):
    """(violations, blocks) — strip the header line (marker + optional label),
    an optional freshness line, and the rule, then split the body on `---`
    lines. Each block is the text between rules. A label that contradicts
    `kind` is a violation; a bare marker (legacy drafts) is tolerated."""
    violations = []
    lines = text.split("\n")
    idx = 0
    while idx < len(lines) and not lines[idx].strip():
        idx += 1
    if idx >= len(lines) or not lines[idx].lstrip().startswith(marker):
        violations.append("marker: comment must start with the bot marker line")
    else:
        label = lines[idx].lstrip()[len(marker):].strip().strip("—–-").strip()
        if label and kind and label != LABELS[kind]:
            violations.append(
                f"header: label {label!r} does not match the comment kind "
                f"({kind} → {LABELS[kind]!r})")
        idx += 1
        while idx < len(lines) and not lines[idx].strip():
            idx += 1
        for line_re in (_FRESHNESS_RE, _DISCLAIMER_RE):
            if idx < len(lines) and line_re.match(lines[idx].strip()):
                idx += 1
                while idx < len(lines) and not lines[idx].strip():
                    idx += 1
        if idx >= len(lines) or not _RULE_LINE_RE.match(lines[idx].strip()):
            violations.append("rule: the marker line must be followed by a --- rule")
        else:
            idx += 1
    blocks, current = [], []
    in_fence = False
    for line in lines[idx:]:
        if line.strip().startswith("```"):
            in_fence = not in_fence
            current.append(line)
        elif not in_fence and _RULE_LINE_RE.match(line.strip()):
            blocks.append("\n".join(current))
            current = []
        else:
            current.append(line)
    blocks.append("\n".join(current))
    blocks = [b for b in blocks if b.strip()]
    return violations, blocks


def _block_header(block: str) -> str:
    for line in block.split("\n"):
        if line.strip():
            return line.strip()
    return ""


def _header_kind(header: str) -> str:
    """'submitter' | 'reviewers' | 'developer' | ''"""
    if _HELLO_RE.match(header):
        return "submitter"
    if header == _REVIEWERS_HEADER:
        return "reviewers"
    if header == _DEVELOPER_HEADER:
        return "developer"
    return ""


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
    violations, blocks = _split_blocks(text, marker, kind)

    audiences = []
    for block in blocks:
        header = _block_header(block)
        audience = _header_kind(header)
        if not audience:
            violations.append(
                f"audience: block starting {header[:40]!r} must open with "
                "'Hello <name>,' or '**Notes for defect reviewers**'")
        audiences.append(audience)

    if kind == "assessment":
        if not blocks:
            violations.append(
                "kind: an assessment must contain at least a "
                "'**Notes for defect reviewers**' block")
        if "submitter" in audiences:
            violations.append(
                "kind: an assessment must not contain a 'Hello …,' submitter "
                "block — submitter requests are ask comments")
        if "developer" in audiences:
            violations.append(
                "kind: an assessment must not contain a '**Notes for "
                "developer**' block — give reviewers only what the "
                "disposition decision needs; code-adjacent pointers go to "
                "the ANALYSIS")
        if audiences and audiences[0] not in ("reviewers", ""):
            violations.append(
                "kind: the first assessment block must be "
                "'**Notes for defect reviewers**'")
        lines = [ln.strip() for ln in text.split("\n")]
        dispo = [i for i, ln in enumerate(lines) if _DISPOSITION_RE.match(ln)]
        if not dispo:
            violations.append(
                "disposition: an assessment must contain a "
                "'**Proposed disposition:** …' line")
        else:
            trailing = [name for ln in lines[dispo[0] + 1:]
                        for name in _OTHER_SECTIONS if ln.startswith(f"**{name}")]
            if trailing:
                violations.append(
                    "order: '**Proposed disposition**' must be the LAST "
                    f"section of the reviewers block — move '{trailing[0]}' "
                    "above it")
        wc = word_count("\n".join(blocks))
        if wc > ASSESS_WORDS:
            violations.append(
                f"words: {wc} exceeds the assessment ceiling {ASSESS_WORDS}")
        return violations

    # kind == "ask"
    if len(blocks) != 1 or (audiences and audiences[0] not in ("submitter", "")):
        violations.append(
            "kind: an ask comment is exactly one block addressed to the "
            "submitter ('Hello <name>,') — no reviewer/developer blocks")
    asks = split_asks(text)
    if len(asks) > MAX_ASKS:
        violations.append(f"asks: {len(asks)} numbered asks exceed the max {MAX_ASKS}")
    nums = [int(re.match(r"^(\d+)", a).group(1)) for a in asks]
    if nums != list(range(1, len(nums) + 1)):
        violations.append(
            f"numbering: asks numbered {nums}, expected "
            f"{list(range(1, len(nums) + 1))} — renumber contiguously from 1")
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
    wc = word_count("\n".join(blocks))
    if wc > ceiling:
        violations.append(f"words: {wc} exceeds the ask ceiling {ceiling}")
    return violations


def _freshness_line(updated: str) -> str:
    ts = datetime.strptime(updated, "%Y-%m-%dT%H:%M:%S.%f%z")
    return ("_Reflects the ticket as of "
            f"{ts.astimezone(timezone.utc).strftime('%Y-%m-%d %H:%M')} UTC_")


def ensure_header(text: str, marker: str, kind: str, updated: str = None) -> str:
    """Compose the code-owned header: `<marker> — <label>`, then (for an
    assessment with `updated` given) the freshness line, then the AI
    disclaimer line, then the `---` rule. Replaces any existing marker line
    (LLM-freelanced suffixes included) and any stale freshness/disclaimer
    line. Idempotent."""
    header = f"{marker} — {LABELS[kind]}"
    lines = text.split("\n")
    i = 0
    while i < len(lines) and not lines[i].strip():
        i += 1
    body = lines[i:]
    if body and body[0].lstrip().startswith(marker):
        body = body[1:]
        while body and not body[0].strip():
            body = body[1:]
        for line_re in (_FRESHNESS_RE, _DISCLAIMER_RE):
            if body and line_re.match(body[0].strip()):
                body = body[1:]
                while body and not body[0].strip():
                    body = body[1:]
    out = [header]
    if kind == "assessment" and updated:
        out.append(_freshness_line(updated))
    out.append(DISCLAIMER)
    if body and _RULE_LINE_RE.match(body[0].strip()):
        out.extend(body)
    else:
        out.extend(["---", ""])
        out.extend(body)
    return "\n".join(out)


def main():
    ap = argparse.ArgumentParser(description="Check a draft comment against the contract.")
    ap.add_argument("file", help="Path to the draft comment (markdown).")
    ap.add_argument("--kind", required=True, choices=("ask", "assessment"))
    ap.add_argument("--marker", default=DEFAULT_MARKER)
    ap.add_argument("--fix-marker", action="store_true",
                    help="Compose the typed header (marker — label, freshness "
                         "line for assessments) in place, before checking.")
    ap.add_argument("--updated", default=None,
                    help="Ticket `updated` ISO timestamp for the assessment "
                         "freshness line (used with --fix-marker).")
    args = ap.parse_args()

    path = Path(args.file)
    text = path.read_text(encoding="utf-8")
    if args.fix_marker:
        fixed = ensure_header(text, args.marker, args.kind, args.updated)
        if fixed != text:
            path.write_text(fixed, encoding="utf-8")
            text = fixed
    violations = check(text, args.kind, args.marker)
    for v in violations:
        print(v)
    sys.exit(1 if violations else 0)


if __name__ == "__main__":
    main()
