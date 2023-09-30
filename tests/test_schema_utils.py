from pydrawise import schema_utils


def test_parse_skip():
    skip = ["a", "b.c", "b.d", "e.f.g"]
    want = ["a"], {"b": ["c", "d"], "e": ["f.g"]}
    assert schema_utils.parse_skip(skip) == want
