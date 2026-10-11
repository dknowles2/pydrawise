"""GraphQL API schema for pydrawise."""

from __future__ import annotations

import dataclasses
from collections.abc import Callable
from dataclasses import field
from datetime import UTC, datetime, time, timedelta
from enum import Enum, auto
from importlib import resources
from typing import Annotated, Any, TypeVar, cast, dataclass_transform

from gql.dsl import DSLSchema
from graphql import build_ast_schema, parse
from pydantic import BeforeValidator, ConfigDict, ValidationError, model_validator
from pydantic.alias_generators import to_camel
from pydantic.dataclasses import dataclass as _pydantic_dataclass
from pydantic.dataclasses import is_pydantic_dataclass, rebuild_dataclass
from pydantic_core.core_schema import ValidatorFunctionWrapHandler

# The names in this file are from the GraphQL schema and don't always adhere to
# the naming scheme that pylint expects.
# pylint: disable=invalid-name

SCHEMA_TEXT = resources.files(__package__).joinpath("hydrawise.graphql").read_text()
DSL_SCHEMA = DSLSchema(build_ast_schema(parse(SCHEMA_TEXT)))


_T = TypeVar("_T")

# The Hydrawise API speaks camelCase while these dataclasses are snake_case, so
# every type below deserializes by alias. Field names have to be accepted too:
# pydantic routes a dataclass's __init__ through the same validator, and the
# REST paths (rest.py, Zone.from_json, Controller.from_json) construct these
# types with ordinary snake_case keyword arguments.
_PYDANTIC_CONFIG = ConfigDict(
    alias_generator=to_camel, validate_by_alias=True, validate_by_name=True
)

# Field metadata key set by _optional_field. See _fall_back_on_default.
_OPTIONAL_FIELD_METADATA = "pydrawise_optional"

# Field metadata key set by _sensitive_field (and by _optional_field's
# `sensitive` argument). Read by the diagnostics module, which replaces such a
# field's value with a placeholder.
_SENSITIVE_FIELD_METADATA = "pydrawise_sensitive"


class _WireType:
    """Marks the GraphQL type a field is deserialized from.

    Only needed when the wire type is a GraphQL object but the field exposes a
    native Python type -- `DateTime` arriving as a `datetime`, say.
    `schema_utils.get_selectors` reads this to know it must emit a
    sub-selection for the field rather than treating it as a scalar leaf.

    :meta private:
    """

    def __init__(self, graphql_type: type) -> None:
        self.graphql_type = graphql_type


_GRAPHQL_TYPE_NAMES: dict[type, str] = {}


def _type_name(name: str) -> Callable[[type[_T]], type[_T]]:
    """Declares the GraphQL type a dataclass deserializes from.

    Only needed when the names differ; otherwise the class name is used.

    :meta private:
    """

    def decorate(cls: type[_T]) -> type[_T]:
        _GRAPHQL_TYPE_NAMES[cls] = name
        return cls

    return decorate


def _graphql_type_name(cls: Any) -> str:
    """Returns the GraphQL type name a dataclass deserializes from.

    :meta private:
    """
    return _GRAPHQL_TYPE_NAMES.get(cls, cls.__name__)


def _optional_field(*args: Any, sensitive: bool = False, **kwargs: Any) -> Any:
    """Declares a field that falls back to its default when the API sends null.

    :param sensitive: Whether the field holds sensitive information. See
        `_sensitive_field`.

    :meta private:
    """
    metadata = {**kwargs.pop("metadata", {}), _OPTIONAL_FIELD_METADATA: True}
    if sensitive:
        metadata[_SENSITIVE_FIELD_METADATA] = True
    return field(*args, metadata=metadata, **kwargs)


def _sensitive_field(*args: Any, **kwargs: Any) -> Any:
    """Declares a field that holds sensitive information.

    `diagnostics.redacted_dump` replaces such a field's value with
    `diagnostics.REDACTED`, so that a dump can be attached to a bug report
    without leaking account or hardware identity.

    :meta private:
    """
    kwargs["metadata"] = {
        **kwargs.get("metadata", {}),
        _SENSITIVE_FIELD_METADATA: True,
    }
    return field(*args, **kwargs)


