"""GraphQL API schema for pydrawise."""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections import namedtuple
from dataclasses import dataclass, field, fields, is_dataclass
from datetime import datetime, timedelta, timezone
from enum import auto, Enum
from functools import cache
from typing import (
    Iterator,
    List,
    Optional,
    Type,
    Union,
    get_args,
    get_origin,
    get_type_hints,
)

from apischema import deserialize as _deserialize
from apischema.conversions import Conversion
from apischema.graphql import graphql_schema
from apischema.metadata import conversion, skip
from apischema.metadata.keys import CONVERSION_METADATA, SKIP_METADATA
from apischema.utils import to_camel_case
from gql.dsl import DSLField, DSLInlineFragment, DSLSchema
from graphql import GraphQLSchema

from .auth import Auth
from .exceptions import NotAuthenticatedError


# For compatibility with < python 3.10.
NoneType = type(None)


def deserialize(*args, **kwargs):
    kwargs.setdefault("aliaser", to_camel_case)
    return _deserialize(*args, **kwargs)


@cache
def get_schema() -> GraphQLSchema:
    return graphql_schema(
        query=[Query.me, Query.controller, Query.zone],
        mutation=[
            Mutation.start_zone,
            Mutation.stop_zone,
            Mutation.suspend_zone,
            Mutation.resume_zone,
            Mutation.start_all_zones,
            Mutation.stop_all_zones,
            Mutation.suspend_all_zones,
            Mutation.resume_all_zones,
        ],
    )


_Field = namedtuple("_Field", ["name", "types"])


def _fields(cls) -> Iterator[_Field]:
    hints = get_type_hints(cls)
    for f in fields(cls):
        skip_md = f.metadata.get(SKIP_METADATA, None)
        if skip_md and (skip_md.serialization or skip_md.deserialization):
            continue

        conversion_md = f.metadata.get(CONVERSION_METADATA, None)
        if conversion_md:
            yield _Field(f.name, [conversion_md.deserialization.source])
            continue

        field_type = hints[f.name]
        origin = get_origin(field_type)

        if origin == Union:
            # Drop None from Optional fields.
            field_types = set(get_args(field_type)) - {NoneType}
            if len(field_types) == 1:
                [field_type] = field_types
            else:
                yield _Field(f.name, list(field_types))
                continue
        elif origin in (List, list):
            # Extract the contained type.
            # We assume all list types are uniform.
            [field_type] = get_args(field_type)

        yield _Field(f.name, [field_type])


def get_selectors(ds: DSLSchema, cls: Type) -> list[DSLField]:
    ret = []
    for f in _fields(cls):
        dsl_field = getattr(getattr(ds, cls.__name__), f.name)
        if len(f.types) == 1:
            [f_type] = f.types
            if is_dataclass(f_type):
                ret.append(getattr(dsl_field, "select")(*get_selectors(ds, f_type)))
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
                    .on(getattr(ds, f_type.__name__))
                    .select(*get_selectors(ds, f_type))
                )
            ret.append(getattr(dsl_field, "select")(*sel_args))
    return ret


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
class ProgramStartTimeApplication:

    all: bool
    zones: [BaseZone]


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
class BaseZone:

    id: int
    number: Option
    name: str


