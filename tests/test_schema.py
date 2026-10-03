from dataclasses import fields, is_dataclass
from datetime import datetime, time
from string import ascii_lowercase
from types import UnionType
from typing import Union, get_args, get_origin, get_type_hints

import pytest
from graphql import build_schema
from graphql.type import (
    GraphQLBoolean,
    GraphQLInt,
    GraphQLInterfaceType,
    GraphQLNonNull,
    GraphQLObjectType,
    GraphQLString,
)
from pydantic import ValidationError
from pydantic.alias_generators import to_camel

from pydrawise import schema as _schema
from pydrawise.schema import (
    _OPTIONAL_FIELD_METADATA,
    SelectedOption,
    Zone,
    ZoneStatus,
    _graphql_type_name,
)
from pydrawise.schema_utils import deserialize


def _is_converted(annotation) -> bool:
    """Whether a field deserializes through a converter.

    Such a field's Python type deliberately differs from its GraphQL type
    (a `timedelta` from an Int, say), so the scalar type comparison below
    doesn't apply to it.
    """
    if getattr(annotation, "__metadata__", ()):
        return True
    if get_origin(annotation) in (Union, UnionType):
        return any(_is_converted(arg) for arg in get_args(annotation))
    return False


def test_valid_schema():
    gql_schema = build_schema(_schema.SCHEMA_TEXT)

    for k, v in vars(_schema).items():
        if k.startswith(("_", *ascii_lowercase)):
            # Ignore private types
            continue
        if getattr(v, "_pydrawise_type", False):
            # Ignore internal types
            continue
        if not is_dataclass(v):
            # Only look at dataclass types
            continue
        if v.__module__ != _schema.__name__:
            # Ignore dataclasses imported from elsewhere (pydantic's
            # BeforeValidator, say) that happen to be in this namespace.
            continue
        name = _graphql_type_name(v)
        annotated_hints = get_type_hints(v, include_extras=True)

        st = gql_schema.get_type(name)
        assert st is not None, f"{name} not found in schema"
        # Every dataclass in schema.py maps to a GraphQL type that has fields --
        # an object type, or an interface such as Program. The isinstance check
        # both documents that and gives `st.fields` a type.
        assert isinstance(st, GraphQLObjectType | GraphQLInterfaceType), (
            f"{name} has no fields"
        )
        for f in fields(v):
            if f.name.startswith("_"):
                # Ignore private fields.
                continue
            fname = to_camel(f.name)
            assert fname in st.fields, f"{name}.{f.name} is not a valid field"
            sf = st.fields[fname]

            want_optional = False
            if isinstance(sf.type, GraphQLNonNull):
                stype = sf.type.of_type
            else:
                stype = sf.type
                is_optional_field = bool(f.metadata.get(_OPTIONAL_FIELD_METADATA))
                want_optional = not is_optional_field
                assert is_optional_field or "Optional" in f.type or "None" in f.type, (
                    f"{name}.{f.name} should be optional"
                )

            type_map = {
                GraphQLBoolean: "bool",
                GraphQLInt: "int",
                GraphQLString: "str",
            }
            if stype not in type_map:
                continue
            want_type = type_map[stype]
            if want_optional:
                if " | None" in f.type:
                    want_type = f"{want_type} | None"
                else:
                    want_type = f"Optional[{want_type}]"
            got_type = f.type
            if _is_converted(annotated_hints[f.name]):
                # TODO: Validate the GraphQL type the converter reads from.
                continue
            assert got_type == want_type, (
                f"{name}.{f.name} is {got_type}, want {want_type}"
            )