def _optional_field_names(cls: type) -> frozenset[str]:
    """Names of the fields on `cls` that _optional_field declared.

    Called before pydantic processes the class, so `dataclasses.fields` isn't
    available yet -- the raw Field objects are still plain class attributes.
    Inherited names come from the already-decorated base classes.

    :meta private:
    """
    names = {
        name
        for name, value in vars(cls).items()
        if isinstance(value, dataclasses.Field)
        and value.metadata.get(_OPTIONAL_FIELD_METADATA)
    }
    for base in cls.__mro__[1:]:
        names |= getattr(base, "_pydrawise_optional_fields", frozenset())
    return frozenset(names)


@dataclass_transform(field_specifiers=(field, _optional_field, _sensitive_field))
def _dataclass(cls: type[_T]) -> type[_T]:
    """Declares a dataclass that deserializes from camelCased GraphQL JSON.

    Wraps `pydantic.dataclasses.dataclass`, so the result is still a real
    dataclass -- `dataclasses.fields()` and `is_dataclass()` work on it, which
    is what lets `schema_utils.get_selectors` walk it.

    :meta private:
    """
    optional = _optional_field_names(cls)
    # Deserialization is by alias, so an error is reported under whichever
    # spelling the payload used.
    keys = optional | {to_camel(name) for name in optional}

    def fall_back_on_default(
        _cls: type, data: Any, handler: ValidatorFunctionWrapHandler
    ) -> Any:
        """Falls back to the default for any _optional_field that won't parse.

        The Hydrawise API regularly sends null -- or a half-populated object --
        where its own schema promises a value. Dropping the offending key lets
        pydantic substitute the field's default, which is what callers expect.

        Only applies while deserializing a payload: constructing one of these
        dataclasses directly passes ArgsKwargs rather than a mapping, and those
        errors are the caller's own and stay fatal.
        """
        try:
            return handler(data)
        except ValidationError as err:
            if not isinstance(data, dict):
                raise
            dropped = {
                loc[0]
                for error in err.errors()
                if (loc := error["loc"]) and loc[0] in keys
            }
            if not dropped:
                raise
            return handler({k: v for k, v in data.items() if k not in dropped})

    cls._pydrawise_optional_fields = optional  # type: ignore[attr-defined]
    # pydantic types model_validator for decorator use inside a class body,
    # where it can infer the model type; applying it programmatically like this
    # is correct at runtime but outside what those overloads describe.
    validator = model_validator(mode="wrap")(
        classmethod(fall_back_on_default)  # type: ignore[arg-type]
    )
    cls._fall_back_on_default = validator  # type: ignore[attr-defined]
    return cast(type[_T], _pydantic_dataclass(cls, config=_PYDANTIC_CONFIG))


def _now() -> datetime:
    """Current datetime.

    :meta private:
    """
    return datetime.now().replace(microsecond=0)


default_datetime = _now


def _duration(unit: str) -> BeforeValidator:
    """Deserializes a bare count of `unit` into a timedelta.

    :meta private:
    """

    def convert(value: Any) -> Any:
        if isinstance(value, int | float):
            return timedelta(**{unit: value})
        return value

    return BeforeValidator(convert)


def _from_timestamp(value: Any) -> Any:
    """Deserializes a Unix timestamp into a datetime.

    :meta private:
    """
    if isinstance(value, int | float):
        return datetime.fromtimestamp(value)
    return value


def _from_hour_minute(value: Any) -> Any:
    """Deserializes an "HH:MM" string into a time.

    :meta private:
    """
    if isinstance(value, str):
        return datetime.strptime(value, "%H:%M").time()
    return value


# Converted field types. Each pairs the Python type a field exposes with the
# converter that turns the wire representation into it. The converters all pass
# an already-converted value straight through, so these types stay usable as
# ordinary constructor arguments -- which the REST paths in Zone.from_json and
# Controller.from_json rely on.
_Minutes = Annotated[timedelta, _duration("minutes")]
_Seconds = Annotated[timedelta, _duration("seconds")]
_Timestamp = Annotated[datetime, BeforeValidator(_from_timestamp)]
_HourMinute = Annotated[time, BeforeValidator(_from_hour_minute)]


