import os
import re
import sys
import json
import hashlib
import argparse
import tempfile
import requests
from datetime import datetime, timezone
from pathlib import Path
import config as _config

# ─────────────────────────────────────────────
# CONFIG (Jira Cloud)
# ─────────────────────────────────────────────
# Cloud uses HTTP Basic auth: <email>:<API token>. Generate an API token at
# https://id.atlassian.com/manage-profile/security/api-tokens and export:
#     export JIRA_EMAIL=you@example.com
#     export JIRA_TOKEN=<api-token>
# Env var still wins (handy for one-off overrides); otherwise read from wiki.config.yaml.
# JIRA_BASE_URL is the site URL (human /browse links); JIRA_API_BASE_URL is where
# REST calls go — differs only for scoped tokens (api.atlassian.com/ex/jira/<cloudId>).
JIRA_BASE_URL = os.getenv("JIRA_BASE_URL") or _config.jira_base_url()
JIRA_API_BASE_URL = os.getenv("JIRA_API_BASE_URL") or _config.jira_api_base_url()

CREDS_FILE = _config.config_dir() / "jira.token"


def load_credentials(path: Path = CREDS_FILE) -> tuple[str, str]:
    """Return (email, token). Prefer the chmod-600 creds file; fall back to env vars."""
    email = os.getenv("JIRA_EMAIL", "")
    token = os.getenv("JIRA_TOKEN", "")
    if path.is_file():
        for line in path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            k, v = line.split("=", 1)
            k, v = k.strip(), v.strip()
            if k == "JIRA_EMAIL":
                email = v
            elif k == "JIRA_TOKEN":
                token = v
    return email, token


# Backwards-compatible module-level values (read once at import).
JIRA_EMAIL, JIRA_TOKEN = load_credentials()


def get_headers() -> dict:
    return {
        "Content-Type": "application/json",
        "Accept": "application/json",
    }


def get_auth() -> tuple:
    """HTTP Basic auth tuple for Jira Cloud (email + API token)."""
    return load_credentials()


def require_credentials() -> None:
    if not JIRA_EMAIL:
        print("Error: JIRA_EMAIL not set. Export your Atlassian account email.")
        sys.exit(1)
    if not JIRA_TOKEN or JIRA_TOKEN == "your_api_token":
        print("Error: JIRA_TOKEN not set. Export a Cloud API token.")
        sys.exit(1)


# ─────────────────────────────────────────────
# ADF (Atlassian Document Format) → Markdown
# ─────────────────────────────────────────────
# Jira Cloud REST v3 returns rich text (description, comment bodies) as ADF
# JSON rather than wiki markup. The functions below convert that JSON tree
# into Markdown. Unknown node/mark types degrade gracefully to their text.


def adf_to_md(node) -> str:
    """Convert an ADF document (dict) to Markdown. Accepts None or a plain
    string (some legacy fields) and returns it unchanged."""
    if not node:
        return ""
    if isinstance(node, str):
        return node.replace("\xa0", " ").strip()
    if not isinstance(node, dict):
        return str(node)
    return _render_nodes(node.get("content", [])).strip()


def _render_nodes(nodes) -> str:
    blocks = []
    for n in nodes or []:
        rendered = _render_block(n)
        if rendered:
            blocks.append(rendered)
    return "\n\n".join(blocks)


def _render_block(node, list_depth: int = 0) -> str:
    t = node.get("type")
    if t == "paragraph":
        return _render_inline(node.get("content", []))
    if t == "heading":
        level = (node.get("attrs") or {}).get("level", 1)
        return "#" * int(level) + " " + _render_inline(node.get("content", []))
    if t in ("bulletList", "orderedList"):
        return "\n".join(_render_list_lines(node, t == "orderedList", list_depth))
    if t == "codeBlock":
        lang = (node.get("attrs") or {}).get("language") or ""
        return f"```{lang}\n{_plain_text(node.get('content', []))}\n```"
    if t == "blockquote":
        return _prefix_lines(_render_nodes(node.get("content", [])), "> ")
    if t == "panel":
        ptype = (node.get("attrs") or {}).get("panelType", "info")
        body = _prefix_lines(_render_nodes(node.get("content", [])), "> ")
        return f"> **{str(ptype).capitalize()}**\n>\n{body}"
    if t == "rule":
        return "---"
    if t in ("mediaSingle", "mediaGroup"):
        return _render_media(node)
    if t == "media":
        return _render_media({"content": [node]})
    if t == "table":
        return _render_table(node)
    if t in ("expand", "nestedExpand"):
        title = (node.get("attrs") or {}).get("title", "Details")
        return f"**{title}**\n\n{_render_nodes(node.get('content', []))}"
    # Unknown block: fall back to rendering any children.
    if node.get("content"):
        return _render_nodes(node.get("content", []))
    return ""