def test_optional_fields():
    deserialize(_schema.LocalizedValueType, {"value": None, "unit": None})
    deserialize(_schema.SelectedOption, {"value": 0, "label": None})
    deserialize(_schema.RunTimeGroup, {"id": 0, "name": None, "duration": 0})
    deserialize(_schema.WateringPeriodicity, {"value": None, "label": None})
    deserialize(
        _schema.AdvancedProgram,
        {
            "zoneSpecific": False,
            "advancedProgramId": 0,
            "wateringFrequency": None,
            "runTimeGroup": None,
        },
    )
    deserialize(_schema.TimeRange, {"validFrom": None, "validTo": None})
    deserialize(
        _schema.StandardProgram,
        {
            "startTimes": [],
            "timeRange": {
                "validFrom": None,
                "validTo": None,
            },
            "ignoreRainSensor": False,
            "daysRun": [],
            "standardProgramDayPattern": "",
            "periodicity": None,
        },
    )
    deserialize(_schema.RunStatus, {"value": None, "label": None})
    deserialize(_schema.PastZoneRuns, {"lastRun": None, "runs": None})
    deserialize(_schema.ZoneSuspension, {"id": 0, "startTime": None, "endTime": None})
    deserialize(_schema.ProgramStartTimeApplication, {"all": False, "zones": None})
    deserialize(
        _schema.ProgramStartTime,
        {"id": 0, "time": "10:00", "wateringDays": None, "application": {}},
    )
    deserialize(_schema.ControllerFirmware, {"type": "", "version": None})
    deserialize(
        _schema.ControllerHardware,
        {
            "serialNumber": None,
            "version": None,
            "status": None,
            "model": None,
            "firmware": None,
        },
    )
    deserialize(
        _schema.SensorModel,
        {
            "id": 0,
            "name": None,
            "active": None,
            "offLevel": None,
            "offTimer": None,
            "delay": None,
            "divisor": None,
            "flowRate": None,
            "sensorType": None,
        },
    )
    deserialize(_schema.SensorStatus, {"waterFlow": None, "active": None})
    deserialize(_schema.SensorFlowSummary, {"totalWaterVolume": None})
    deserialize(_schema._WaterTime, {"value": None})
    deserialize(
        _schema.ControllerStatus,
        {
            "summary": "",
            "online": False,
            "actualWaterTime": None,
            "normalWaterTime": None,
            "lastContact": None,
        },
    )
    deserialize(
        _schema.RunEvent,
        {
            "id": "",
            "zone": {},
            "standardProgram": None,
            "advancedProgram": None,
            "reportedStartTime": None,
            "reportedEndTime": None,
            "reportedDuration": None,
            "reportedStatus": None,
            "reportedWaterUsage": None,
            "reportedStopReason": None,
            "reportedCurrent": None,
        },
    )
    deserialize(_schema.WateringReportEntry, {"runEvent": None})
    deserialize(
        _schema.Controller,
        {
            "id": 0,
            "name": None,
            "softwareVersion": None,
            "hardware": {},
            "lastContactTime": None,
            "lastAction": None,
            "online": None,
            "sensors": None,
            "zones": None,
            "permittedProgramStartTimes": None,
            "status": None,
        },
    )
    deserialize(
        _schema.User,
        {
            "id": 0,
            "customerId": 0,
            "name": "",
            "email": None,
            "controllers": [],
        },
    )


def _zone(suspended_until):
    zone = Zone(id=0x10A, number=SelectedOption(value=1), name="Zone A")
    zone.status = ZoneStatus(suspended_until=suspended_until)
    return zone


def _relay_json(time_, type_=1, run=1800):
    """A REST API statusschedule.php 'relays' entry."""
    return {
        "name": "Zone A",
        "period": 259200,
        "relay": 1,
        "relay_id": 0x10A,
        "run": run,
        "stop": 1,
        "time": time_,
        "timestr": "Sat",
        "type": type_,
    }


def test_update_with_json_preserves_dated_suspension_with_scheduled_next_run():
    """Regression test for #493.

    The REST API can't represent a non-permanent (GraphQL-managed) suspension:
    a suspended-until-a-date zone looks identical in the REST response to an
    unsuspended one, since both report a normal upcoming next-run time. A REST
    poll must not clobber the suspension in that case.
    """
    suspended_until = datetime(2026, 8, 1, 12, 0, 0)
    zone = _zone(suspended_until)

    zone.update_with_json(_relay_json(time_=5400))

    assert zone.status.suspended_until == suspended_until
    assert zone.scheduled_runs.current_run is None
    assert zone.scheduled_runs.next_run is not None


def test_update_with_json_leaves_unsuspended_zone_unsuspended():
    zone = _zone(None)

    zone.update_with_json(_relay_json(time_=5400))

    assert zone.status.suspended_until is None


def test_update_with_json_clears_suspension_for_running_zone():
    """A zone that's actively running cannot be suspended."""
    zone = _zone(datetime(2026, 8, 1, 12, 0, 0))

    zone.update_with_json(_relay_json(time_=1, run=1788))

    assert zone.status.suspended_until is None
    assert zone.scheduled_runs.current_run is not None


