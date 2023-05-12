"""GraphQL API schema for pydrawise."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from enum import Enum, auto
from typing import Optional, Union

from apischema.conversions import Conversion
from apischema.metadata import conversion, skip


class StatusCodeEnum(Enum):
    OK = auto()
    WARNING = auto()
    ERROR = auto()


@dataclass
class StatusCodeAndSummary:
    status: StatusCodeEnum
    summary: str


@dataclass
class LocalizedValueType:
    value: float
    unit: str


@dataclass
class Option:
    value: int
    label: str


@dataclass
class DateTime:
    value: str
    timestamp: int

    @staticmethod
    def from_json(dt: DateTime) -> datetime:
        return datetime.fromtimestamp(dt.timestamp)

    @staticmethod
    def to_json(dt: datetime) -> DateTime:
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
        return conversion(
            Conversion(DateTime.from_json, source=DateTime, target=datetime),
            Conversion(DateTime.to_json, source=datetime, target=DateTime),
        )


duration_conversion = conversion(
    Conversion(lambda d: timedelta(minutes=d), source=int, target=timedelta),
    Conversion(lambda d: d.minutes, source=timedelta, target=int),
)


@dataclass
class CycleAndSoakSettings:
    cycle_duration: timedelta = field(metadata=duration_conversion)
    soak_duration: timedelta = field(metadata=duration_conversion)


@dataclass
class RunTimeGroup:
    id: int
    duration: timedelta = field(metadata=duration_conversion)


@dataclass
class AdvancedProgram:
    advanced_program_id: int
    run_time_group: RunTimeGroup


class AdvancedProgramDayPatternEnum(Enum):
    def _generate_next_value_(name, start, count, last_values):
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
class BaseZone:
    id: int
    number: Option
    name: str


@dataclass
class ProgramStartTimeApplication:
    all: bool
    zones: list[BaseZone]


@dataclass
class ProgramStartTime:
    id: int
    time: str  # e.g. "02:00"
    watering_days: list[AdvancedProgramDayPatternEnum]


@dataclass
class WateringSettings:
    fixed_watering_adjustment: int
    cycle_and_soak_settings: Optional[CycleAndSoakSettings]


@dataclass
class AdvancedWateringSettings(WateringSettings):
    advanced_program: Optional[AdvancedProgram]


@dataclass
class StandardProgram:
    name: str
    start_times: list[str]


@dataclass
class StandardProgramApplication:
    zone: BaseZone
    standard_program: StandardProgram
    run_time_group: RunTimeGroup


@dataclass
class StandardWateringSettings(WateringSettings):
    standard_program_applications: list[StandardProgramApplication]


@dataclass
class RunStatus:
    value: int
    label: str


@dataclass
class ScheduledZoneRun:
    id: str
    start_time: datetime = field(metadata=DateTime.conversion())
    end_time: datetime = field(metadata=DateTime.conversion())
    normal_duration: timedelta = field(metadata=duration_conversion)
    duration: timedelta = field(metadata=duration_conversion)
    status: RunStatus


@dataclass
class ScheduledZoneRuns:
    summary: str
    current_run: Optional[ScheduledZoneRun]
    next_run: Optional[ScheduledZoneRun]
    status: Optional[str]


@dataclass
class PastZoneRuns:
    last_run: Optional[ScheduledZoneRun]
    runs: list[ScheduledZoneRun]


@dataclass
class ZoneStatus:
    relative_water_balance: int
    suspended_until: datetime = field(metadata=DateTime.conversion())


@dataclass
class ZoneSuspension:
    id: int
    start_time: datetime = field(metadata=DateTime.conversion())
    end_time: datetime = field(metadata=DateTime.conversion())


@dataclass
class Zone(BaseZone):
    watering_settings: Union[AdvancedWateringSettings, StandardWateringSettings]
    scheduled_runs: ScheduledZoneRuns
    past_runs: PastZoneRuns
    status: ZoneStatus
    suspensions: list[ZoneSuspension] = field(default_factory=list)


@dataclass
class ControllerFirmware:
    type: str
    version: str


@dataclass
class ControllerModel:
    name: str
    description: str


@dataclass
class ControllerHardware:
    serial_number: str
    version: str
    status: str
    model: ControllerModel
    firmware: list[ControllerFirmware]


@dataclass
class SensorModel:
    id: int
    name: str
    active: bool
    off_level: int
    off_timer: int
    delay: int
    divisor: float
    flow_rate: float


@dataclass
class SensorStatus:
    water_flow: Optional[LocalizedValueType]
    active: bool


@dataclass
class SensorFlowSummary:
    total_water_volume: LocalizedValueType


@dataclass
class Sensor:
    id: int
    name: str
    model: SensorModel
    status: SensorStatus


@dataclass
class WaterTime:
    value: timedelta = field(metadata=duration_conversion)


@dataclass
class ControllerStatus:
    summary: str
    online: bool
    actual_water_time: WaterTime
    normal_water_time: WaterTime
    last_contact: Optional[DateTime] = None


@dataclass
class Controller:
    id: int
    name: str
    software_version: str
    hardware: ControllerHardware
    last_contact_time: datetime = field(metadata=DateTime.conversion())
    last_action: datetime = field(metadata=DateTime.conversion())
    online: bool
    sensors: list[Sensor]
    zones: list[Zone] = field(default_factory=list, metadata=skip(deserialization=True))
    permitted_program_start_times: list[ProgramStartTime] = field(default_factory=list)
    status: Optional[ControllerStatus] = field(default=None)


@dataclass
class User:
    id: int
    name: str
    email: str
    controllers: list[Controller] = field(
        default_factory=list, metadata=skip(deserialization=True)
    )


class Query(ABC):
    @staticmethod
    @abstractmethod
    def me() -> User:
        ...

    @staticmethod
    @abstractmethod
    def controller(controller_id: int) -> Controller:
        ...

    @staticmethod
    @abstractmethod
    def zone(zone_id: int) -> Zone:
        ...


class Mutation(ABC):
    @staticmethod
    @abstractmethod
    def start_zone(
        zone_id: int, mark_run_as_scheduled: bool = False, custom_run_duration: int = 0
    ) -> StatusCodeAndSummary:
        ...

    @staticmethod
    @abstractmethod
    def stop_zone(zone_id: int) -> StatusCodeAndSummary:
        ...

    @staticmethod
    @abstractmethod
    def suspend_zone(zone_id: int, until: str) -> StatusCodeAndSummary:
        ...

    @staticmethod
    @abstractmethod
    def resume_zone(zone_id: int) -> StatusCodeAndSummary:
        ...

    @staticmethod
    @abstractmethod
    def start_all_zones(
        controller_id: int,
        mark_run_as_scheduled: bool = False,
        custom_run_duration: int = 0,
    ) -> StatusCodeAndSummary:
        ...

    @staticmethod
    @abstractmethod
    def stop_all_zones(controller_id: int) -> StatusCodeAndSummary:
        ...

    @staticmethod
    @abstractmethod
    def suspend_all_zones(controller_id: int, until: str) -> StatusCodeAndSummary:
        ...

    @staticmethod
    @abstractmethod
    def resume_all_zones(controller_id: int) -> StatusCodeAndSummary:
        ...

    @staticmethod
    @abstractmethod
    def delete_zone_suspension(id: int) -> bool:
        ...