def _render_list_lines(node, ordered: bool, depth: int) -> list:
    lines: list[str] = []
    indent = "  " * depth
    idx = 1
    for item in node.get("content", []):
        if item.get("type") != "listItem":
            continue
        marker = f"{idx}." if ordered else "-"
        first_done = False
        for child in item.get("content", []):
            ct = child.get("type")
            if ct in ("bulletList", "orderedList"):
                lines.extend(_render_list_lines(child, ct == "orderedList", depth + 1))
            else:
                block = _render_block(child, list_depth=depth)
                for ln in block.split("\n"):
                    if not first_done:
                        lines.append(f"{indent}{marker} {ln}")
                        first_done = True
                    else:
                        lines.append(f"{indent}  {ln}")
        if not first_done:
            lines.append(f"{indent}{marker} ")
        idx += 1
    return lines


def _render_inline(nodes) -> str:
    parts = []
    for n in nodes or []:
        t = n.get("type")
        if t == "text":
            parts.append(_apply_marks(n.get("text", ""), n.get("marks", [])))
        elif t == "hardBreak":
            parts.append("\n")
        elif t == "mention":
            txt = (n.get("attrs") or {}).get("text", "")
            parts.append("@" + txt.lstrip("@") if txt else "@user")
        elif t == "emoji":
            attrs = n.get("attrs") or {}
            parts.append(attrs.get("text") or attrs.get("shortName") or "")
        elif t == "inlineCard":
            url = (n.get("attrs") or {}).get("url", "")
            parts.append(f"<{url}>" if url else "")
        elif t == "date":
            ts = (n.get("attrs") or {}).get("timestamp")
            try:
                parts.append(
                    datetime.fromtimestamp(int(ts) / 1000, tz=timezone.utc).strftime("%Y-%m-%d")
                    if ts else ""
                )
            except (ValueError, TypeError):
                parts.append("")
        elif n.get("content"):
            parts.append(_render_inline(n.get("content", [])))
    return "".join(parts)


def _apply_marks(text: str, marks) -> str:
    if not text:
        return text
    href = None
    is_code = False
    fmt = set()
    for m in marks or []:
        mt = m.get("type")
        if mt == "code":
            is_code = True
        elif mt in ("strong", "em", "strike", "underline"):
            fmt.add(mt)
        elif mt == "link":
            href = (m.get("attrs") or {}).get("href")
    if is_code:
        text = f"`{text}`"
    else:
        if "strike" in fmt:
            text = f"~~{text}~~"
        if "strong" in fmt:
            text = f"**{text}**"
        if "em" in fmt:
            text = f"*{text}*"
        if "underline" in fmt:
            text = f"<u>{text}</u>"
    if href:
        text = f"[{text}]({href})"
    return text


def _plain_text(nodes) -> str:
    out = []
    for n in nodes or []:
        if n.get("type") == "text":
            out.append(n.get("text", ""))
        elif n.get("type") == "hardBreak":
            out.append("\n")
        elif n.get("content"):
            out.append(_plain_text(n.get("content", [])))
    return "".join(out)


def _render_media(node) -> str:
    items = []
    for child in node.get("content", []):
        if child.get("type") == "media":
            attrs = child.get("attrs") or {}
            alt = attrs.get("alt") or attrs.get("id") or "media"
            items.append(f"![{alt}]({alt})")
    return "\n".join(items)


def _render_table(node) -> str:
    rows = []
    for row in node.get("content", []):
        if row.get("type") != "tableRow":
            continue
        cells = []
        for cell in row.get("content", []):
            cells.append(_render_nodes(cell.get("content", [])).replace("\n", " ").strip())
        rows.append(cells)
    if not rows:
        return ""
    header = rows[0]
    lines = [
        "| " + " | ".join(header) + " |",
        "| " + " | ".join(["---"] * len(header)) + " |",
    ]
    for r in rows[1:]:
        r = r + [""] * (len(header) - len(r))
        lines.append("| " + " | ".join(r) + " |")
    return "\n".join(lines)


def _prefix_lines(text: str, prefix: str) -> str:
    return "\n".join((prefix + line) if line else prefix.rstrip() for line in text.split("\n"))


# ─────────────────────────────────────────────
# Markdown → ADF (comment posting)
# ─────────────────────────────────────────────
# Inverse of adf_to_md for the pragmatic subset review comments need:
# paragraphs, headings, bullet/ordered lists (one nesting level), fenced code,
# and inline bold/italic/code/links. Unknown constructs degrade to plain text.

_MD_INLINE_RE = re.compile(
    r"\*\*(?P<strong>.+?)\*\*"
    r"|\*(?P<em>.+?)\*"
    r"|`(?P<code>[^`]+)`"
    r"|\[(?P<ltext>[^\]]+)\]\((?P<lurl>[^)\s]+)\)"
)

_MD_LIST_ITEM_RE = re.compile(r"^(?P<indent>\s*)(?P<marker>-|\d+[.)])\s+(?P<text>.*)$")