class _AutoEnum(Enum):
    @staticmethod
    def _generate_next_value_(
        name: str, start: int, count: int, last_values: list[Any]
    ) -> str:
        """Determines the value for an auto() call."""
        return name


class StatusCodeEnum(_AutoEnum):
    """Response status codes."""

    OK = auto()
    WARNING = auto()
    ERROR = auto()


@_dataclass
class StatusCodeAndSummary:
    """A response status code and a human-readable summary."""

    status: StatusCodeEnum = StatusCodeEnum.OK
    summary: str = ""


@_dataclass
class LocalizedValueType:
    """A localized value."""

    value: float = _optional_field(default=0.0)
    unit: str = _optional_field(default="")


@_dataclass
class SelectedOption:
    """A generic option."""

    value: int = 0
    label: str = _optional_field(default="")


@_dataclass
class DateTime:
    """A date & time.

    This is only used for serialization and deserialization.
    """

    value: str = ""
    timestamp: int = 0

    @staticmethod
    def from_json(dt: DateTime) -> datetime:
        """Converts a DateTime to a native python type."""
        return datetime.fromtimestamp(dt.timestamp)

    @staticmethod
    def to_json(dt: datetime) -> DateTime:
        """Converts a native datetime to a DateTime GraphQL type."""
        local = dt
        if local.tzinfo is None:
            # Make sure we have a timezone set so strftime outputs a valid string.
            local = local.replace(tzinfo=datetime.now(UTC).astimezone().tzinfo)
        return DateTime(
            value=local.strftime("%a, %d %b %y %H:%M:%S %z"),
            timestamp=int(dt.timestamp()),
        )


def _from_datetime_object(value: Any) -> Any:
    """Deserializes a GraphQL DateTime object into a datetime.

    :meta private:
    """
    if isinstance(value, DateTime):
        return DateTime.from_json(value)
    if isinstance(value, dict):
        if (timestamp := value.get("timestamp")) is None:
            raise ValueError(f"DateTime has no timestamp: {value!r}")
        return datetime.fromtimestamp(timestamp)
    return value


#: A datetime that arrives on the wire as a GraphQL `DateTime` object.
_GqlDateTime = Annotated[
    datetime, BeforeValidator(_from_datetime_object), _WireType(DateTime)
]


@_type_name("Zone")
@_dataclass
class BaseZone:
    """Basic zone information."""

    id: int = 0
    number: SelectedOption = field(default_factory=SelectedOption)
    name: str = ""


@_dataclass
class CycleAndSoakSettings:
    """Cycle and soak durations."""

    cycle_duration: _Minutes = timedelta()
    soak_duration: _Minutes = timedelta()


@_dataclass
class RunTimeGroup:
    """The runtime of a watering program group."""

    id: int = 0
    name: str = _optional_field(default="")
    duration: _Minutes = timedelta()


@_dataclass
class WateringPeriodicity:
    """Watering frequency description (e.g., "Every Program Start Time")."""

    value: int = _optional_field(default=0)
    label: str = _optional_field(default="")


@_dataclass
class ProgramWateringFrequency:
    """Watering frequency information."""

    label: str = ""
    period: WateringPeriodicity = field(default_factory=WateringPeriodicity)
    description: str = ""


@_dataclass
@_type_name("StandardProgram")
class StandardProgramRef:
    """Super small base class to reference a watering program without having
    to pull in all the voluminous sub-fields."""

    id: int = 0
    name: str = ""


@_dataclass
@_type_name("AdvancedProgram")
class AdvancedProgramRef:
    """Super small base class to reference a watering program without having
    to pull in all the voluminous sub-fields."""

    id: int = 0
    name: str = ""


@_dataclass
class Program:
    """Base class for a watering program."""

    id: int = 0
    name: str = ""

    scheduling_method: SelectedOption = field(default_factory=SelectedOption)
    monthly_watering_adjustments: list[int] = field(default_factory=list)
    applies_to_zones: list[BaseZone] = field(default_factory=list)


