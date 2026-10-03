"""Utilities for managing the GraphQL schema."""

from __future__ import annotations

from collections import namedtuple
from collections.abc import Iterator
from dataclasses import fields, is_dataclass
from functools import cache
from types import NoneType, UnionType
from typing import (
    TYPE_CHECKING,
    Any,
    Union,
    get_args,
    get_origin,
    get_type_hints,
)

from gql.dsl import DSLField, DSLInlineFragment
from pydantic import TypeAdapter

from .schema import DSL_SCHEMA, _graphql_type_name, _WireType

if TYPE_CHECKING:
    from _typeshed import DataclassInstance

#: Field metadata key: leave this field out of generated GraphQL selections.
SKIP_FIELD_METADATA = "pydrawise_skip_field"


@cache
def _adapter(cls: Any) -> TypeAdapter[Any]:
    """Returns a cached validator for the given type.

    Building a TypeAdapter compiles a validator, which is far too expensive to
    repeat on every API response.

    :meta private:
    """
    return TypeAdapter(cls)


def deserialize(cls: Any, payload: Any) -> Any:
    """Deserializes a GraphQL JSON blob.

    :meta private:
    """
    return _adapter(cls).validate_python(payload)


_Field = namedtuple("_Field", ["name", "types"])


def _wire_type(annotation: Any) -> Any | None:
    """Returns the GraphQL type an annotation deserializes from, if it differs.

    Looks through union wrappers: `ZoneStatus.suspended_until` is spelled
    `_GqlDateTime | None`, but still selects the `DateTime` object's fields.

    :meta private:
    """
    for metadata in getattr(annotation, "__metadata__", ()):
        if isinstance(metadata, _WireType):
            return metadata.graphql_type
    if get_origin(annotation) in (Union, UnionType):
        for arg in get_args(annotation):
            if (found := _wire_type(arg)) is not None:
                return found
    return None


def _fields(
    cls: DataclassInstance | type[DataclassInstance], skip: list[str]
) -> Iterator[_Field]:
    """Returns _Field objects for every field on the given dataclass.

    :meta private:
    """
    hints = get_type_hints(cls)
    # The same hints with their Annotated metadata left on, which is where a
    # field records the GraphQL type it deserializes from.
    annotated_hints = get_type_hints(cls, include_extras=True)
    for f in fields(cls):
        if f.name in skip:
            continue

        if f.metadata.get(SKIP_FIELD_METADATA):
            continue

        if (wire_type := _wire_type(annotated_hints[f.name])) is not None:
            yield _Field(f.name, [wire_type])
            continue

        field_type = hints[f.name]
        origin = get_origin(field_type)

        # `X | Y` and `Union[X, Y]` do not report the same origin: before
        # Python 3.14 the former is types.UnionType and only the latter is
        # typing.Union. Both spellings appear in schema.py, and matching only
        # typing.Union silently emitted union fields with no sub-selection.
        if origin is Union or origin is UnionType:
            # Drop None from Optional fields. Declaration order is kept so the
            # inline fragments a union expands into -- and therefore the query
            # text we send -- are stable across processes.
            field_types = [t for t in get_args(field_type) if t is not NoneType]

            # Actual unions just yield the union.
            if len(field_types) > 1:
                yield _Field(f.name, field_types)
                continue

            # If we have only one type left after dropping None, this could
            # still be a list. Perform the normal extraction routine.
            [field_type] = field_types
            origin = get_origin(field_type)

        if origin is list:
            # Extract the contained type.
            # We assume all list types are uniform.
            [field_type] = get_args(field_type)

        yield _Field(f.name, [field_type])


@cache
def _get_selectors_cached(
    cls: type[DataclassInstance],
    skip_fields: tuple[str, ...],
) -> tuple[DSLField, ...]:
    """Cached implementation of get_selectors.

    Uses a tuple for skip_fields to allow LRU caching with hashable arguments.

    :meta private:
    """
    ret = []
    skip_now, skip_later = parse_skip(list(skip_fields))
    for f in _fields(cls, skip_now):
        dsl_field = getattr(getattr(DSL_SCHEMA, _graphql_type_name(cls)), f.name)
        if len(f.types) == 1:
            [f_type] = f.types
            if is_dataclass(f_type):
                f_skip = tuple(skip_later.get(f.name, []))
                ret.append(dsl_field.select(*_get_selectors_cached(f_type, f_skip)))  # type: ignore[arg-type]
            else:
                ret.append(dsl_field)
        else:
            # This is a Union; we must pass an inline fragment for each type.
            sel_args = []
            for f_type in f.types:
                if not is_dataclass(f_type):
                    raise NotImplementedError
                sel_args.append(
                    DSLInlineFragment()
                    .on(getattr(DSL_SCHEMA, _graphql_type_name(f_type)))
                    .select(*_get_selectors_cached(f_type, ()))  # type: ignore[arg-type]
                )
            ret.append(dsl_field.select(*sel_args))
    return tuple(ret)


def get_selectors(
    cls: DataclassInstance | type[DataclassInstance],
    skip_fields: list[str] | None = None,
) -> list[DSLField]:
    """Constructs GraphQL selectors for the given dataclass.

    :meta private:
    """
    cls_type = cls if isinstance(cls, type) else type(cls)
    return list(_get_selectors_cached(cls_type, tuple(skip_fields or [])))


def parse_skip(skip: list[str] | None = None) -> tuple[list[str], dict[str, list[str]]]:
    """Converts a flat list of skip fields into (skip_now, skip_later).

    skip_now is a list of fields in the current scope to skip.
    skip_later is a list of descendant fields to skip.

    :meta private:
    """
    now: list[str] = []
    later: dict[str, list[str]] = {}
    for item in skip or []:
        field, _, descendants = item.partition(".")
        if descendants:
            later.setdefault(field, []).append(descendants)
        else:
            now.append(field)
    return now, later