_MD_RULE_RE = re.compile(r"^-{3,}\s*$")


def _adf_text_node(text: str, marks: list | None = None) -> dict:
    node = {"type": "text", "text": text}
    if marks:
        node["marks"] = marks
    return node


def _md_inline_nodes(text: str) -> list:
    nodes, pos = [], 0
    for m in _MD_INLINE_RE.finditer(text):
        if m.start() > pos:
            nodes.append(_adf_text_node(text[pos:m.start()]))
        if m.group("strong") is not None:
            nodes.append(_adf_text_node(m.group("strong"), [{"type": "strong"}]))
        elif m.group("em") is not None:
            nodes.append(_adf_text_node(m.group("em"), [{"type": "em"}]))
        elif m.group("code") is not None:
            nodes.append(_adf_text_node(m.group("code"), [{"type": "code"}]))
        else:
            nodes.append(_adf_text_node(
                m.group("ltext"),
                [{"type": "link", "attrs": {"href": m.group("lurl")}}],
            ))
        pos = m.end()
    if pos < len(text):
        nodes.append(_adf_text_node(text[pos:]))
    return nodes


def _collect_md_list(lines: list, i: int) -> tuple:
    """Collect consecutive list items. A blank-line gap does NOT end the list
    when the next non-blank line is another item that is nested (deeper
    indent) or of the same kind (ordered/bullet) at top level — authors put
    blank lines between numbered asks, and splitting there makes Jira render
    every item as "1."."""
    items = []
    top_indent = top_ordered = None
    while i < len(lines):
        m = _MD_LIST_ITEM_RE.match(lines[i])
        if m:
            if top_indent is None:
                top_indent = len(m.group("indent"))
                top_ordered = m.group("marker") != "-"
            items.append((len(m.group("indent")), m.group("marker"), m.group("text")))
            i += 1
            continue
        if lines[i].strip():
            break
        j = i
        while j < len(lines) and not lines[j].strip():
            j += 1
        m2 = _MD_LIST_ITEM_RE.match(lines[j]) if j < len(lines) else None
        if not m2:
            break
        if len(m2.group("indent")) >= top_indent + 2 or (m2.group("marker") != "-") == top_ordered:
            i = j
            continue
        break
    return items, i


def _build_md_list(items: list) -> dict:
    """(indent, marker, text) tuples → ADF list; deeper indents nest one level."""
    top_indent = items[0][0]
    ordered = items[0][1] != "-"
    node = {"type": "orderedList" if ordered else "bulletList", "content": []}
    idx = 0
    while idx < len(items):
        _, _, text = items[idx]
        item = {"type": "listItem",
                "content": [{"type": "paragraph", "content": _md_inline_nodes(text)}]}
        idx += 1
        sub = []
        # ≥2 spaces past the parent = nested (same convention as
        # comment_contract._SUBSTEP_RE); 1 space is drift, not nesting
        while idx < len(items) and items[idx][0] >= top_indent + 2:
            sub.append(items[idx])
            idx += 1
        if sub:
            item["content"].append(_build_md_list(sub))
        node["content"].append(item)
    return node


def linkify_issue_keys(node, project_key: str, base_url: str):
    """Make bare <project_key>-<n> references in an ADF tree clickable
    (link marks to <base_url>/browse/<KEY>). Post-time and mechanical, so it
    applies however the comment was written. Skips code blocks, code spans,
    and text that already carries a link. Scoped to the wiki's own project
    key so key-shaped strings (UTF-8, SHA-256) can never false-match."""
    if isinstance(node, list):
        out = []
        for child in node:
            r = linkify_issue_keys(child, project_key, base_url)
            out.extend(r) if isinstance(r, list) else out.append(r)
        return out
    if not isinstance(node, dict) or node.get("type") == "codeBlock":
        return node
    if node.get("type") == "text":
        marks = node.get("marks") or []
        if any(m.get("type") in ("link", "code") for m in marks):
            return node
        text = node["text"]
        pieces, pos = [], 0
        for m in re.finditer(rf"\b{re.escape(project_key)}-\d+\b", text):
            if m.start() > pos:
                pieces.append(_adf_text_node(text[pos:m.start()], marks or None))
            href = f"{base_url}/browse/{m.group(0)}"
            pieces.append(_adf_text_node(
                m.group(0), marks + [{"type": "link", "attrs": {"href": href}}]))
            pos = m.end()
        if not pieces:
            return node
        if pos < len(text):
            pieces.append(_adf_text_node(text[pos:], marks or None))
        return pieces
    if "content" in node:
        node = dict(node)
        node["content"] = linkify_issue_keys(node["content"], project_key, base_url)
    return node


