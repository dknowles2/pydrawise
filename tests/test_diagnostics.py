import json
from dataclasses import dataclass, field
from datetime import datetime, time, timedelta

from pydrawise.diagnostics import REDACTED, redacted_dump
from pydrawise.schema import (
    _SENSITIVE_FIELD_METADATA,
    Controller,
    ControllerWaterUseSummary,
    CustomSensorTypeEnum,
    User,
    Zone,
)


def test_redacts_account_and_controller_identity(user: User):
    dump = redacted_dump(user)

    assert dump["id"] == REDACTED
    assert dump["customer_id"] == REDACTED
    assert dump["name"] == REDACTED
    assert dump["email"] == REDACTED

    [controller] = dump["controllers"]
    assert controller["name"] == REDACTED
    assert controller["hardware"]["serial_number"] == REDACTED

    # Everything that identifies *equipment* rather than a person is kept: it's
    # what makes a dump useful.
    assert controller["id"] == 9876
    assert controller["software_version"] == "s0"
    assert controller["hardware"]["model"]["name"] == "HPC 10"
    assert [sensor["name"] for sensor in controller["sensors"]] == [
        "Rain sensor ",
        "Flow meter",
    ]


def test_dump_is_json_serializable(user: User, zone: Zone):
    # Serializing with no `default` is the point: Home Assistant hands
    # diagnostics data to its own encoder, which must not have to know about
    # timedelta, datetime, or any pydrawise type.
    dump = json.loads(json.dumps(redacted_dump({"user": user, "zone": zone})))

    [controller] = dump["user"]["controllers"]
    assert controller["last_contact_time"] == "2023-01-01T00:00:00"
    assert controller["status"]["actual_water_time"]["value"] == 600.0
    assert controller["sensors"][0]["model"]["sensor_type"] == "LEVEL_CLOSED"

    assert dump["zone"]["name"] == "Zone A"
    assert dump["zone"]["status"]["suspended_until"] == "2023-01-01T00:00:00"
    advanced = dump["zone"]["watering_settings"]["advanced_program"]
    assert advanced["run_time_group"]["duration"] == 1200.0
    assert advanced["applies_to_zones"][0]["name"] == "Front Lawn"


def test_extra_redact(controller: Controller, zone: Zone):
    dump = redacted_dump(
        {"controller": controller, "zone": zone}, extra_redact=["name"]
    )

    assert dump["controller"]["hardware"]["model"]["name"] == REDACTED
    assert dump["controller"]["sensors"][0]["name"] == REDACTED
    assert dump["zone"]["name"] == REDACTED
    # Only the named field is affected.
    assert dump["controller"]["id"] == 9876
    # Raw JSON (what legacy.LegacyHydrawise exposes) has no dataclass field to
    # carry a marker, so `extra_redact` matches mapping keys too.
    assert redacted_dump({"relay": {"name": "Zone A"}}, extra_redact=["name"]) == {
        "relay": {"name": REDACTED}
    }


def test_conversions():
    summary = ControllerWaterUseSummary(
        total_active_time=timedelta(minutes=5),
        active_time_by_zone_id={1: timedelta(minutes=2)},
        total_use=3.5,
        unit="gal",
    )
    assert redacted_dump(summary) == {
        "total_active_time": 300.0,
        "active_time_by_zone_id": {1: 120.0},
        "total_use": 3.5,
        "total_active_use": None,
        "total_inactive_use": None,
        "active_use_by_zone_id": {},
        "unit": "gal",
    }
    assert redacted_dump(CustomSensorTypeEnum.FLOW) == "FLOW"
    assert redacted_dump(datetime(2023, 1, 1, 12, 30)) == "2023-01-01T12:30:00"
    assert redacted_dump(time(6, 0)) == "06:00:00"
    assert redacted_dump(timedelta(seconds=90)) == 90.0
    assert redacted_dump((1, {2}, True, None, "x")) == [1, [2], True, None, "x"]
    # Keys JSON can't express become strings.
    assert redacted_dump({(1, 2): "x"}) == {"[1, 2]": "x"}
    # An unknown type is described rather than failing to serialize.
    assert redacted_dump(Ellipsis) == "Ellipsis"
    # Passing a dataclass *type* dumps the type, not its fields.
    assert redacted_dump(User).endswith("User'>")


@dataclass
class _CallerData:
    """Stands in for a caller's own wrapper around pydrawise objects."""

    controllers: dict[int, Controller] = field(default_factory=dict)
    secret: str | None = field(default=None, metadata={_SENSITIVE_FIELD_METADATA: True})


def test_walks_foreign_dataclasses(controller: Controller):
    dump = redacted_dump(_CallerData(controllers={controller.id: controller}))

    assert dump["controllers"][9876]["hardware"]["serial_number"] == REDACTED
    # A sensitive field with no value stays None: "the API sent nothing here"
    # is worth knowing and discloses nothing.
    assert dump["secret"] is None
    assert redacted_dump(_CallerData(secret="s3cret"))["secret"] == REDACTED
