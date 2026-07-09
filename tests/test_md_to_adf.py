import jira_utils


def test_paragraphs_split_on_blank_lines():
    doc = jira_utils.md_to_adf("first para\nsame para\n\nsecond para")
    assert doc["type"] == "doc" and doc["version"] == 1
    assert [b["type"] for b in doc["content"]] == ["paragraph", "paragraph"]
    assert doc["content"][0]["content"][0]["text"] == "first para same para"


def test_inline_marks():
    doc = jira_utils.md_to_adf("**bold** and *em* and `code` and [link](https://x.io)")
    nodes = doc["content"][0]["content"]
    marks = [n.get("marks", [{}])[0].get("type") for n in nodes if n.get("marks")]
    assert marks == ["strong", "em", "code", "link"]
    link = [n for n in nodes if n.get("marks", [{}])[0].get("type") == "link"][0]
    assert link["marks"][0]["attrs"]["href"] == "https://x.io"


def test_ordered_list_with_nested_substeps():
    md = "1. Which version: 2.7 or 2.8?\n2. Run the check:\n   1. Open **Method Editor**\n   2. Report what step 1 shows"
    doc = jira_utils.md_to_adf(md)
    top = doc["content"][0]
    assert top["type"] == "orderedList"
    assert len(top["content"]) == 2
    second_item = top["content"][1]
    nested = [c for c in second_item["content"] if c["type"] == "orderedList"]
    assert len(nested) == 1 and len(nested[0]["content"]) == 2


def test_code_block_with_language():
    doc = jira_utils.md_to_adf("```python\nx = 1\n```")
    block = doc["content"][0]
    assert block["type"] == "codeBlock"
    assert block["attrs"] == {"language": "python"}
    assert block["content"][0]["text"] == "x = 1"


def test_heading():
    doc = jira_utils.md_to_adf("## Verdict")
    assert doc["content"][0]["type"] == "heading"
    assert doc["content"][0]["attrs"]["level"] == 2


def test_roundtrip_through_adf_to_md():
    md = "One line status.\n\n1. Which version: 2.7 or 2.8?\n2. Attach the log from `C:\\logs`"
    back = jira_utils.adf_to_md(jira_utils.md_to_adf(md))
    assert "One line status." in back
    assert "Which version: 2.7 or 2.8?" in back
    assert "`C:\\logs`" in back


def test_empty_input_returns_valid_empty_doc():
    assert jira_utils.md_to_adf("") == {"type": "doc", "version": 1, "content": []}


def _walk_text_nodes(node):
    if isinstance(node, dict):
        if node.get("type") == "text":
            yield node
        for child in node.get("content", []) or []:
            yield from _walk_text_nodes(child)


def test_no_empty_text_nodes_from_empty_constructs():
    doc = jira_utils.md_to_adf("- \n\n```\n```\n\n1. real ask")
    assert all(n["text"] for n in _walk_text_nodes(doc))


def _linkify(md: str):
    return jira_utils.linkify_issue_keys(
        jira_utils.md_to_adf(md), "OLAC", "https://x.atlassian.net")


def _texts_and_hrefs(doc):
    out = []
    def walk(n):
        if isinstance(n, list):
            [walk(c) for c in n]
        elif isinstance(n, dict):
            if n.get("type") == "text":
                href = next((m["attrs"]["href"] for m in n.get("marks", [])
                             if m["type"] == "link"), None)
                out.append((n["text"], href))
            walk(n.get("content", []))
    walk(doc)
    return out


def test_linkify_bare_key_in_paragraph():
    doc = _linkify("matches OLAC-1783 exactly")
    assert ("OLAC-1783", "https://x.atlassian.net/browse/OLAC-1783") in _texts_and_hrefs(doc)
    assert ("matches ", None) in _texts_and_hrefs(doc)


def test_linkify_keeps_existing_marks():
    doc = _linkify("see **OLAC-42** now")
    node = [n for n in doc["content"][0]["content"] if n["text"] == "OLAC-42"][0]
    types = [m["type"] for m in node["marks"]]
    assert types == ["strong", "link"]


def test_linkify_skips_code_and_links_and_other_projects():
    doc = _linkify("`OLAC-1` [OLAC-2](https://y.io) CDS2ASV-3 OLAC-4")
    pairs = dict(_texts_and_hrefs(doc))
    assert pairs["OLAC-1"] is None                      # code span untouched
    assert pairs["OLAC-2"] == "https://y.io"            # existing link kept
    assert pairs["OLAC-4"] == "https://x.atlassian.net/browse/OLAC-4"
    assert not any(h and "CDS2ASV" in h for h in pairs.values())  # other project bare