def md_to_adf(md: str) -> dict:
    """Markdown → ADF document for the review-comment subset (see section
    comment). Always returns a valid `doc` node, empty input included."""
    lines = (md or "").replace("\r\n", "\n").split("\n")
    blocks: list = []
    para: list = []

    def flush_para():
        if para:
            blocks.append({"type": "paragraph",
                           "content": _md_inline_nodes(" ".join(para))})
            para.clear()

    i = 0
    while i < len(lines):
        stripped = lines[i].strip()
        if not stripped:
            flush_para()
            i += 1
            continue
        if stripped.startswith("```"):
            flush_para()
            lang = stripped[3:].strip()
            code = []
            i += 1
            while i < len(lines) and not lines[i].strip().startswith("```"):
                code.append(lines[i])
                i += 1
            i += 1  # move past the closing fence (or EOF when the fence is unclosed)
            code_text = "\n".join(code)
            block = {"type": "codeBlock"}
            if code_text:
                block["content"] = [{"type": "text", "text": code_text}]
            if lang:
                block["attrs"] = {"language": lang}
            blocks.append(block)
            continue
        m = re.match(r"^(#{1,6})\s+(.*)$", stripped)
        if m:
            flush_para()
            blocks.append({"type": "heading", "attrs": {"level": len(m.group(1))},
                           "content": _md_inline_nodes(m.group(2))})
            i += 1
            continue
        if _MD_RULE_RE.match(stripped):
            flush_para()
            blocks.append({"type": "rule"})
            i += 1
            continue
        if _MD_LIST_ITEM_RE.match(lines[i]):
            flush_para()
            items, i = _collect_md_list(lines, i)
            blocks.append(_build_md_list(items))
            continue
        para.append(stripped)
        i += 1
    flush_para()
    return {"type": "doc", "version": 1, "content": blocks}


# ─────────────────────────────────────────────
# WRITE PATHS (defect review) — notify email + comment
# ─────────────────────────────────────────────
# The plugin's only Jira writes. Failures are LOUD (SystemExit with status and
# response body) and never fall back: a rejected notify must not degrade into
# posting a comment.


def resolve_account_id(user: str) -> str:
    """Jira Cloud notify/mention targets need an accountId. Pass an accountId
    through untouched; resolve an email via user search."""
    if "@" not in user:
        return user
    url = f"{JIRA_API_BASE_URL}/rest/api/3/user/search"
    resp = requests.get(url, params={"query": user},
                        headers=get_headers(), auth=get_auth())
    resp.raise_for_status()
    users = resp.json()
    if not users:
        raise SystemExit(f"no Jira user found for {user!r}")
    return users[0]["accountId"]


def build_notify_payload(subject: str, body_text: str, account_id: str) -> dict:
    return {
        "subject": subject,
        "textBody": body_text,
        "to": {"users": [{"accountId": account_id}]},
    }


def notify_issue(key: str, subject: str, body_text: str, to_user: str) -> None:
    """Email `to_user` about issue `key` via Jira's notify API. Leaves no trace
    on the ticket."""
    payload = build_notify_payload(subject, body_text, resolve_account_id(to_user))
    url = f"{JIRA_API_BASE_URL}/rest/api/3/issue/{key}/notify"
    resp = requests.post(url, headers=get_headers(), auth=get_auth(), json=payload)
    if resp.status_code >= 300:
        raise SystemExit(
            f"notify {key} failed: HTTP {resp.status_code}: {resp.text[:500]}"
        )


def post_comment(key: str, markdown_body: str) -> None:
    """Post `markdown_body` (converted to ADF, bare same-project issue keys
    linkified) as a comment on `key`."""
    body = linkify_issue_keys(
        md_to_adf(markdown_body), _config.project_key(), JIRA_BASE_URL)
    url = f"{JIRA_API_BASE_URL}/rest/api/3/issue/{key}/comment"
    resp = requests.post(url, headers=get_headers(), auth=get_auth(),
                         json={"body": body})
    if resp.status_code >= 300:
        raise SystemExit(
            f"comment on {key} failed: HTTP {resp.status_code}: {resp.text[:500]}"
        )


# ─────────────────────────────────────────────
# FIELD RESOLUTION
# ─────────────────────────────────────────────
# Custom field IDs are instance-specific and change on a Server→Cloud
# migration. Resolve them by display name at runtime instead of hard-coding.

_FIELD_CACHE = None


def get_all_fields() -> list:
    global _FIELD_CACHE
    if _FIELD_CACHE is None:
        url = f"{JIRA_API_BASE_URL}/rest/api/3/field"
        resp = requests.get(url, headers=get_headers(), auth=get_auth())
        resp.raise_for_status()
        _FIELD_CACHE = resp.json()
    return _FIELD_CACHE


def resolve_field_id(name: str, default=None):
    for fld in get_all_fields():
        if (fld.get("name") or "").lower() == name.lower():
            return fld.get("id")
    return default


def resolve_epic_link_field() -> str:
    """Return the field that carries an issue's epic. Migrated company-managed
    projects keep an 'Epic Link' custom field; otherwise Cloud uses native
    'parent'."""
    return resolve_field_id("Epic Link", default="parent")


