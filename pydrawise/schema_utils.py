"""Utilities for managing the GraphQL schema."""

from __future__ import annotations

from collections import namedtuple
from dataclasses import fields, is_dataclass
from functools import lru_cache
from typing import (
    TYPE_CHECKING,
    Iterator,
    List,
    Union,
    get_args,
    get_origin,
    get_type_hints,
)

from apischema import deserialize as _deserialize
from apischema.metadata.keys import CONVERSION_METADATA, SKIP_METADATA
from apischema.type_names import get_type_name
from apischema.utils import to_camel_case
from gql.dsl import DSLField, DSLInlineFragment

from .schema import DSL_SCHEMA

if TYPE_CHECKING:
    from _typeshed import DataclassInstance

# For compatibility with < python 3.10.
NoneType = type(None)


def deserialize(*args, **kwargs):
    """Deserializes a GraphQL JSON blob.

    :meta private:
    """
    kwargs.setdefault("aliaser", to_camel_case)
    return _deserialize(*args, **kwargs)


_Field = namedtuple("_Field", ["name", "types"])


def _fields(
    cls: DataclassInstance | type[DataclassInstance], skip: list[str]
) -> Iterator[_Field]:
    """Returns _Field objects for every field on the given dataclass.

    :meta private:
    """
    hints = get_type_hints(cls)
    for f in fields(cls):
        if f.name in skip:
            continue

        if (skip_md := f.metadata.get(SKIP_METADATA, None)) and (
            skip_md.serialization or skip_md.deserialization
        ):
            continue

        if conversion_md := f.metadata.get(CONVERSION_METADATA, None):
            yield _Field(f.name, [conversion_md.deserialization.source])
            continue

        field_type = hints[f.name]
        origin = get_origin(field_type)

        if origin == Union:
            # Drop None from Optional fields.
            field_types = set(get_args(field_type)) - {NoneType}

            # Actual unions just yield the union.
            if len(field_types) > 1:
                yield _Field(f.name, list(field_types))
                continue

            # If we have only one type left after dropping None, this could
            # still be a list. Perform the normal extraction routine.
            [field_type] = field_types
            origin = get_origin(field_type)

        if origin in (List, list):
            # Extract the contained type.
            # We assume all list types are uniform.
            [field_type] = get_args(field_type)

        yield _Field(f.name, [field_type])


@lru_cache(maxsize=None)
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
        dsl_field = getattr(getattr(DSL_SCHEMA, get_type_name(cls).graphql), f.name)  # type: ignore[arg-type]
        if len(f.types) == 1:
            [f_type] = f.types
            if is_dataclass(f_type):
                f_skip = tuple(skip_later.get(f.name, []))
                ret.append(dsl_field.select(*_get_selectors_cached(f_type, f_skip)))
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
                    .on(getattr(DSL_SCHEMA, get_type_name(f_type).graphql))  # type: ignore[arg-type]
                    .select(*_get_selectors_cached(f_type, ()))
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
