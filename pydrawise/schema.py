"""GraphQL API schema for pydrawise."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, time, timedelta, timezone
from enum import Enum, auto
from typing import Optional, Union

from apischema import type_name
from apischema.conversions import Conversion
from apischema.metadata import conversion, fall_back_on_default

# The names in this file are from the GraphQL schema and don't always adhere to
# the naming scheme that pylint expects.
# pylint: disable=invalid-name


def _optional_field(*args, **kwargs):
    if "metadata" in kwargs:
        kwargs["metadata"] |= fall_back_on_default
    else:
        kwargs["metadata"] = fall_back_on_default
    return field(*args, **kwargs)


def default_datetime() -> datetime:
    """Default datetime factory for fields in this module.

    Abstracted so it can be mocked out.

    :meta private:
    """
    return datetime.now()


def _duration_conversion(unit: str) -> conversion:
    assert unit in (
        "days",
        "seconds",
        "microseconds",
        "milliseconds",
        "minutes",
        "hours",
        "weeks",
    )
    return conversion(
        Conversion(lambda d: timedelta(**{unit: d}), source=int, target=timedelta),
        Conversion(lambda d: getattr(d, unit), source=timedelta, target=int),
    )


def _timestamp_conversion() -> conversion:
    return conversion(
        Conversion(datetime.fromtimestamp, source=int, target=datetime),
        Conversion(datetime.timestamp, source=datetime, target=int),
    )


def _time_conversion() -> conversion:
    return conversion(
        Conversion(
            lambda s: datetime.strptime(s, "%H:%M").time(), source=str, target=time
        ),
        Conversion(lambda t: t.strftime("%H:%M"), source=time, target=str),
    )


def _list_conversion(element_conversion) -> conversion:
    return conversion(
        Conversion(
            lambda l: list(map(element_conversion.deserialization.converter, l)),
            source=list,
            target=list,
        ),
        Conversion(
            lambda l: list(map(element_conversion.serialization.converter, l)),
            source=list,
            target=list,
        ),
    )


class _AutoEnum(Enum):
    @staticmethod
    def _generate_next_value_(name, start, count, last_values):
        """Determines the value for an auto() call."""
        return name


class StatusCodeEnum(_AutoEnum):
    """Response status codes."""

    OK = auto()
    WARNING = auto()
    ERROR = auto()


@dataclass
class StatusCodeAndSummary:
    """A response status code and a human-readable summary."""

    status: StatusCodeEnum = StatusCodeEnum.OK
    summary: str = ""


@dataclass
class LocalizedValueType:
    """A localized value."""

    value: float = _optional_field(default=0.0)
    unit: str = _optional_field(default="")


@dataclass
class SelectedOption:
    """A generic option."""

    value: int = 0
    label: str = _optional_field(default="")


@dataclass
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
            local = local.replace(tzinfo=datetime.now(timezone.utc).astimezone().tzinfo)
        return DateTime(
            value=local.strftime("%a, %d %b %y %H:%I:%S %z"),
            timestamp=int(dt.timestamp()),
        )

    @staticmethod
    def conversion() -> conversion:
        """Returns a GraphQL conversion for a DateTime."""
        return conversion(
            Conversion(DateTime.from_json, source=DateTime, target=datetime),
            Conversion(DateTime.to_json, source=datetime, target=DateTime),
        )


@type_name("Zone")
@dataclass
class BaseZone:
    """Basic zone information."""

    id: int = 0
    number: SelectedOption = field(default_factory=SelectedOption)
    name: str = ""


@dataclass
class CycleAndSoakSettings:
    """Cycle and soak durations."""

    cycle_duration: timedelta = field(
        metadata=_duration_conversion("minutes"), default=timedelta()
    )
    soak_duration: timedelta = field(
        metadata=_duration_conversion("minutes"), default=timedelta()
    )


@dataclass
class RunTimeGroup:
    """The runtime of a watering program group."""

    id: int = 0
    name: str = _optional_field(default="")
    duration: timedelta = field(
        metadata=_duration_conversion("minutes"), default=timedelta()
    )


@dataclass
class WateringPeriodicity:
    """Watering frequency description (e.g., "Every Program Start Time")."""

    value: int = _optional_field(default=0)
    label: str = _optional_field(default="")


@dataclass
class ProgramWateringFrequency:
    """Watering frequency information."""

    label: str = ""
    period: WateringPeriodicity = field(default_factory=WateringPeriodicity)
    description: str = ""


@dataclass
@type_name("StandardProgram")
class StandardProgramRef:
    """Super small base class to reference a watering program without having
    to pull in all the voluminous sub-fields."""

    id: int = 0
    name: str = ""


@dataclass
@type_name("AdvancedProgram")
class AdvancedProgramRef:
    """Super small base class to reference a watering program without having
    to pull in all the voluminous sub-fields."""

    id: int = 0
    name: str = ""


@dataclass
class Program:
    """Base class for a watering program."""

    id: int = 0
    name: str = ""

    scheduling_method: SelectedOption = field(default_factory=SelectedOption)
    monthly_watering_adjustments: list[int] = field(default_factory=list)
    applies_to_zones: list[BaseZone] = field(default_factory=list)


@dataclass
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


@dataclass
class WateringSettings:
    """Generic settings for a watering program."""

    fixed_watering_adjustment: int = 0
    cycle_and_soak_settings: Optional[CycleAndSoakSettings] = None


@dataclass
class AdvancedWateringSettings(WateringSettings):
    """Advanced watering program settings."""

    advanced_program: Optional[AdvancedProgram] = None


@dataclass
@type_name("Unit")
class TimeRange:
    """Time range units."""

    valid_from: datetime = _optional_field(
        metadata=_timestamp_conversion(), default_factory=default_datetime
    )
    valid_to: datetime = _optional_field(
        metadata=_timestamp_conversion(), default_factory=default_datetime
    )


@dataclass
class StandardProgramPeriodicity:
    """Program frequency for a standard program."""

    period: int = 0
    series_start: datetime = field(
        metadata=DateTime.conversion(), default_factory=default_datetime
    )


@dataclass
class StandardProgram(Program):
    """A standard watering program."""

    start_times: list[time] = _optional_field(
        metadata=_list_conversion(_time_conversion()), default_factory=list
    )
    time_range: TimeRange = field(default_factory=TimeRange)
    ignore_rain_sensor: bool = False
    days_run: list[DaysOfWeekEnum] = field(default_factory=list)
    standard_program_day_pattern: str = ""
    periodicity: StandardProgramPeriodicity = _optional_field(
        default_factory=StandardProgramPeriodicity
    )


@dataclass
class StandardProgramApplication:
    """A standard watering program application."""

    zone: BaseZone = field(default_factory=BaseZone)
    standard_program: StandardProgram = field(default_factory=StandardProgram)
    run_time_group: RunTimeGroup = field(default_factory=RunTimeGroup)


@dataclass
class StandardWateringSettings(WateringSettings):
    """Standard watering settings."""

    standard_program_applications: list[StandardProgramApplication] = field(
        default_factory=list
    )


@dataclass
class RunStatus:
    """Run status."""

    value: int = _optional_field(default=0)
    label: str = _optional_field(default="")


@dataclass
class ScheduledZoneRun:
    """A scheduled zone run."""

    id: str = ""
    start_time: datetime = field(
        metadata=DateTime.conversion(), default_factory=default_datetime
    )
    end_time: datetime = field(
        metadata=DateTime.conversion(), default_factory=default_datetime
    )
    normal_duration: timedelta = field(
        metadata=_duration_conversion("minutes"), default=timedelta()
    )
    duration: timedelta = field(
        metadata=_duration_conversion("minutes"), default=timedelta()
    )
    remaining_time: timedelta = field(
        metadata=_duration_conversion("seconds"), default=timedelta()
    )
    status: RunStatus = field(default_factory=RunStatus)


@dataclass
class ScheduledZoneRuns:
    """Scheduled runs for a zone."""

    summary: str = ""
    current_run: Optional[ScheduledZoneRun] = None
    next_run: Optional[ScheduledZoneRun] = None
    status: Optional[str] = None


@dataclass
class PastZoneRuns:
    """Previous zone runs."""

    last_run: Optional[ScheduledZoneRun] = None
    runs: list[ScheduledZoneRun] = _optional_field(default_factory=list)


@dataclass
class ZoneStatus:
    """A zone's status."""

    relative_water_balance: int = 0
    suspended_until: Optional[datetime] = field(
        metadata=DateTime.conversion(), default=None
    )


