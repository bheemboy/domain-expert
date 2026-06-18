import importlib

import ingest_state


def test_is_doc():
    assert ingest_state.is_doc("docs/report.PDF") is True
    assert ingest_state.is_doc("a/deck.pptx") is True
    assert ingest_state.is_doc("readme.md") is False
    assert ingest_state.is_doc("main.py") is False


def test_doc_key_shape_and_stability():
    k = ingest_state.doc_key("docs/specs/Big Design.pdf")
    assert k.startswith("doc__")
    parts = k.split("__")
    assert len(parts) == 3            # doc__<slug>__<hash8>
    assert parts[1] == "big-design"   # slugified stem, lowercase
    assert len(parts[2]) == 8         # short hash
    assert ingest_state.doc_key("docs/specs/Big Design.pdf") == k


def test_doc_key_distinguishes_same_name_different_path():
    a = ingest_state.doc_key("teamA/report.pdf")
    b = ingest_state.doc_key("teamB/report.pdf")
    assert a != b                     # same stem, different hash
    assert a.split("__")[1] == b.split("__")[1] == "report"


def test_key_of_dispatch_jira():
    assert ingest_state.key_of("jira-export-cds2asv-846-story.md") == "CDS2ASV-846"


def test_key_of_dispatch_doc():
    assert ingest_state.key_of("docs/report.pdf") == ingest_state.doc_key("docs/report.pdf")


def test_key_of_text_has_no_key():
    import pytest
    with pytest.raises(ValueError):
        ingest_state.key_of("src/main.py")
