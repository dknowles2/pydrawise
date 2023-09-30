"""GraphQL API schema for pydrawise."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from enum import Enum, auto
from typing import Optional, Union

from apischema.conversions import Conversion
from apischema.metadata import conversion, skip

# The names in this file are from the GraphQL schema and don't always adhere to
# the naming scheme that pylint expects.
# pylint: disable=invalid-name


def default_datetime() -> datetime:
    """Default datetime factory for fields in this module.

    Abstracted so it can be mocked out.

    :meta private:
    """
    return datetime.now()


class StatusCodeEnum(Enum):
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

    value: float = 0.0
    unit: str = ""


@dataclass
class Option:
    """A generic option."""

    value: int = 0
    label: str = ""


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


@dataclass
class BaseZone:
    """Basic zone information."""

    id: int = 0
    number: Option = field(default_factory=Option)
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
    duration: timedelta = field(
        metadata=_duration_conversion("minutes"), default=timedelta()
    )


@dataclass
class AdvancedProgram:
    """An advanced watering program."""

    advanced_program_id: int = 0
    run_time_group: RunTimeGroup = field(default_factory=RunTimeGroup)


class AdvancedProgramDayPatternEnum(Enum):
    """A value for an advanced watering program day pattern."""

    @staticmethod
    def _generate_next_value_(name, start, count, last_values):
        """Determines the value for an auto() call."""
        return name

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
class ProgramStartTime:
    """Start time for a watering program."""

    id: int = 0
    time: str = ""  # e.g. "02:00"
    watering_days: list[AdvancedProgramDayPatternEnum] = field(default_factory=list)


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
class StandardProgram:
    """A standard watering program."""

    name: str = ""
    start_times: list[str] = field(default_factory=list)


@dataclass
class StandardProgramApplication:
    """A standard watering program."""

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

    value: int = 0
    label: str = ""


@dataclass
class ScheduledZoneRun:
    """A scheduled zone run."""

    id: str = 0
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
    runs: list[ScheduledZoneRun] = field(default_factory=list)


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
    start_time: datetime = field(
        metadata=DateTime.conversion(), default_factory=default_datetime
    )
    end_time: datetime = field(
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
class ControllerFirmware:
    """Information about the controller's firmware."""

    type: str = ""
    version: str = ""


@dataclass
class ControllerModel:
    """Information about a controller model."""

    name: str = ""
    description: str = ""


@dataclass
class ControllerHardware:
    """Information about a controller's hardware."""

    serial_number: str = ""
    version: str = ""
    status: str = ""
    model: ControllerModel = field(default_factory=ControllerModel)
    firmware: list[ControllerFirmware] = field(default_factory=list)


@dataclass
class SensorModel:
    """Information about a sensor model."""

    id: int = 0
    name: str = ""
    active: bool = False
    off_level: int = 0
    off_timer: int = 0
    delay: int = 0
    divisor: float = 0.0
    flow_rate: float = 0.0


@dataclass
class SensorStatus:
    """Current status of a sensor."""

    water_flow: Optional[LocalizedValueType] = None
    active: bool = False


@dataclass
class SensorFlowSummary:
    """Summary of a sensor's water flow."""

    total_water_volume: LocalizedValueType = field(default_factory=LocalizedValueType)


@dataclass
class Sensor:
    """A sensor connected to a controller."""

    id: int = 0
    name: str = ""
    model: SensorModel = field(default_factory=SensorModel)
    status: SensorStatus = field(default_factory=SensorStatus)


@dataclass
class WaterTime:
    """A water time duration."""

    value: timedelta = field(
        metadata=_duration_conversion("minutes"), default=timedelta()
    )


@dataclass
class ControllerStatus:
    """Current status of a controller."""

    summary: str = ""
    online: bool = False
    actual_water_time: WaterTime = field(default_factory=WaterTime)
    normal_water_time: WaterTime = field(default_factory=WaterTime)
    last_contact: Optional[DateTime] = None


@dataclass
class Controller:
    """A Hydrawise controller."""

    id: int = 0
    name: str = ""
    software_version: str = ""
    hardware: ControllerHardware = field(default_factory=ControllerHardware)
    last_contact_time: datetime = field(
        metadata=DateTime.conversion(), default_factory=default_datetime
    )
    last_action: datetime = field(
        metadata=DateTime.conversion(), default_factory=default_datetime
    )
    online: bool = False
    sensors: list[Sensor] = field(default_factory=list)
    zones: list[Zone] = field(default_factory=list, metadata=skip(deserialization=True))
    permitted_program_start_times: list[ProgramStartTime] = field(default_factory=list)
    status: Optional[ControllerStatus] = None


@dataclass
class User:
    """A Hydrawise user account."""

    id: int = 0
    customer_id: int = 0
    name: str = ""
    email: str = ""
    controllers: list[Controller] = field(
        default_factory=list, metadata=skip(deserialization=True)
    )


class Query(ABC):
    """GraphQL schema for queries.

    :meta private:
    """

    @staticmethod
    @abstractmethod
    def me() -> User:
        """Returns the current user.

        :meta private:
        """

    @staticmethod
    @abstractmethod
    def controller(controller_id: int) -> Controller:
        """Returns a controller by its unique identifier.

        :meta private:
        """

    @staticmethod
    @abstractmethod
    def zone(zone_id: int) -> Zone:
        """Returns a zone by its unique identifier.

        :meta private:
        """


class Mutation(ABC):
    """GraphQL schema for mutations.

    :meta private:
    """

    @staticmethod
    @abstractmethod
    def start_zone(
        zone_id: int, mark_run_as_scheduled: bool = False, custom_run_duration: int = 0
    ) -> StatusCodeAndSummary:
        """Starts a zone.

        :meta private:
        """

    @staticmethod
    @abstractmethod
    def stop_zone(zone_id: int) -> StatusCodeAndSummary:
        """Stops a zone.

        :meta private:
        """

    @staticmethod
    @abstractmethod
    def suspend_zone(zone_id: int, until: str) -> StatusCodeAndSummary:
        """Suspends a zone.

        :meta private:
        """

    @staticmethod
    @abstractmethod
    def resume_zone(zone_id: int) -> StatusCodeAndSummary:
        """Resumes a zone.

        :meta private:
        """

    @staticmethod
    @abstractmethod
    def start_all_zones(
        controller_id: int,
        mark_run_as_scheduled: bool = False,
        custom_run_duration: int = 0,
    ) -> StatusCodeAndSummary:
        """Starts all zones.

        :meta private:
        """

    @staticmethod
    @abstractmethod
    def stop_all_zones(controller_id: int) -> StatusCodeAndSummary:
        """Stops all zones.

        :meta private:
        """

    @staticmethod
    @abstractmethod
    def suspend_all_zones(controller_id: int, until: str) -> StatusCodeAndSummary:
        """Suspends all zones.

        :meta private:
        """

    @staticmethod
    @abstractmethod
    def resume_all_zones(controller_id: int) -> StatusCodeAndSummary:
        """Resumes all zones.

        :meta private:
        """

    @staticmethod
    @abstractmethod
    def delete_zone_suspension(id: int) -> bool:  # pylint: disable=redefined-builtin
        """Deletes a zone suspension.

        :meta private:
        """
