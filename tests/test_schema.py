from dataclasses import fields, is_dataclass
from pathlib import Path
from string import ascii_lowercase

from apischema.metadata.keys import CONVERSION_METADATA, FALL_BACK_ON_DEFAULT_METADATA
from apischema.type_names import get_type_name
from apischema.utils import to_camel_case
from graphql import build_schema
from graphql.type import GraphQLBoolean, GraphQLInt, GraphQLNonNull, GraphQLString

from pydrawise import schema as _schema


def test_valid_schema():
    root = Path(__file__).parent.parent
    with open(Path(f"{root}/pydrawise/hydrawise.graphql")) as f:
        schema_str = f.read()

    gql_schema = build_schema(schema_str)

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
            assert fname in st.fields, f"{name}.{f.name} is not a valid field"
            sf = st.fields[fname]

            want_optional = False
            if isinstance(sf.type, GraphQLNonNull):
                stype = sf.type.of_type
            else:
                stype = sf.type
                want_optional = FALL_BACK_ON_DEFAULT_METADATA not in f.metadata
                assert (
                    FALL_BACK_ON_DEFAULT_METADATA in f.metadata or "Optional" in f.type
                ), f"{name}.{f.name} should be optional"

            type_map = {
                GraphQLBoolean: "bool",
                GraphQLInt: "int",
                GraphQLString: "str",
            }
            if stype not in type_map:
                continue
            want_type = type_map[stype]
            if want_optional:
                want_type = f"Optional[{want_type}]"
            got_type = f.type
            if md := f.metadata.get(CONVERSION_METADATA):
                assert md.deserialization is not None
                # TODO: Validate the source type.
                # got_type = md.deserialization.source
                continue
            assert (
                got_type == want_type
            ), f"{name}.{f.name} is {got_type}, want {want_type}"
