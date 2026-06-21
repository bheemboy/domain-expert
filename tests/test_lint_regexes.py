from pathlib import Path

import lint_wiki


def test_flaggable_noun_matches_generic_and_brand():
    assert lint_wiki._FLAGGABLE_NOUN_RE.search("the Report page")
    assert lint_wiki._FLAGGABLE_NOUN_RE.search("Host-ASV-Instrument")
    assert lint_wiki._FLAGGABLE_NOUN_RE.search("Host-QualA-Instrument")


def test_era_qualifier_matches_brand_and_generic():
    assert lint_wiki._ERA_QUALIFIER_RE.search("this was ASV 1.0 behaviour")
    assert lint_wiki._ERA_QUALIFIER_RE.search("CA era only")
    assert lint_wiki._ERA_QUALIFIER_RE.search("formerly known as X")   # generic, built-in
    assert lint_wiki._ERA_QUALIFIER_RE.search("legacy path")            # generic, built-in


def test_deictic_matches_context_dependent_phrases():
    assert lint_wiki._DEICTIC_RE.search("The pump stops in this state.")
    assert lint_wiki._DEICTIC_RE.search("In that case the gate stays closed.")
    assert lint_wiki._DEICTIC_RE.search("Configure it as described above.")
    assert lint_wiki._DEICTIC_RE.search("AS SHOWN BELOW, the flag flips")  # case-insensitive
    # Bare nouns / unrelated prose must not match.
    assert not lint_wiki._DEICTIC_RE.search("The state machine resets on boot.")
    assert not lint_wiki._DEICTIC_RE.search("This case study covers the API.")


def test_resolving_link_matches_followable_references():
    assert lint_wiki._RESOLVING_LINK_RE.search("see [[error-handling]]")
    assert lint_wiki._RESOLVING_LINK_RE.search("([details](#errors))")
    assert lint_wiki._RESOLVING_LINK_RE.search("([details](../ops/gate.md))")
    # Sibling/absolute markdown links and bare external URLs are NOT recognised.
    assert not lint_wiki._RESOLVING_LINK_RE.search("([details](gate.md))")
    assert not lint_wiki._RESOLVING_LINK_RE.search("see https://example.com")


def _warns(text):
    p = Path("page.md")
    return lint_wiki._context_dependent_refs([p], {p: text})


def test_context_dependent_refs_flags_unlinked_deixis():
    assert _warns("The pump stops in this state.")


def test_context_dependent_refs_silent_when_resolving_link_present():
    assert not _warns("The pump stops in this state, see [[error-handling]].")
    assert not _warns("The pump stops in this state ([why](#errors)).")


def test_context_dependent_refs_skips_frontmatter_and_fences():
    assert not _warns("---\nnote: in this state\n---\nClean body line.")
    assert not _warns("```\nif x:  # in this state\n```")