def _epic_ref(fields: dict, epic_link_field: str) -> str:
    val = fields.get(epic_link_field) if epic_link_field else None
    if isinstance(val, str) and val:
        return val
    if isinstance(val, dict) and val.get("key"):
        return val["key"]
    parent = fields.get("parent")
    if isinstance(parent, dict) and parent.get("key"):
        return parent["key"]
    return ""


# ─────────────────────────────────────────────
# FORMATTING
# ─────────────────────────────────────────────


def format_links(links: list, issue_type: str) -> str:
    lines = []
    for link in links:
        if "outwardIssue" in link:
            rel = link.get("type", {}).get("outward", "links to")
            tgt = link["outwardIssue"]
        elif "inwardIssue" in link:
            rel = link.get("type", {}).get("inward", "is linked by")
            tgt = link["inwardIssue"]
        else:
            continue

        tgt_key = tgt.get("key", "")
        tgt_type = (tgt.get("fields") or {}).get("issuetype", {}).get("name", "Unknown")
        tgt_summary = (tgt.get("fields") or {}).get("summary", "")

        # Simplify test linkages
        if "test" in rel.lower():
            if issue_type.lower() == "test":
                rel = "Tests"
            else:
                rel = "Tested by"
        elif "clone" in rel.lower():
            rel = "Clones" if "outward" in link else "Is cloned by"

        lines.append(f"- **{rel.capitalize()}**: `{tgt_key}` ({tgt_type}) — {tgt_summary}")

    if lines:
        return "- " + "\n- ".join(line[2:] for line in lines)
    return ""


def format_comment(comment: dict) -> str:
    author = (comment.get("author") or {}).get("displayName", "Unknown")
    created = comment.get("created", "")[:10]
    body = adf_to_md(comment.get("body"))
    return f"**{author}** _{created}_\n\n{body}"


def _comment_is_marked(comment: dict, marker: str) -> bool:
    return adf_to_md(comment.get("body")).lstrip().startswith(marker)


def format_comments(comments: list, include_bot_comments: bool) -> str:
    """Render a ticket's comment thread. By default the reviewer bot's own
    marker comments are reduced to an omission stub: ingest must not feed the
    bot's generated hypotheses back into the wiki it grounds itself in (a
    wrong assessment would launder itself into ground truth). The
    defect-review skill opts in to the full thread via
    `--print-md --include-bot-comments` — the brain has to see what it
    already said."""
    marker = _config.defect_review_config()["marker"]
    parts = []
    for c in comments:
        if not include_bot_comments and marker and _comment_is_marked(c, marker):
            author = (c.get("author") or {}).get("displayName", "Unknown")
            created = c.get("created", "")[:10]
            parts.append(f"**{author}** _{created}_\n\n"
                         "_[automated review comment omitted from ingest]_")
        else:
            parts.append(format_comment(c))
    return "\n\n---\n\n".join(parts)


def format_fix_versions(fix_versions: list) -> str:
    names = [v.get("name", "") for v in fix_versions if v.get("name")]
    return ", ".join(names) if names else "—"


# ─────────────────────────────────────────────
# ATTACHMENTS
# ─────────────────────────────────────────────


def _human_size(num) -> str:
    num = float(num or 0)
    for unit in ("B", "KB", "MB", "GB"):
        if num < 1024 or unit == "GB":
            return f"{num:.0f} {unit}" if unit == "B" else f"{num:.1f} {unit}"
        num /= 1024
    return f"{num:.1f} GB"


def format_attachments(attachments: list, issue_key: str) -> str:
    """Markdown manifest of an issue's attachments. Files are not downloaded;
    each line carries the type/size metadata plus the authenticated content URL
    so the extraction step can fetch a file on demand if it decides the
    contents are worth reading."""
    if not attachments:
        return ""
    lines = []
    for att in attachments:
        fname = att.get("filename", "attachment")
        url = att.get("content", "")
        mime = att.get("mimeType", "")
        author = (att.get("author") or {}).get("displayName", "Unknown")
        created = (att.get("created", "") or "")[:10]
        meta = ", ".join(p for p in (_human_size(att.get("size")), mime, author, created) if p)
        link = f"[{fname}]({url})" if url else fname
        lines.append(f"- {link} — {meta}")
    return "\n".join(lines)


