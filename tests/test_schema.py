from dataclasses import fields, is_dataclass
from datetime import datetime
from string import ascii_lowercase

from apischema.metadata.keys import CONVERSION_METADATA, FALL_BACK_ON_DEFAULT_METADATA
from apischema.type_names import get_type_name
from apischema.utils import to_camel_case
from graphql import build_schema
from graphql.type import GraphQLBoolean, GraphQLInt, GraphQLNonNull, GraphQLString

from pydrawise import schema as _schema
from pydrawise.schema import Zone, ZoneStatus
from pydrawise.schema_utils import deserialize


def test_valid_schema():
    gql_schema = build_schema(_schema.SCHEMA_TEXT)

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
    zone = Zone(id=0x10A, number=1, name="Zone A")
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
