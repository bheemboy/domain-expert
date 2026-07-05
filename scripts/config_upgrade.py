"""config_upgrade.py — append missing optional blocks to wiki.config.yaml.

The upgrade path for the checked-in config is APPEND-ONLY: existing lines are
never modified, reordered, uncommented, or filled in. A block counts as
present when a top-level `<key>:` line exists, active or commented — the
repo's version then wins unconditionally. Absent blocks are appended in their
commented, inert template form (the contiguous comment run around `# <key>:`,
explanatory paragraph included).

Deterministic — the LLM's role is to show the dry-run output and get the
human's confirmation, never to edit the config itself.

Usage (from a wiki repo, or with $WIKI_CONFIG set):
  python config_upgrade.py            # dry-run: print what would be appended
  python config_upgrade.py --write    # append, then print what was appended
"""

import argparse
import re
import sys
from pathlib import Path

import config

OPTIONAL_BLOCKS = ["docs", "synth_tuning", "ignore", "defect_review"]

_TEMPLATE_PATH = (
    Path(__file__).resolve().parent.parent
    / "skills" / "wiki-init" / "templates" / "wiki.config.yaml.tmpl"
)


def block_present(config_text: str, key: str) -> bool:
    """True when a top-level `<key>:` line exists, active or commented.

    Anchored at column 0 so nested keys and prose mentions don't count.
    """
    return re.search(rf"^(?:#\s*)?{re.escape(key)}\s*:", config_text, re.MULTILINE) is not None


def extract_block(template_text: str, key: str) -> str:
    """The full contiguous comment run containing `# <key>:` in the template.

    Optional template blocks are single runs of `#`-prefixed lines (the
    explanatory paragraph flows straight into the commented keys), so the
    block is the whole run around the key line. Refuses placeholder leakage:
    optional blocks must be render-free.
    """
    lines = template_text.split("\n")
    key_re = re.compile(rf"^#\s*{re.escape(key)}\s*:")
    idx = next((i for i, ln in enumerate(lines) if key_re.match(ln)), None)
    if idx is None:
        raise SystemExit(f"template has no commented block for {key!r}: {_TEMPLATE_PATH}")
    start = idx
    while start > 0 and lines[start - 1].startswith("#"):
        start -= 1
    end = idx
    while end + 1 < len(lines) and lines[end + 1].startswith("#"):
        end += 1
    block = "\n".join(lines[start:end + 1])
    if "{{" in block:
        raise SystemExit(f"template block {key!r} contains unrendered placeholders")
    return block


def missing_blocks(config_text: str, template_text: str) -> list:
    """[(key, block)] for every optional block absent from the config."""
    return [
        (key, extract_block(template_text, key))
        for key in OPTIONAL_BLOCKS
        if not block_present(config_text, key)
    ]


def append_missing(config_path: Path, template_text: str) -> list:
    """Append every missing optional block to the config file. Returns what
    was appended as [(key, block)]; the existing content is never altered."""
    text = config_path.read_text(encoding="utf-8")
    missing = missing_blocks(text, template_text)
    if not missing:
        return []
    parts = [text if text.endswith("\n") else text + "\n"]
    for _, block in missing:
        parts.append("\n" + block + "\n")
    config_path.write_text("".join(parts), encoding="utf-8")
    return missing


def main():
    ap = argparse.ArgumentParser(
        description="Append missing optional blocks (commented, inert) to wiki.config.yaml.")
    ap.add_argument("--write", action="store_true",
                    help="Apply the append. Default is a dry-run that only prints.")
    args = ap.parse_args()

    config_path = config.config_path()
    template_text = _TEMPLATE_PATH.read_text(encoding="utf-8")
    if args.write:
        appended = append_missing(config_path, template_text)
        if not appended:
            print("all optional blocks present — nothing appended.")
            return
        print(f"appended to {config_path}:")
        for key, _ in appended:
            print(f"  {key}")
        return

    missing = missing_blocks(config_path.read_text(encoding="utf-8"), template_text)
    if not missing:
        print("all optional blocks present — nothing to append.")
        return
    print(f"would append to {config_path} (run with --write to apply):\n", file=sys.stderr)
    for _, block in missing:
        print(block)
        print()


if __name__ == "__main__":
    main()