def download_attachments(
    issue: dict,
    dest_root: Path,
    exts: set[str] | None = None,
    list_only: bool = False,
    force: bool = False,
) -> list[Path]:
    """Download an issue's attachments to ``dest_root/<ISSUE-KEY>/<filename>``.

    Attachment metadata (including the authenticated ``content`` URL) comes from
    the already-fetched issue, so no extra API call is needed. The wiki ingest
    uses this to actually read images/PDFs rather than just their URLs. Downloaded
    files are raw sources — treat them as immutable. Existing files are skipped
    unless ``force``. Returns the local paths written or already present.
    """
    key = issue.get("key", "UNKNOWN")
    attachments = (issue.get("fields") or {}).get("attachment") or []
    if not attachments:
        print(f"{key}: no attachments.")
        return []

    out_dir = dest_root / key
    print(f"{key}: {len(attachments)} attachment(s) → {out_dir}")
    written: list[Path] = []

    for att in attachments:
        fname = att.get("filename", "attachment")
        ext = fname.rsplit(".", 1)[-1].lower() if "." in fname else ""
        if exts and ext not in exts:
            print(f"  skip (ext) : {fname}")
            continue
        if list_only:
            print(f"  would get  : {fname} ({_human_size(att.get('size'))}, {att.get('mimeType', '')})")
            continue
        dest = out_dir / fname
        if dest.exists() and not force:
            print(f"  exists     : {fname}")
            written.append(dest)
            continue
        # Rebuild the download URL from the attachment id: the payload's
        # `content` URL points at the site, which scoped tokens can't
        # authenticate against (only the api.atlassian.com gateway).
        att_id = att.get("id", "")
        content_url = (
            f"{JIRA_API_BASE_URL}/rest/api/3/attachment/content/{att_id}"
            if att_id else att.get("content", "")
        )
        if not content_url:
            print(f"  no url     : {fname}")
            continue
        resp = requests.get(content_url, auth=get_auth(), timeout=120)
        resp.raise_for_status()
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes(resp.content)
        print(f"  downloaded : {fname} ({len(resp.content)} bytes)")
        written.append(dest)

    return written


# ─────────────────────────────────────────────
# FETCH (Jira Cloud REST v3 — /search/jql cursor pagination)
# ─────────────────────────────────────────────


def fetch_issues(jql: str, epic_link_field: str = "") -> list:
    fields = [
        "summary",
        "description",
        "issuetype",
        "status",
        "fixVersions",
        "comment",
        "resolution",
        "resolutiondate",
        "issuelinks",
        "updated",
        "parent",
        "attachment",
        "reporter",
    ]
    if epic_link_field and epic_link_field not in fields:
        fields.append(epic_link_field)

    url = f"{JIRA_API_BASE_URL}/rest/api/3/search/jql"
    issues = []
    next_token = None
    while True:
        payload = {
            "jql": jql,
            "maxResults": 100,
            "fields": fields,
        }
        if next_token:
            payload["nextPageToken"] = next_token
        resp = requests.post(url, headers=get_headers(), auth=get_auth(), json=payload)
        resp.raise_for_status()
        data = resp.json()
        issues.extend(data.get("issues", []))
        next_token = data.get("nextPageToken")
        if not next_token or data.get("isLast"):
            break
    return issues


def build_issue_md(issue: dict, epic_link_field: str,
                   include_bot_comments: bool = False) -> str:
    f = issue.get("fields") or {}
    key = issue.get("key", "")
    issue_type = (f.get("issuetype") or {}).get("name", "Unknown")
    summary = f.get("summary", "_No summary_")
    description = adf_to_md(f.get("description"))
    status_name = (f.get("status") or {}).get("name", "")
    resolution = (f.get("resolution") or {}).get("name", "Unresolved")
    reporter = (f.get("reporter") or {}).get("displayName", "—") or "—"
    fix_versions = format_fix_versions(f.get("fixVersions") or [])
    epic_link = _epic_ref(f, epic_link_field)
    updated_iso = (f.get("updated") or "").strip()
    updated_disp = updated_iso[:19].replace("T", " ") if updated_iso else "—"
    now_utc = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    links_md = format_links(f.get("issuelinks") or [], issue_type)
    attachments_md = format_attachments(f.get("attachment") or [], key)
    comments = (f.get("comment") or {}).get("comments", [])
    comments_md = format_comments(comments, include_bot_comments)
    lines = [
        f"# {key} — {summary}",
        "",
        f"> **Exported**: {now_utc}  ",
        f"> **Source**: `{JIRA_BASE_URL}/browse/{key}`",
        "",
        "---",
        "",
        "## Metadata",
        "",
        "| Field | Value |",
        "|-------|-------|",
        f"| **Key** | `{key}` |",
        f"| **Issue Type** | {issue_type} |",
        f"| **Reporter** | {reporter} |",
        f"| **Status** | {status_name} |",
        f"| **Resolution** | {resolution} |",
        f"| **Fix Version/s** | {fix_versions} |",
        f"| **Epic Link** | {epic_link or '—'} |",
        f"| **Updated** | {updated_disp} |",
        "",
        "---",
        "",
        "## Summary",
        "",
        summary,
        "",
        "---",
        "",
        "## Description",
        "",
        description,
    ]
    if links_md:
        lines.extend([
            "",
            "---",
            "",
            "## Links",
            "",
            links_md,
        ])
    if attachments_md:
        lines.extend([
            "",
            "---",
            "",
            "## Attachments",
            "",
            attachments_md,
        ])
    if comments_md:
        lines.extend([
            "",
            "---",
            "",
            "## Comments",
            "",
            comments_md,
        ])
    lines.append("")
    return "\n".join(lines)