@_dataclass
class AdvancedProgram(Program):
    """An advanced watering program."""

    zone_specific: bool = False
    advanced_program_id: int = 0
    watering_frequency: ProgramWateringFrequency = _optional_field(
        default_factory=ProgramWateringFrequency
    )
    run_time_group: RunTimeGroup = _optional_field(default_factory=RunTimeGroup)


class AdvancedProgramDayPatternEnum(_AutoEnum):
    """A value for an advanced watering program day pattern."""

    EVEN = auto()
    ODD = auto()
    MONDAY = auto()
    TUESDAY = auto()
    WEDNESDAY = auto()
    THURSDAY = auto()
    FRIDAY = auto()
    SATURDAY = auto()
    SUNDAY = auto()
    DAYS = auto()


@_dataclass
class WateringSettings:
    """Generic settings for a watering program."""

    fixed_watering_adjustment: int = 0
    cycle_and_soak_settings: CycleAndSoakSettings | None = None


@_dataclass
class AdvancedWateringSettings(WateringSettings):
    """Advanced watering program settings."""

    advanced_program: AdvancedProgram | None = None


@_dataclass
@_type_name("Unit")
class TimeRange:
    """Time range units."""

    valid_from: _Timestamp = _optional_field(default_factory=default_datetime)
    valid_to: _Timestamp = _optional_field(default_factory=default_datetime)


@_dataclass
class StandardProgramPeriodicity:
    """Program frequency for a standard program."""

    period: int = 0
    series_start: _GqlDateTime = field(default_factory=default_datetime)


@_dataclass
class StandardProgram(Program):
    """A standard watering program."""

    start_times: list[_HourMinute] = _optional_field(default_factory=list)
    time_range: TimeRange = field(default_factory=TimeRange)
    ignore_rain_sensor: bool = False
    days_run: list[DaysOfWeekEnum] = field(default_factory=list)
    standard_program_day_pattern: str = ""
    periodicity: StandardProgramPeriodicity = _optional_field(
        default_factory=StandardProgramPeriodicity
    )


@_dataclass
class StandardProgramApplication:
    """A standard watering program application."""

    zone: BaseZone = field(default_factory=BaseZone)
    standard_program: StandardProgram = field(default_factory=StandardProgram)
    run_time_group: RunTimeGroup = field(default_factory=RunTimeGroup)


@_dataclass
class StandardWateringSettings(WateringSettings):
    """Standard watering settings."""

    standard_program_applications: list[StandardProgramApplication] = field(
        default_factory=list
    )


@_dataclass
class RunStatus:
    """Run status."""

    value: int = _optional_field(default=0)
    label: str = _optional_field(default="")


@_dataclass
class ScheduledZoneRun:
    """A scheduled zone run."""

    id: str = ""
    start_time: _GqlDateTime = field(default_factory=default_datetime)
    end_time: _GqlDateTime = field(default_factory=default_datetime)
    normal_duration: _Minutes = timedelta()
    duration: _Minutes = timedelta()
    remaining_time: _Seconds = timedelta()
    status: RunStatus = field(default_factory=RunStatus)


@_dataclass
class ScheduledZoneRuns:
    """Scheduled runs for a zone."""

    summary: str = ""
    current_run: ScheduledZoneRun | None = None
    next_run: ScheduledZoneRun | None = None
    status: str | None = None


@_dataclass
class PastZoneRuns:
    """Previous zone runs."""

    last_run: ScheduledZoneRun | None = None
    runs: list[ScheduledZoneRun] = _optional_field(default_factory=list)


@_dataclass
class ZoneStatus:
    """A zone's status."""

    relative_water_balance: int = 0
    suspended_until: _GqlDateTime | None = None


@_dataclass
class ZoneSuspension:
    """A zone suspension."""

    id: int = 0
    start_time: _GqlDateTime = _optional_field(default_factory=default_datetime)
    end_time: _GqlDateTime = _optional_field(default_factory=default_datetime)