@dataclass
class ZoneSuspension:
    """A zone suspension."""

    id: int = 0
    start_time: datetime = _optional_field(
        metadata=DateTime.conversion(), default_factory=default_datetime
    )
    end_time: datetime = _optional_field(
        metadata=DateTime.conversion(), default_factory=default_datetime
    )


@dataclass
class Zone(BaseZone):
    """A watering zone."""

    watering_settings: Union[
        AdvancedWateringSettings, StandardWateringSettings
    ] = field(default_factory=StandardWateringSettings)
    scheduled_runs: ScheduledZoneRuns = field(default_factory=ScheduledZoneRuns)
    past_runs: PastZoneRuns = field(default_factory=PastZoneRuns)
    status: ZoneStatus = field(default_factory=ZoneStatus)
    suspensions: list[ZoneSuspension] = field(default_factory=list)


@dataclass
class ProgramStartTimeApplication:
    """Application of a start time to a program."""

    all: bool = False
    zones: list[BaseZone] = _optional_field(default_factory=list)


@dataclass
class ProgramStartTime:
    """Start time for a watering program."""

    id: int = 0
    time: time = field(metadata=_time_conversion(), default_factory=time)
    watering_days: list[AdvancedProgramDayPatternEnum] = _optional_field(
        default_factory=list
    )
    application: ProgramStartTimeApplication = field(
        default_factory=ProgramStartTimeApplication
    )