# ─────────────────────────────────────────────
# CONTENT EQUIVALENCE (ignore dynamic export metadata)
# ─────────────────────────────────────────────


def get_substantive_content(md_text: str) -> str:
    """
    Extracts only the substantive parts of the Jira export (Title, Summary,
    Description, and Comments) by removing the dynamic metadata and export headers.
    """
    # Remove the Exported/Source header block
    text = re.sub(r"> \*\*Exported\*\*:.*?> \*\*Source\*\*:.*?\n+", "", md_text, flags=re.DOTALL)

    # Remove the entire Metadata section and the horizontal rules around it
    text = re.sub(r"---\s*\n\s*## Metadata\s*\n\s*\|.*?\|\s*\n\s*---\s*\n", "", text, flags=re.DOTALL)

    # Remove link label spelling variations (e.g. "Tested by" vs "Is tested by")
    text = re.sub(r"^- \*\*(?:is\s+)?([^*]+)\*\*:", r"- **\1**:", text, flags=re.MULTILINE | re.IGNORECASE)

    # Collapse all whitespace/newlines to a single space
    return re.sub(r"\s+", " ", text).strip()


def content_hash(md_text: str) -> str:
    """sha256 of the substantive ticket content (title/summary/description/comments).

    Volatile metadata (export header, Metadata table) is stripped first, so bulk
    maintenance updates that don't touch substance produce an unchanged hash.
    """
    return hashlib.sha256(
        get_substantive_content(md_text).encode("utf-8")
    ).hexdigest()


def export_content_equivalent(a: str, b: str) -> bool:
    return get_substantive_content(a) == get_substantive_content(b)


def _rendered_md_for(key: str, include_bot_comments: bool = False) -> str:
    """Fetch one issue by KEY and render it to export-equivalent markdown."""
    epic_link_field = resolve_epic_link_field()
    issues = fetch_issues(f"key = {key}", epic_link_field)
    if not issues:
        raise SystemExit(f"{key}: not found or not accessible")
    return build_issue_md(issues[0], epic_link_field,
                          include_bot_comments=include_bot_comments)


def stamp_digest_hash(key: str, digest_path: Path) -> None:
    """Compute the live content_hash for KEY and write it into the digest frontmatter.

    Inserts `content_hash:` after the `key:` line, or replaces an existing one.
    Deterministic — never run by the LLM.
    """
    h = content_hash(_rendered_md_for(key))
    text = digest_path.read_text(encoding="utf-8")
    line = f"content_hash: {h}"
    if re.search(r"^content_hash\s*:.*$", text, re.MULTILINE):
        new = re.sub(r"^content_hash\s*:.*$", line, text, count=1, flags=re.MULTILINE)
    else:
        new = re.sub(r"(^key\s*:.*$)", r"\1\n" + line, text, count=1, flags=re.MULTILINE)
    if new != text:
        digest_path.write_text(new, encoding="utf-8")


# ─────────────────────────────────────────────
# CLI
# ─────────────────────────────────────────────


def _default_export_root() -> Path:
    """Default base for --export / --attachments output. A system temp dir, NOT the
    repo — these standalone export commands are not part of the /ingest flow (which
    uses --print-md + --attachments-dir /tmp/jira-<KEY>), so their output must never
    land inside the wiki repo. Override with --out-dir / --attachments-dir."""
    return Path(tempfile.gettempdir()) / "wiki-jira-exports"


