from dataclasses import fields, is_dataclass
from pathlib import Path
from string import ascii_lowercase

from apischema.type_names import get_type_name
from apischema.utils import to_camel_case
from graphql import build_schema
from graphql.type import GraphQLNonNull

from pydrawise import schema as _schema


def test_valid_schema():
    root = Path(__file__).parent.parent
    with open(Path(f"{root}/pydrawise/hydrawise.graphql")) as f:
        schema_str = f.read()

    gql_schema = build_schema(schema_str)
    # print(schema.get_type("User"))

    import pdb

    for k, v in vars(_schema).items():
        if k.startswith("_") or k.startswith(ascii_lowercase):
            # Ignore private types
            continue
        if getattr(v, "_pydrawise_type", False):
            # Ignore internal types
            continue
        if not is_dataclass(v):
            # Only look at dataclass types
            continue
        if not (name := get_type_name(v).graphql):
            # Ignore types that are not graphql types.
            continue

        st = gql_schema.get_type(name)
        assert st is not None, f"{name} not found in schema"
        for f in fields(v):
            if f.name.startswith("_"):
                # Ignore private fields.
                continue
            fname = to_camel_case(f.name)
            assert fname in st.fields, f"{f.name} is not a valid field"
            sf = st.fields[fname]
            if not isinstance(sf.type, GraphQLNonNull):
                assert "Optional" in f.type, f"{name}.{f.name} should be optional"