@_dataclass
class Zone(BaseZone):
    """A watering zone."""

    watering_settings: AdvancedWateringSettings | StandardWateringSettings = field(
        default_factory=StandardWateringSettings
    )
    scheduled_runs: ScheduledZoneRuns = field(default_factory=ScheduledZoneRuns)
    past_runs: PastZoneRuns = field(default_factory=PastZoneRuns)
    status: ZoneStatus = field(default_factory=ZoneStatus)
    suspensions: list[ZoneSuspension] = field(default_factory=list)

    @classmethod
    def from_json(cls, zone_json: dict) -> Zone:
        """Builds a new Zone from a REST API "relay" JSON object.

        :param zone_json: A single relay entry, as returned by the REST
            API's statusschedule.php endpoint.
        :rtype: Zone
        """
        zone = Zone(
            id=zone_json["relay_id"],
            # The REST API sends a bare integer where the GraphQL API sends a
            # SelectedOption. Wrap it so a Zone has the same shape regardless of
            # which API produced it -- HybridClient merges the two.
            number=SelectedOption(value=zone_json["relay"]),
            name=zone_json["name"],
        )
        zone.update_with_json(zone_json)
        return zone

    def update_with_json(
        self, zone_json: dict, *, trust_suspension_sentinel: bool = True
    ) -> None:
        """Updates this Zone's schedule and status from a REST API "relay" JSON object.

        :param zone_json: A single relay entry, as returned by the REST
            API's statusschedule.php endpoint.
        :param trust_suspension_sentinel: Whether the REST API's ambiguous
            "suspended" sentinel value should be treated as authoritative for
            this zone. Callers with a more reliable source of truth (e.g.
            HybridClient, once it already knows this zone's real suspension
            state from the GraphQL API) should pass False so the sentinel can
            only corroborate a suspension already known, never originate one.
        """
        current_run = None
        next_run = None
        if zone_json["time"] == 1:
            # Zone is currently running; it cannot be suspended.
            current_run = ScheduledZoneRun(
                remaining_time=timedelta(seconds=zone_json["run"]),
            )
            self.status = ZoneStatus(suspended_until=None)
        elif zone_json["time"] == 1576800000 or zone_json.get("type") == 110:
            # The REST API sends this same sentinel both for a truly
            # suspended zone and for one that's merely being held off by
            # e.g. a rain sensor -- it can't tell the two apart. Callers that
            # already have a more reliable source of truth for this zone
            # (e.g. HybridClient, which only falls back to REST when its
            # cached zone was last populated by the GraphQL API) pass
            # trust_suspension_sentinel=False so the sentinel is only used to
            # corroborate a suspension we already know about, never to
            # originate one -- treating it as authoritative produced false
            # positives that then flapped back to unsuspended on the next
            # GraphQL poll. Callers with no other source of truth (e.g. a
            # brand new Zone built straight from REST data) keep the default
            # of trusting it, since it's the only signal available.
            if trust_suspension_sentinel or self.status.suspended_until is not None:
                self.status = ZoneStatus(suspended_until=datetime.max)
        else:
            start_time = _now() + timedelta(seconds=zone_json["time"])
            duration = timedelta(seconds=zone_json["run"])
            next_run = ScheduledZoneRun(
                start_time=start_time,
                end_time=start_time + duration,
                normal_duration=duration,
                duration=duration,
            )
            # Do NOT overwrite self.status.suspended_until here. The REST API
            # cannot represent non-permanent suspensions (e.g. those set via the
            # GraphQL API), so leaving the existing value in place preserves any
            # suspension that was established through the GraphQL API.
        self.scheduled_runs = ScheduledZoneRuns(
            current_run=current_run,
            next_run=next_run,
        )


@_dataclass
class ProgramStartTimeApplication:
    """Application of a start time to a program."""

    all: bool = False
    zones: list[BaseZone] = _optional_field(default_factory=list)


@_dataclass
class ProgramStartTime:
    """Start time for a watering program."""

    id: int = 0
    time: _HourMinute = field(default_factory=time)
    watering_days: list[AdvancedProgramDayPatternEnum] = _optional_field(
        default_factory=list
    )
    application: ProgramStartTimeApplication = field(
        default_factory=ProgramStartTimeApplication
    )


@_dataclass
class ControllerFirmware:
    """Information about the controller's firmware."""

    type: str = ""
    version: str = _optional_field(default="")