def test_update_with_json_sets_permanent_suspension_from_sentinel_time():
    zone = _zone(None)

    zone.update_with_json(_relay_json(time_=1576800000))

    assert zone.status.suspended_until == datetime.max


def test_update_with_json_sets_permanent_suspension_from_type_110():
    zone = _zone(None)

    zone.update_with_json(_relay_json(time_=339777, type_=110))

    assert zone.status.suspended_until == datetime.max


def test_update_with_json_untrusted_sentinel_does_not_originate_suspension():
    """Regression test for #176404.

    The REST API sends the same 'not scheduled to run' sentinel when a zone
    is merely being held off by a rain sensor as it does for a truly
    suspended zone -- it can't tell the two apart. Callers that already have
    a more reliable source of truth (e.g. HybridClient, whose cached zone was
    last populated by the GraphQL API) pass trust_suspension_sentinel=False.
    If we don't already have a reason to believe the zone is suspended, the
    sentinel must not be treated as authoritative in that case, or a
    rain-sensor hold would falsely flip the zone to suspended until the next
    GraphQL poll corrects it -- causing Home Assistant's automatic watering
    switch to flap.
    """
    zone = _zone(None)

    zone.update_with_json(
        _relay_json(time_=1576800000), trust_suspension_sentinel=False
    )

    assert zone.status.suspended_until is None


def test_update_with_json_untrusted_type_110_does_not_originate_suspension():
    zone = _zone(None)

    zone.update_with_json(
        _relay_json(time_=339777, type_=110), trust_suspension_sentinel=False
    )

    assert zone.status.suspended_until is None


def test_update_with_json_untrusted_sentinel_still_corroborates_known_suspension():
    """Even with trust_suspension_sentinel=False, a REST sentinel corroborates
    a suspension we already know about (e.g. from the GraphQL API) rather
    than being ignored outright."""
    suspended_until = datetime(2026, 8, 1, 12, 0, 0)
    zone = _zone(suspended_until)

    zone.update_with_json(
        _relay_json(time_=1576800000), trust_suspension_sentinel=False
    )

    assert zone.status.suspended_until == datetime.max


def test_converts_a_unix_timestamp():
    time_range = deserialize(_schema.TimeRange, {"validFrom": 1672531200})
    assert time_range.valid_from == datetime.fromtimestamp(1672531200)


def test_converts_an_hour_minute_string():
    start = deserialize(_schema.ProgramStartTime, {"id": 1, "time": "06:30"})
    assert start.time == time(6, 30)


def test_accepts_an_already_converted_value():
    """The converters pass a native value through, so these dataclasses stay
    constructible with ordinary Python values -- which the REST paths rely on."""
    start = _schema.ProgramStartTime(id=1, time=time(6, 30))
    assert start.time == time(6, 30)

    run = _schema.ScheduledZoneRun(start_time=datetime(2023, 1, 1, 0, 0, 0))
    assert run.start_time == datetime(2023, 1, 1, 0, 0, 0)

    time_range = _schema.TimeRange(valid_from=datetime(2023, 1, 1, 0, 0, 0))
    assert time_range.valid_from == datetime(2023, 1, 1, 0, 0, 0)


def test_converts_a_datetime_object_instance():
    """A GraphQL DateTime arrives as a mapping, but an already-built one works.

    The field is annotated as a datetime, so this is deliberately looser than
    the type says -- it keeps DateTime.from_json usable as an input the way
    apischema's DateTime conversion was.
    """
    run = _schema.ScheduledZoneRun(
        start_time=_schema.DateTime(  # type: ignore[arg-type]
            value="Sun, 01 Jan 23 00:12:00", timestamp=1672531200
        )
    )
    assert run.start_time == datetime.fromtimestamp(1672531200)


def test_rejects_a_datetime_object_with_no_timestamp():
    with pytest.raises(ValidationError, match="has no timestamp"):
        deserialize(
            _schema.ScheduledZoneRun, {"startTime": {"value": "Sun, 01 Jan 23"}}
        )


def test_rejects_null_for_a_required_field():
    """Only _optional_field falls back to its default; everything else is fatal."""
    with pytest.raises(ValidationError):
        deserialize(_schema.StatusCodeAndSummary, {"status": None})
