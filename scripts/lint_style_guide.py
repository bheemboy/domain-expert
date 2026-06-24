#!/usr/bin/env python3
"""lint_style_guide.py — deterministic genericity guard for the bundled style guide.

Enforces the "100% generic" contract (Plan 2): no vendor/product tokens, no
dropped rule IDs, no invented house values (brand colors, dropped resolution),
and unique stable R-<CATEGORY>-NN rule IDs. Pure stdlib. Exit 0 = clean,
1 = findings printed. Mirrors lint_wiki.py's deterministic-check convention.
"""

import os
import re
import sys
from pathlib import Path

# Vendor / product tokens that must never appear in a generic guide.
# Case-sensitive with word boundaries so "the system" / "decide" don't match.
_VENDOR = [
    r"\bAgilent\b", r"\bOpenL[Aa]b\b", r"\bCID\b", r"\bAIC\b", r"\bFlex[Nn]et\b",
    r"\bCockpit\b", r"\bCorporate NIC\b", r"\bHouse NIC\b", r"\bAllow Changes\b",
    r"\bSYSTEM\b", r"\bSetup\.exe\b", r"\bOLS-", r"\bNET-", r"\bCAR-",
]
_VENDOR_RE = [re.compile(p) for p in _VENDOR]

# Invented house values dropped by the disposition.
_FORBIDDEN_STR = [r"#0073B7", r"#D32F2F", r"1920\s*[x×]\s*1080"]
_FORBIDDEN_RE = [re.compile(p, re.IGNORECASE) for p in _FORBIDDEN_STR]

# Rule IDs dropped by the disposition (must not appear anywhere in the guide).
_DROPPED_ID_RE = re.compile(r"\bR-REVIEW-\d+\b|\bR-LINK-0[678]\b|\bR-LIST-07\b")

# A rule definition line: "- **R-CAT-NN:** ...". Used for the uniqueness check.
_RULE_DEF_RE = re.compile(r"\*\*(R-[A-Z0-9]+-\d+)\*\*|\*\*(R-[A-Z0-9]+-\d+):")


def lint_text(rel: str, text: str) -> list[str]:
    """Per-file findings (vendor tokens, forbidden values, dropped IDs)."""
    out: list[str] = []
    for i, line in enumerate(text.splitlines(), start=1):
        for rx in _VENDOR_RE:
            m = rx.search(line)
            if m:
                out.append(f"{rel}:{i}: vendor token '{m.group(0)}' — replace with a generic example")
        for rx in _FORBIDDEN_RE:
            m = rx.search(line)
            if m:
                out.append(f"{rel}:{i}: forbidden house value '{m.group(0)}'")
        for m in _DROPPED_ID_RE.finditer(line):
            out.append(f"{rel}:{i}: dropped rule id '{m.group(0)}' must not appear")
    return out


def _rule_def_ids(text: str) -> list[str]:
    ids: list[str] = []
    for line in text.splitlines():
        m = _RULE_DEF_RE.search(line)
        if m:
            ids.append(m.group(1) or m.group(2))
    return ids


def lint_dir(root: Path) -> list[str]:
    """All per-file findings plus cross-file duplicate-rule-ID findings."""
    out: list[str] = []
    seen: dict[str, str] = {}
    for path in sorted(root.rglob("*.md")):
        rel = path.relative_to(root).as_posix()
        text = path.read_text(encoding="utf-8")
        out.extend(lint_text(rel, text))
        for rid in _rule_def_ids(text):
            if rid in seen:
                out.append(f"{rel}: duplicate rule id '{rid}' (also defined in {seen[rid]})")
            else:
                seen[rid] = rel
    return out


def main() -> int:
    root = Path(os.environ.get("STYLE_GUIDE_DIR")
                or (Path(__file__).resolve().parent.parent / "style-guide"))
    if not root.is_dir():
        print(f"no style-guide dir at {root}", file=sys.stderr)
        return 1
    findings = lint_dir(root)
    for f in findings:
        print(f)
    print(f"\n{len(findings)} finding(s)." if findings else "style-guide: clean.")
    return 1 if findings else 0


if __name__ == "__main__":
    raise SystemExit(main())