@_dataclass
class ControllerModel:
    """Information about a controller model."""

    name: str = ""
    description: str = ""


@_dataclass
class ControllerHardware:
    """Information about a controller's hardware."""

    serial_number: str = _optional_field(default="", sensitive=True)
    version: str = _optional_field(default="")
    status: str = _optional_field(default="")
    model: ControllerModel = _optional_field(default_factory=ControllerModel)
    firmware: list[ControllerFirmware] = _optional_field(default_factory=list)


class CustomSensorTypeEnum(_AutoEnum):
    """A value for a sensor type."""

    LEVEL_OPEN = auto()
    LEVEL_CLOSED = auto()
    FLOW = auto()
    THRESHOLD = auto()


@_dataclass
class SensorModel:
    """Information about a sensor model."""

    id: int = 0
    name: str = _optional_field(default="")
    active: bool = _optional_field(default=False)
    off_level: int = _optional_field(default=0)
    off_timer: int = _optional_field(default=0)
    delay: _Minutes = _optional_field(default=timedelta())
    divisor: float = _optional_field(default=0.0)
    flow_rate: float = _optional_field(default=0.0)
    sensor_type: CustomSensorTypeEnum | None = None


@_dataclass
class SensorStatus:
    """Current status of a sensor."""

    water_flow: LocalizedValueType | None = None
    active: bool = _optional_field(default=False)


@_dataclass
class SensorFlowSummary:
    """Summary of a sensor's water flow."""

    total_water_volume: LocalizedValueType = _optional_field(
        default_factory=LocalizedValueType
    )


@_dataclass
class Sensor:
    """A sensor connected to a controller."""

    id: int = 0
    name: str = ""
    model: SensorModel = field(default_factory=SensorModel)
    status: SensorStatus = field(default_factory=SensorStatus)


@_dataclass
@_type_name("Sensor")
class SensorWithFlowSummary(Sensor):
    """A Sensor, as returned by its `flowSummary` method."""

    flow_summary: SensorFlowSummary | None = _optional_field(
        default_factory=SensorFlowSummary
    )


@_dataclass
class _WaterTime:
    """A water time duration."""

    value: _Minutes = _optional_field(default=timedelta())


@_dataclass
class ActualWaterTime(_WaterTime):
    """An actual water time duration."""


@_dataclass
class NormalWaterTime(_WaterTime):
    """A normal water time duration."""


@_dataclass
class ControllerStatus:
    """Current status of a controller."""

    summary: str = ""
    online: bool = False
    actual_water_time: ActualWaterTime = _optional_field(
        default_factory=ActualWaterTime
    )
    normal_water_time: NormalWaterTime = _optional_field(
        default_factory=NormalWaterTime
    )
    last_contact: DateTime | None = None


@_dataclass
class RunStatusType:
    """The status of a reported zone run."""

    value: int = 0
    label: str = ""


@_dataclass
class RunStopReasonType:
    """Why a reported zone run stopped."""

    finished_normally: bool = False
    description: list[str] = field(default_factory=list)


@_dataclass
@_type_name("RunEventType")
class RunEvent:
    """A Hydrawise run event type."""

    id: str = ""
    zone: BaseZone = field(default_factory=BaseZone)
    standard_program: StandardProgramRef = _optional_field(
        default_factory=StandardProgramRef
    )
    advanced_program: AdvancedProgramRef = _optional_field(
        default_factory=AdvancedProgramRef
    )
    reported_start_time: _GqlDateTime | None = None
    reported_end_time: _GqlDateTime | None = None
    reported_duration: _Seconds = _optional_field(default=timedelta())
    reported_status: RunStatusType = _optional_field(default_factory=RunStatusType)
    reported_water_usage: LocalizedValueType = _optional_field(
        default_factory=LocalizedValueType
    )
    reported_stop_reason: RunStopReasonType = _optional_field(
        default_factory=RunStopReasonType
    )
    reported_current: LocalizedValueType = _optional_field(
        default_factory=LocalizedValueType
    )


