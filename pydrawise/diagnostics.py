"""Redacted data dumps, for bug reports and Home Assistant diagnostics."""

from __future__ import annotations

from collections.abc import Iterable, Mapping, Sequence, Set
from dataclasses import Field, fields, is_dataclass
from datetime import date, datetime, time, timedelta
from enum import Enum
from typing import Any, Final

from .schema import _SENSITIVE_FIELD_METADATA

#: Placeholder substituted for the value of every sensitive field.
REDACTED: Final = "**REDACTED**"


def redacted_dump(obj: Any, *, extra_redact: Iterable[str] = ()) -> Any:
    """Converts an object into a JSON-serializable dump, minus sensitive data.

    Walks `obj` recursively, turning dataclasses into dicts keyed by field
    name and converting the non-JSON types used by `pydrawise.schema`:
    `datetime`, `date` and `time` become ISO 8601 strings, a `timedelta`
    becomes its length in seconds, and an `Enum` becomes its value. Containers
    and dataclasses that aren't part of pydrawise are walked too, so a caller
    can pass its own object holding pydrawise objects (a Home Assistant
    coordinator's data, say).

    The value of every field pydrawise considers sensitive -- account identity
    (user id, customer id, name, email) and controller identity (name and
    hardware serial number) -- is replaced with `REDACTED`. Zone and sensor
    names and ids are kept: they're what makes a dump useful for diagnosing a
    scheduling problem, and they aren't account identifying.

    Nothing here reaches the API: the dump is built from objects the caller
    already holds, so it costs no requests against Hydrawise's rate limits.

    :param obj: The object to dump. Typically a `User` or a list of
        `Controller` objects.
    :param extra_redact: Names of additional fields to redact, matched at any
        depth. Useful for callers with a stricter policy than pydrawise's --
        `extra_redact=["name"]` redacts every name in the dump, including zone
        and sensor names.
    :rtype: A JSON-serializable value: a dict for a dataclass or mapping, a
        list for any other container, and a string, number, boolean or None
        for everything else.
    """
    return _dump(obj, frozenset(extra_redact))


def _dump(obj: Any, redact: frozenset[str]) -> Any:
    """Recursive implementation of `redacted_dump`.

    :meta private:
    """
    if obj is None or isinstance(obj, bool | int | float | str):
        return obj
    if isinstance(obj, Enum):
        return _dump(obj.value, redact)
    if isinstance(obj, datetime | date | time):
        return obj.isoformat()
    if isinstance(obj, timedelta):
        return obj.total_seconds()
    if is_dataclass(obj) and not isinstance(obj, type):
        return {f.name: _dump_field(obj, f, redact) for f in fields(obj)}
    if isinstance(obj, Mapping):
        return _dump_mapping(obj, redact)
    if isinstance(obj, Sequence | Set):
        return [_dump(item, redact) for item in obj]
    # Anything else is some type pydrawise doesn't know about. A dump is for
    # reading, so describe it rather than failing to serialize it.
    return str(obj)


def _dump_mapping(obj: Mapping[Any, Any], redact: frozenset[str]) -> dict[Any, Any]:
    """Dumps a mapping, redacting the values of keys named in `redact`.

    `extra_redact` names fields, but it applies to mapping keys too, so that it
    also covers raw JSON -- what `legacy.LegacyHydrawise` exposes -- where
    there is no dataclass field to carry a sensitivity marker.

    :meta private:
    """
    ret = {}
    for key, value in obj.items():
        dumped_key = _dump_key(key, redact)
        ret[dumped_key] = REDACTED if dumped_key in redact else _dump(value, redact)
    return ret


def _dump_field(obj: Any, f: Field[Any], redact: frozenset[str]) -> Any:
    """Dumps a single dataclass field, redacting it if it is sensitive.

    A sensitive field that holds no value stays None rather than becoming
    `REDACTED`: "the API sent nothing here" is worth knowing in a dump and
    discloses nothing.

    :meta private:
    """
    value = getattr(obj, f.name)
    if value is None:
        return None
    if f.metadata.get(_SENSITIVE_FIELD_METADATA) or f.name in redact:
        return REDACTED
    return _dump(value, redact)


def _dump_key(key: Any, redact: frozenset[str]) -> str | int | float | bool | None:
    """Dumps a mapping key, which JSON only allows to be a primitive.

    :meta private:
    """
    dumped = _dump(key, redact)
    if dumped is None or isinstance(dumped, bool | int | float | str):
        return dumped
    return str(dumped)
