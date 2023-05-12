from gql.dsl import DSLSchema

from pydrawise import schema


def test_get_schema():
    sc = DSLSchema(schema.get_schema())
    # Make sure these exist in the schema.
    assert "'Query'" in repr(sc.Query)
    assert "'Mutation'" in repr(sc.Mutation)