def main():
    parser = argparse.ArgumentParser(description="A utility to fetch, inspect, and export Jira issues.")
    parser.add_argument("issue_keys", metavar="ISSUE_KEYS", nargs="*", help="One or more specific Jira issue keys to fetch (e.g., OLAC-7328).")
    parser.add_argument("--jql", help="Fetch issues matching a specific JQL query instead of individual keys.")
    parser.add_argument("--export", action="store_true", help="Format the issues as Markdown and save them under a temp export dir (see --out-dir).")
    parser.add_argument("--raw", action="store_true", help="Print the raw JSON payload from Jira instead of the formatted summary/comments.")
    parser.add_argument("--out-dir", type=str, help="Override the default export directory (a system temp dir).")
    parser.add_argument("--attachments", action="store_true", help="Download each issue's attachments to <export-dir>/assets/<KEY>/.")
    parser.add_argument("--list-attachments", action="store_true", help="List each issue's attachments without downloading.")
    parser.add_argument("--attachments-ext", type=str, help="Comma-separated extensions to limit attachment downloads (e.g. png,pdf).")
    parser.add_argument("--force", action="store_true", help="Re-download attachments even if the local file already exists.")
    parser.add_argument("--print-md", action="store_true", help="Fetch one KEY and print its markdown to stdout (writes no file). Automated-review comments are omitted unless --include-bot-comments.")
    parser.add_argument("--include-bot-comments", action="store_true", help="Render the reviewer bot's marker comments in full instead of an omission stub. The defect-review skill needs this; ingest must not use it.")
    parser.add_argument("--stamp-hash", action="store_true", help="Compute content_hash for KEY and write it into raw/imports/jira/<KEY>.md.")
    parser.add_argument("--attachments-dir", type=str, help="Directory to download attachments into (overrides the default assets root).")
    parser.add_argument("--notify", action="store_true", help="Send a Jira notify email about each KEY (requires --subject, --body-file, --to). Writes nothing to the ticket.")
    parser.add_argument("--post-comment", action="store_true", help="Post --body-file (markdown) as a comment on each KEY.")
    parser.add_argument("--subject", type=str, help="Subject line for --notify.")
    parser.add_argument("--body-file", type=str, help="Path to the markdown body for --notify / --post-comment.")
    parser.add_argument("--to", dest="to_user", type=str, help="Recipient for --notify: accountId or email.")
    args = parser.parse_args()

    if not args.issue_keys and not args.jql:
        parser.print_help()
        sys.exit(1)

    if args.print_md:
        require_credentials()
        for key in args.issue_keys:
            sys.stdout.write(_rendered_md_for(
                key, include_bot_comments=args.include_bot_comments))
        return
    if args.stamp_hash:
        require_credentials()
        imports_jira = Path(os.environ.get("IMPORTS_DIR", "raw/imports")) / "jira"
        for key in args.issue_keys:
            stamp_digest_hash(key, imports_jira / f"{key}.md")
            print(f"stamped {key}")
        return

    if args.notify or args.post_comment:
        require_credentials()
        if not args.issue_keys or not args.body_file:
            parser.error("--notify/--post-comment require ISSUE_KEYS and --body-file")
        body = Path(args.body_file).read_text(encoding="utf-8")
        for key in args.issue_keys:
            if args.notify:
                if not (args.subject and args.to_user):
                    parser.error("--notify requires --subject and --to")
                notify_issue(key, args.subject, body, args.to_user)
                print(f"notified {args.to_user} about {key}")
            if args.post_comment:
                post_comment(key, body)
                print(f"commented on {key}")
        return

    require_credentials()

    if args.jql:
        jql = args.jql
    else:
        jql = f"key in ({','.join(args.issue_keys)})"

    try:
        epic_link_field = resolve_epic_link_field()
        issues = fetch_issues(jql, epic_link_field)
    except requests.HTTPError as exc:
        print(f"\nERROR: HTTP {exc.response.status_code} from Jira search API.")
        print(f"  Response: {exc.response.text[:500]}")
        sys.exit(1)
    except Exception as e:
        print(f"Failed to fetch issues: {e}")
        sys.exit(1)

    if not issues:
        print("No issues found.")
        sys.exit(0)

    if args.attachments_dir:
        assets_root = Path(args.attachments_dir)
    else:
        assets_root = (Path(args.out_dir) if args.out_dir else _default_export_root()) / "assets"
    att_exts = (
        {e.strip().lower() for e in args.attachments_ext.split(",") if e.strip()}
        if args.attachments_ext
        else None
    )

    for issue in issues:
        if args.raw:
            print(json.dumps(issue, indent=2))
            continue

        if args.attachments or args.list_attachments:
            download_attachments(
                issue, assets_root,
                exts=att_exts, list_only=args.list_attachments, force=args.force,
            )
            # Attachments-only mode: don't also dump the markdown.
            if not args.export:
                continue

        md_content = build_issue_md(issue, epic_link_field)

        if args.export:
            # Save it to <export-dir>/YYYY/..., keyed on the close (resolution)
            # date so the filename stays stable across re-exports.
            fields = issue.get("fields") or {}
            closed_iso = (fields.get("resolutiondate") or "") or (fields.get("updated") or "")
            year = closed_iso[:4] if closed_iso else datetime.now(timezone.utc).strftime("%Y")
            closed_compact = re.sub(r"[^\d]", "", closed_iso[:16]) if closed_iso else datetime.now(timezone.utc).strftime("%Y%m%d%H%M")
            key = issue.get("key", "").lower()
            issue_type = (fields.get("issuetype") or {}).get("name", "unknown").lower()

            export_dir = (Path(args.out_dir) if args.out_dir else _default_export_root()) / year
            export_dir.mkdir(parents=True, exist_ok=True)

            filename = f"{closed_compact}-{key}-{issue_type}.md"
            filepath = export_dir / filename

            filepath.write_text(md_content, encoding="utf-8")
            print(f"Exported {issue['key']} to {filepath}")
        else:
            print(md_content)
            print("\n" + "=" * 80 + "\n")


if __name__ == "__main__":
    main()
