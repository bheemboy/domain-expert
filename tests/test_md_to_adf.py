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
