import ignore


def test_double_star_prefix_matches_any_depth():
    assert ignore.first_match("a/b/c.min.js", ["**/*.min.js"]) == "**/*.min.js"
    assert ignore.first_match("c.min.js", ["**/*.min.js"]) == "**/*.min.js"


def test_single_star_does_not_cross_slash():
    # *.js (no **/) only matches at the root, one segment
    assert ignore.first_match("x.js", ["*.js"]) == "*.js"
    assert ignore.first_match("a/x.js", ["*.js"]) is None


def test_subtree_glob_matches_everything_under_dir():
    g = "ac_portal/local_modules/**"
    assert ignore.first_match("ac_portal/local_modules/@agilent/common/x.js", [g]) == g
    assert ignore.first_match("ac_portal/src/app/main.ts", [g]) is None


def test_question_mark_matches_one_non_slash_char():
    assert ignore.first_match("ab.ts", ["a?.ts"]) == "a?.ts"
    assert ignore.first_match("a/b.ts", ["a?.ts"]) is None


def test_no_match_returns_none():
    assert ignore.first_match("ac_server/model/user.py", ["**/*.min.js", "**/*.svg"]) is None


def test_partition_keeps_order_and_tallies_by_rule():
    paths = ["a.py", "b.min.js", "c.svg", "d.py", "e.min.js"]
    globs = ["**/*.min.js", "**/*.svg"]
    kept, ignored = ignore.partition(paths, globs)
    assert kept == ["a.py", "d.py"]
    assert ignored == {"**/*.min.js": 2, "**/*.svg": 1}


def test_first_match_is_first_glob_in_order():
    # a path matching two globs is attributed to the first listed
    kept, ignored = ignore.partition(["x.css"], ["**/*.css", "**/*.css"])
    assert kept == []
    assert ignored == {"**/*.css": 1}