@_dataclass
class WateringReportEntry:
    """A Hydrawise watering report entry."""

    run_event: RunEvent = _optional_field(default_factory=RunEvent)


@_dataclass
class MasterValve:
    """A master valve setting for a controller."""

    zone_number: SelectedOption | None = None
    delay: int | None = None
    post_timer: int | None = None


@_dataclass
class Controller:
    """A Hydrawise controller."""

    id: int = 0
    name: str = _optional_field(default="", sensitive=True)
    software_version: str = _optional_field(default="")
    hardware: ControllerHardware = field(default_factory=ControllerHardware)
    last_contact_time: _GqlDateTime = _optional_field(default_factory=default_datetime)
    last_action: _GqlDateTime = _optional_field(default_factory=default_datetime)
    online: bool = _optional_field(default=False)
    sensors: list[Sensor] = _optional_field(default_factory=list)
    zones: list[Zone] = _optional_field(default_factory=list)
    master_zone: MasterValve | None = None
    permitted_program_start_times: list[ProgramStartTime] = _optional_field(
        default_factory=list
    )
    status: ControllerStatus | None = None

    @classmethod
    def from_json(cls, controller_json: dict) -> Controller:
        """Builds a new Controller from a REST API "controller" JSON object.

        :param controller_json: A single controller entry, as returned by
            the REST API's customerdetails.php endpoint.
        :rtype: Controller
        """
        controller = Controller(
            id=controller_json["controller_id"],
            name=controller_json["name"],
            hardware=ControllerHardware(
                serial_number=controller_json["serial_number"],
            ),
        )
        controller.update_with_json(controller_json)
        return controller

    def update_with_json(self, controller_json: dict) -> None:
        """Updates this Controller's last contact time from a REST API "controller" JSON object.

        :param controller_json: A single controller entry, as returned by
            the REST API's customerdetails.php endpoint.
        """
        self.last_contact_time = datetime.fromtimestamp(controller_json["last_contact"])
        self.online = True


@_dataclass
class UnitsSummary:
    """Summary of user unit preferences."""

    units_name: str = ""


@_dataclass
class User:
    """A Hydrawise user account."""

    id: int = _sensitive_field(default=0)
    customer_id: int = _sensitive_field(default=0)
    name: str = _sensitive_field(default="")
    email: str = _optional_field(default="", sensitive=True)
    controllers: list[Controller] = _optional_field(default_factory=list)
    units: UnitsSummary = field(default_factory=UnitsSummary)


class DaysOfWeekEnum(_AutoEnum):
    """All days of the week."""

    SUNDAY = auto()
    MONDAY = auto()
    TUESDAY = auto()
    WEDNESDAY = auto()
    THURSDAY = auto()
    FRIDAY = auto()
    SATURDAY = auto()


@_dataclass
class ControllerWaterUseSummary:
    """Water use summary for a controller.

    Active use means water use during a scheduled or manual zone run.
    Inactive use means water use when no zone was actively running. This can happen when
    faucets (i.e., garden hoses) are installed downstream of the flow meter. Water use
    is only reported in the presence of a flow sensor. Active watering time is always
    reported.
    """

    _pydrawise_type = True

    total_active_time: _Seconds = timedelta()
    active_time_by_zone_id: dict[int, timedelta] = field(default_factory=dict)
    total_use: float | None = None
    total_active_use: float | None = None
    total_inactive_use: float | None = None
    active_use_by_zone_id: dict[int, float] = field(default_factory=dict)
    unit: str | None = None


def _build_deferred_schemas() -> None:
    """Builds the schemas pydantic deferred at class creation.

    Types that reference a type declared further down this module can't get
    their pydantic schema when they are created, so pydantic builds it on
    first use instead. Building it then picks up whatever ``datetime`` is at
    that moment: under freezegun's ``freeze_time`` that is ``FakeDatetime``,
    which pydantic can't generate a schema for. Building everything at import
    keeps that first use from depending on the caller's state.

    :meta private:
    """
    for value in list(globals().values()):
        if (
            isinstance(value, type)
            and is_pydantic_dataclass(value)
            and not value.__pydantic_complete__
        ):
            rebuild_dataclass(value)


_build_deferred_schemas()