@dataclass
class ControllerFirmware:
    """Information about the controller's firmware."""

    type: str = ""
    version: str = _optional_field(default="")


@dataclass
class ControllerModel:
    """Information about a controller model."""

    name: str = ""
    description: str = ""


@dataclass
class ControllerHardware:
    """Information about a controller's hardware."""

    serial_number: str = _optional_field(default="")
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


@dataclass
class SensorModel:
    """Information about a sensor model."""

    id: int = 0
    name: str = _optional_field(default="")
    active: bool = _optional_field(default=False)
    off_level: int = _optional_field(default=0)
    off_timer: int = _optional_field(default=0)
    delay: timedelta = _optional_field(
        metadata=_duration_conversion("minutes"), default=timedelta()
    )
    divisor: float = _optional_field(default=0.0)
    flow_rate: float = _optional_field(default=0.0)
    sensor_type: Optional[CustomSensorTypeEnum] = None


@dataclass
class SensorStatus:
    """Current status of a sensor."""

    water_flow: Optional[LocalizedValueType] = None
    active: bool = _optional_field(default=False)


@dataclass
class SensorFlowSummary:
    """Summary of a sensor's water flow."""

    total_water_volume: LocalizedValueType = _optional_field(
        default_factory=LocalizedValueType
    )


@dataclass
class Sensor:
    """A sensor connected to a controller."""

    id: int = 0
    name: str = ""
    model: SensorModel = field(default_factory=SensorModel)
    status: SensorStatus = field(default_factory=SensorStatus)


@dataclass
@type_name("Sensor")
class SensorWithFlowSummary(Sensor):
    """A Sensor, as returned by its `flowSummary` method."""

    flow_summary: Optional[SensorFlowSummary] = _optional_field(
        default_factory=SensorFlowSummary
    )


@dataclass
class _WaterTime:
    """A water time duration."""

    value: timedelta = _optional_field(
        metadata=_duration_conversion("minutes"), default=timedelta()
    )


@dataclass
class ActualWaterTime(_WaterTime):
    """An actual water time duration."""


@dataclass
class NormalWaterTime(_WaterTime):
    """A normal water time duration."""


@dataclass
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
    last_contact: Optional[DateTime] = None


@dataclass
class RunStatusType:
    value: int = 0
    label: str = ""


@dataclass
class RunStopReasonType:
    finished_normally: bool = False
    description: list[str] = field(default_factory=list)


@dataclass
@type_name("RunEventType")
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
    reported_start_time: Optional[datetime] = field(
        metadata=DateTime.conversion(), default=None
    )
    reported_end_time: Optional[datetime] = field(
        metadata=DateTime.conversion(), default=None
    )
    reported_duration: timedelta = _optional_field(
        metadata=_duration_conversion("seconds"), default=timedelta()
    )
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


@dataclass
class WateringReportEntry:
    """A Hydrawise watering report entry."""

    run_event: RunEvent = _optional_field(
        default_factory=RunEvent, metadata=fall_back_on_default
    )


@dataclass
class Controller:
    """A Hydrawise controller."""

    id: int = 0
    name: str = _optional_field(default="")
    software_version: str = _optional_field(default="")
    hardware: ControllerHardware = field(default_factory=ControllerHardware)
    last_contact_time: datetime = _optional_field(
        metadata=DateTime.conversion(), default_factory=default_datetime
    )
    last_action: datetime = _optional_field(
        metadata=DateTime.conversion(), default_factory=default_datetime
    )
    online: bool = _optional_field(default=False)
    sensors: list[Sensor] = _optional_field(default_factory=list)
    zones: list[Zone] = _optional_field(default_factory=list)
    permitted_program_start_times: list[ProgramStartTime] = _optional_field(
        default_factory=list
    )
    status: Optional[ControllerStatus] = None


@dataclass
class UnitsSummary:
    """Summary of user unit preferences."""

    units_name: str = ""


@dataclass
class User:
    """A Hydrawise user account."""

    id: int = 0
    customer_id: int = 0
    name: str = ""
    email: str = _optional_field(default="")
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


@dataclass
class ControllerWaterUseSummary:
    """Water use summary for a controller.

    Active use means water use during a scheduled or manual zone run.
    Inactive use means water use when no zone was actively running. This can happen when
    faucets (i.e., garden hoses) are installed downstream of the flow meter. Water use
    is only reported in the presence of a flow sensor. Active watering time is always
    reported.
    """

    _pydrawise_type = True

    total_active_time: timedelta = field(
        metadata=_duration_conversion("seconds"), default=timedelta()
    )
    active_time_by_zone_id: dict[int, timedelta] = field(default_factory=dict)
    total_use: Optional[float] = None
    total_active_use: Optional[float] = None
    total_inactive_use: Optional[float] = None
    active_use_by_zone_id: dict[int, float] = field(default_factory=dict)
    unit: Optional[str] = None