def test_linkify_skips_code_blocks_and_lists_work():
    doc = _linkify("```\nOLAC-9\n```\n\n- fixed by OLAC-10")
    pairs = dict(_texts_and_hrefs(doc))
    assert pairs["OLAC-9"] is None
    assert pairs["OLAC-10"] == "https://x.atlassian.net/browse/OLAC-10"


def _issue_with_comments():
    def adf(text):
        return {"type": "doc", "version": 1, "content": [
            {"type": "paragraph", "content": [{"type": "text", "text": text}]}]}
    return {"key": "CDS2ASV-1", "fields": {
        "summary": "s", "issuetype": {"name": "Defect"},
        "comment": {"comments": [
            {"author": {"displayName": "Human"}, "created": "2026-07-01T00:00:00",
             "body": adf("real analysis")},
            {"author": {"displayName": "Bot"}, "created": "2026-07-02T00:00:00",
             "body": adf("🤖 Automated defect review —\n\nverdict text")},
        ]}}}


def test_ingest_export_omits_bot_comments():
    md = jira_utils.build_issue_md(_issue_with_comments(), "")
    assert "real analysis" in md
    assert "verdict text" not in md
    assert "[automated review comment omitted from ingest]" in md
    assert "**Bot**" in md  # thread flow preserved


def test_print_md_keeps_bot_comments():
    md = jira_utils.build_issue_md(_issue_with_comments(), "",
                                   include_bot_comments=True)
    assert "verdict text" in md
    assert "omitted from ingest" not in md


def test_old_marker_bot_comments_still_omitted_after_marker_change():
    """_comment_is_marked must keep stubbing comments posted under the old
    marker once the default becomes the shorter prefix."""
    md = jira_utils.build_issue_md(_issue_with_comments(), "")
    assert "verdict text" not in md
    assert "[automated review comment omitted from ingest]" in md


def test_rule_from_dashes_line():
    doc = jira_utils.md_to_adf("🤖 Automated defect review\n---\n\nHello Martin,")
    assert [b["type"] for b in doc["content"]] == ["paragraph", "rule", "paragraph"]


def test_rule_roundtrip():
    back = jira_utils.adf_to_md(jira_utils.md_to_adf("above\n\n---\n\nbelow"))
    assert "---" in back


def test_numbered_list_continues_across_blank_lines():
    # The exact CDS2ASV-5460 failure shape: blank lines between asks split the
    # list into three one-item orderedLists, which Jira renders "1. 1. 1.".
    md = ("1. Is it a fresh install?\n"
          "\n"
          "2. Does it fail on every reboot?\n"
          "\n"
          "3. After a reboot where it is stopped:\n"
          "   - Open Event Viewer and note the IDs.\n"
          "   - Reply with the output.\n")
    doc = jira_utils.md_to_adf(md)
    lists = [b for b in doc["content"] if b["type"] == "orderedList"]
    assert len(lists) == 1
    assert len(lists[0]["content"]) == 3
    nested = [c for c in lists[0]["content"][2]["content"] if c["type"] == "bulletList"]
    assert len(nested) == 1 and len(nested[0]["content"]) == 2


def test_blank_line_before_different_list_kind_stays_separate():
    # An ordered list followed by a blank line and a top-level bullet list is
    # two lists, not one merged orderedList.
    doc = jira_utils.md_to_adf("1. one\n2. two\n\n- bullet a\n- bullet b")
    assert [b["type"] for b in doc["content"]] == ["orderedList", "bulletList"]


def test_one_space_indent_drift_stays_flat_across_blank_line():
    doc = jira_utils.md_to_adf("1. one\n\n 2. two")
    lists = [b for b in doc["content"] if b["type"] == "orderedList"]
    assert len(lists) == 1
    assert len(lists[0]["content"]) == 2
    item_one = lists[0]["content"][0]
    assert all(c["type"] != "orderedList" for c in item_one["content"])


def test_one_space_indent_drift_stays_flat_consecutive():
    doc = jira_utils.md_to_adf("1. one\n 2. two")
    top = doc["content"][0]
    assert top["type"] == "orderedList"
    assert len(top["content"]) == 2