@dataclass
class Zone(BaseZone):

    watering_settings: Union[AdvancedWateringSettings, StandardWateringSettings]
    scheduled_runs: ScheduledZoneRuns
    past_runs: PastZoneRuns
    status: ZoneStatus
    suspensions: list[ZoneSuspension] = field(default_factory=list)

    _auth: Optional[Auth] = field(
        default=None,
        init=False,
        repr=False,
        metadata=skip(serialization=True, deserialization=True),
    )

    async def start(
        self,
        mark_run_as_scheduled: bool = False,
        custom_run_duration: Optional[int] = None,
    ):
        if not self._auth:
            raise NotAuthenticatedError
        ds = DSLSchema(get_schema())
        kwargs = {
            "zoneId": self.id,
            "markRunAsScheduled": mark_run_as_scheduled,
        }
        if custom_run_duration is not None:
            kwargs["customRunDuration"] = custom_run_duration

        selector = ds.Mutation.startZone.args(**kwargs).select(
            *get_selectors(ds, StatusCodeAndSummary),
        )
        await self._auth.mutation(selector)

    async def stop(self) -> None:
        if not self._auth:
            raise NotAuthenticatedError
        ds = DSLSchema(get_schema())
        selector = ds.Mutation.stopZone.args(zoneId=self.id).select(
            *get_selectors(ds, StatusCodeAndSummary),
        )
        await self._auth.mutation(selector)

    async def suspend(self, until: datetime) -> None:
        if not self._auth:
            raise NotAuthenticatedError
        ds = DSLSchema(get_schema())
        selector = ds.Mutation.suspendZone.args(
            zoneId=self.id,
            until=DateTime.to_json(until).value,
        ).select(*get_selectors(ds, StatusCodeAndSummary))
        await self._auth.mutation(selector)

    async def resume(self) -> None:
        if not self._auth:
            raise NotAuthenticatedError
        ds = DSLSchema(get_schema())
        selector = ds.Mutation.resumeZone.args(zoneId=self.id).select(
            *get_selectors(ds, StatusCodeAndSummary),
        )
        await self._auth.mutation(selector)


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

    _auth: Optional[Auth] = field(
        default=None,
        init=False,
        repr=False,
        metadata=skip(serialization=True, deserialization=True),
    )

    async def get_zones(self) -> list[Zone]:
        if not self._auth:
            raise NotAuthenticatedError
        ds = DSLSchema(get_schema())
        selector = ds.Query.controller(controllerId=self.id).select(
            ds.Controller.zones.select(*get_selectors(ds, Zone)),
        )
        result = await self._auth.query(selector)
        zones = deserialize(list[Zone], result["controller"]["zones"])
        for zone in zones:
            zone._auth = self._auth
        return zones

    async def start_all_zones(
        self, mark_run_as_scheduled: bool = False, custom_run_duration: int = 0
    ) -> None:
        if not self._auth:
            raise NotAuthenticatedError
        ds = DSLSchema(get_schema())
        kwargs = {
            "controllerId": self.id,
            "markRunAsScheduled": mark_run_as_scheduled,
        }
        if custom_run_duration > 0:
            kwargs["customRunDuration"] = custom_run_duration

        selector = ds.Mutation.startAllZones.args(**kwargs).select(
            *get_selectors(ds, StatusCodeAndSummary),
        )
        await self._auth.mutation(selector)

    async def stop_all_zones(self) -> None:
        if not self._auth:
            raise NotAuthenticatedError
        ds = DSLSchema(get_schema())
        selector = ds.Mutation.stopAllZones.args(controllerId=self.id).select(
            *get_selectors(ds, StatusCodeAndSummary),
        )
        await self._auth.mutation(selector)

    async def suspend_all_zones(self, until: datetime) -> None:
        if not self._auth:
            raise NotAuthenticatedError
        ds = DSLSchema(get_schema())
        selector = ds.Mutation.suspendZone.args(
            controllerId=self.id,
            until=DateTime.to_json(until).value,
        ).select(*get_selectors(ds, StatusCodeAndSummary))
        await self._auth.mutation(selector)

    async def resume_all_zones(self) -> None:
        if not self._auth:
            raise NotAuthenticatedError
        ds = DSLSchema(get_schema())
        selector = ds.Mutation.resumeAllZones.args(controllerId=self.id).select(
            *get_selectors(ds, StatusCodeAndSummary),
        )
        await self._auth.mutation(selector)


@dataclass
class User:

    id: int
    name: str
    email: str
    controllers: list[Controller] = field(
        default_factory=list, metadata=skip(deserialization=True)
    )

    _auth: Optional[Auth] = field(
        default=None,
        init=False,
        repr=False,
        metadata=skip(serialization=True, deserialization=True),
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
