from graphql import InlineFragmentNode

from pydrawise import schema_utils
from pydrawise.schema import Controller, User, Zone


def test_parse_skip():
    skip = ["a", "b.c", "b.d", "e.f.g"]
    want = ["a"], {"b": ["c", "d"], "e": ["f.g"]}
    assert schema_utils.parse_skip(skip) == want


def test_parse_skip_empty():
    assert schema_utils.parse_skip([]) == ([], {})
    assert schema_utils.parse_skip(None) == ([], {})


def _field_names(selectors):
    """GraphQL field names for a selection set.

    Top-level selectors are DSLField objects whose .name is a string; nested
    ones are graphql-core FieldNodes whose .name is a NameNode.
    """
    return [s.name if isinstance(s.name, str) else s.name.value for s in selectors]


def test_get_selectors_includes_all_fields_by_default():
    names = _field_names(schema_utils.get_selectors(Zone))
    assert "id" in names
    assert "name" in names
    assert "scheduledRuns" in names


def test_get_selectors_accepts_an_instance():
    """get_selectors takes either a dataclass or an instance of one."""
    assert _field_names(schema_utils.get_selectors(Zone())) == _field_names(
        schema_utils.get_selectors(Zone)
    )


def test_get_selectors_skips_named_fields():
    names = _field_names(schema_utils.get_selectors(Zone, ["scheduledRuns"]))
    assert "scheduledRuns" in names, (
        "skip matches the dataclass field name, not the alias"
    )

    names = _field_names(schema_utils.get_selectors(Zone, ["scheduled_runs"]))
    assert "scheduledRuns" not in names
    assert "id" in names


def test_get_selectors_skips_descendant_fields_only_under_their_parent():
    """A dotted skip prunes a field inside one subtree, leaving siblings alone."""
    controllers = next(
        s
        for s in schema_utils.get_selectors(User, ["controllers.zones"])
        if s.name == "controllers"
    )
    assert "zones" not in _field_names(controllers.selection_set.selections)

    # Without the skip, the same subtree keeps the field.
    controllers = next(
        s for s in schema_utils.get_selectors(User) if s.name == "controllers"
    )
    assert "zones" in _field_names(controllers.selection_set.selections)


def test_get_selectors_expands_unions_into_inline_fragments():
    """Zone.watering_settings is a Union, so it selects one fragment per member."""
    settings = next(
        s for s in schema_utils.get_selectors(Zone) if s.name == "wateringSettings"
    )
    selections = settings.selection_set.selections
    assert all(isinstance(s, InlineFragmentNode) for s in selections)
    type_names = {
        s.type_condition.name.value
        for s in selections
        if isinstance(s, InlineFragmentNode)
    }
    assert type_names == {"AdvancedWateringSettings", "StandardWateringSettings"}


def test_get_selectors_is_cached_per_skip_list():
    """Identical calls reuse the cache; a different skip list does not."""
    first = schema_utils.get_selectors(Controller)
    assert schema_utils.get_selectors(Controller) == first
    assert schema_utils.get_selectors(Controller, ["zones"]) != first
