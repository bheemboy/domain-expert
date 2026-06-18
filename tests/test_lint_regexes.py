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
