"""Asynchronous client library for interacting with Hydrawise's GraphQL API."""

import logging
from collections.abc import Iterable, Iterator
from contextlib import contextmanager
from datetime import datetime, timedelta
from typing import Any

import aiohttp
from gql import Client
from gql.dsl import (
    DSLField,
    DSLInlineFragment,
    DSLMutation,
    DSLQuery,
    DSLSelectable,
    dsl_gql,
)
from gql.transport.aiohttp import AIOHTTPTransport
from gql.transport.aiohttp import log as gql_log
from gql.transport.exceptions import (
    TransportAlreadyConnected,
    TransportError,
    TransportServerError,
)

from .auth import Auth
from .base import HydrawiseBase
from .const import DEFAULT_APP_ID, GRAPHQL_TIMEOUT, GRAPHQL_URL
from .exceptions import APIError, MutationError, NotAuthorizedError
from .schema import (
    DSL_SCHEMA,
    Controller,
    ControllerWaterUseSummary,
    CustomSensorTypeEnum,
    DateTime,
    DaysOfWeekEnum,
    LocalizedValueType,
    Sensor,
    SensorFlowSummary,
    SensorWithFlowSummary,
    StandardProgram,
    StandardProgramApplication,
    StatusCodeAndSummary,
    User,
    WateringProgramAdjustment,
    WateringReportEntry,
    Zone,
    ZoneSuspension,
    _StandardProgramDetails,
)
from .schema_utils import deserialize, get_selectors

# GQL is quite chatty in logs by default.
gql_log.setLevel(logging.ERROR)

_LOGGER = logging.getLogger("pydrawise")


@contextmanager
def _translate_errors() -> Iterator[None]:
    """Translates transport-level errors into pydrawise exceptions."""
    try:
        yield
    except TransportServerError as e:
        if e.code in (401, 403):
            raise NotAuthorizedError(f"HTTP {e.code}") from e
        raise APIError(str(e)) from e
    except (TransportError, aiohttp.ClientError, TimeoutError) as e:
        raise APIError(str(e)) from e


class _SharedSessionTransport(AIOHTTPTransport):
    """Transport that borrows a ClientSession owned by someone else.

    gql's AIOHTTPTransport creates its own session when it connects and closes
    it on exit. A caller-supplied session outlives any one query, so neither
    half of that is right here: connecting adopts the session as-is, and
    closing merely detaches from it.
    """

    def __init__(
        self, *args: Any, session: aiohttp.ClientSession, **kwargs: Any
    ) -> None:
        """Initializer.

        :param session: The session to use. Never closed by this transport.
        """
        super().__init__(*args, **kwargs)
        self._shared_session = session

    async def connect(self) -> None:
        """Adopts the caller-supplied session."""
        if self.session is not None:
            raise TransportAlreadyConnected("Transport is already connected")
        self.session = self._shared_session

    async def close(self) -> None:
        """Detaches from the caller-supplied session without closing it."""
        self.session = None


_DAY_ORDER = (
    DaysOfWeekEnum.SUNDAY,
    DaysOfWeekEnum.MONDAY,
    DaysOfWeekEnum.TUESDAY,
    DaysOfWeekEnum.WEDNESDAY,
    DaysOfWeekEnum.THURSDAY,
    DaysOfWeekEnum.FRIDAY,
    DaysOfWeekEnum.SATURDAY,
)


def _days_to_day_pattern(days: Iterable[DaysOfWeekEnum]) -> str:
    """Converts a collection of weekdays into a 7-character Hydrawise dayPattern.

    Characters are ordered Sunday through Saturday, with ``"1"`` for active
    days and ``"0"`` for inactive days (e.g. ``"0010100"`` for Tuesday and
    Thursday, ``"0000000"`` for no days).
    """
    day_set = set(days)
    invalid = day_set - set(_DAY_ORDER)
    if invalid:
        raise ValueError(f"Invalid days: {invalid!r}")
    return "".join("1" if day in day_set else "0" for day in _DAY_ORDER)


def _prune_watering_report_entries(
    entries: list[WateringReportEntry], start: datetime, end: datetime
) -> list[WateringReportEntry]:
    """Prune watering report entries to make sure they all fall inside the [start, end] time interval.

    The call to watering() can return events outside of the provided time interval.
    Filter out events that happen before or after the provided time interval.
    """
    return list(
        filter(
            lambda entry: (
                entry.run_event is not None
                and entry.run_event.reported_start_time is not None
                and entry.run_event.reported_end_time is not None
                and (
                    (
                        start.timestamp()
                        <= entry.run_event.reported_start_time.timestamp()
                        <= end.timestamp()
                    )
                    or (
                        start.timestamp()
                        <= entry.run_event.reported_end_time.timestamp()
                        <= end.timestamp()
                    )
                )
            ),
            entries,
        )
    )


class Hydrawise(HydrawiseBase):
    """Client library for interacting with Hydrawise sprinkler controllers.

    Should be instantiated with an Auth object that handles authentication and low-level transport.
    """

    def __init__(self, auth: Auth, app_id: str = DEFAULT_APP_ID) -> None:
        """Initializes the client.

        :param auth: Handles authentication and transport.
        :param app_id: Unique identifier for the application accessing the Hydrawise API.
        """
        self._auth = auth
        self._app_id = app_id

    def _client(self) -> Client:
        transport: AIOHTTPTransport
        if (session := self._auth.session) is not None:
            transport = _SharedSessionTransport(url=GRAPHQL_URL, session=session)
        else:
            transport = AIOHTTPTransport(url=GRAPHQL_URL)
        return Client(transport=transport, parse_results=True)

    async def _request_args(self) -> dict[str, Any]:
        """Builds the arguments to send with a single request.

        The authorization header and the timeout are sent per-request rather
        than installed on the session: a caller-supplied session is shared with
        unrelated callers, so it must not carry our credentials and its own
        timeout shouldn't decide how long we wait. gql only applies
        transport-level headers to sessions it creates itself anyway.
        """
        return {
            "headers": {"Authorization": await self._auth.token()},
            "timeout": GRAPHQL_TIMEOUT,
        }

    async def _query(self, selector: DSLSelectable) -> dict:
        with _translate_errors():
            extra_args = await self._request_args()
            if self._app_id:
                extra_args["params"] = {"appVersion": self._app_id}
            async with self._client() as session:
                return await session.execute(
                    dsl_gql(DSLQuery(selector)),
                    extra_args=extra_args,
                )

    async def _mutation(self, selector: DSLField) -> None:
        with _translate_errors():
            extra_args = await self._request_args()
            async with self._client() as session:
                result = await session.execute(
                    dsl_gql(DSLMutation(selector)),
                    extra_args=extra_args,
                )
        resp = result[selector.name]
        if isinstance(resp, dict):
            status = resp.get("status")
            if status == "ERROR":
                raise MutationError(resp["summary"])
            elif status == "WARNING":
                # Not a problem: the API accepted the command, and the summary
                # says when the controller will act on it ("Starting Zone 1 in
                # 14 seconds"). Logging it as a warning floods callers' logs.
                _LOGGER.debug(resp["summary"])
            return
        elif not resp:
            # Assume bool or nullable object response
            raise MutationError

    async def get_user(self, fetch_zones: bool = True) -> User:
        """Retrieves the currently authenticated user.

        :param fetch_zones: Whether to include zones in the controller response.
        :rtype: User
        """
        skip = [] if fetch_zones else ["controllers.zones"]
        if fetch_zones:
            skip.append("controllers.zones.past_runs")
        result = await self._query(
            DSL_SCHEMA.Query.me.select(*get_selectors(User, skip))
        )
        return deserialize(User, result["me"])

    async def get_controllers(
        self, fetch_zones: bool = True, fetch_sensors: bool = True
    ) -> list[Controller]:
        """Retrieves all controllers associated with the currently authenticated user.

        :param fetch_zones: Whether to include zones in the response.
        :param fetch_sensors: Whether to include sensors in the response.
        :rtype: list[Controller]
        """
        skip = []
        if not fetch_zones:
            skip.append("zones")
        else:
            skip.append("zones.past_runs")
        if not fetch_sensors:
            skip.append("sensors")

        result = await self._query(
            DSL_SCHEMA.Query.me.select(
                DSL_SCHEMA.User.controllers.select(*get_selectors(Controller, skip)),
            )
        )
        return deserialize(list[Controller], result["me"]["controllers"])

    async def get_controller(self, controller_id: int) -> Controller:
        """Retrieves a single controller by its unique identifier.

        :param controller_id: Unique identifier for the controller to retrieve.
        :rtype: Controller
        """
        result = await self._query(
            DSL_SCHEMA.Query.controller(controllerId=controller_id).select(
                *get_selectors(Controller, ["zones.past_runs"]),
            )
        )
        return deserialize(Controller, result["controller"])

    async def get_zones(self, controller: Controller) -> list[Zone]:
        """Retrieves zones associated with the given controller.

        :param controller: Controller whose zones to fetch.
        :rtype: list[Zone]
        """
        result = await self._query(
            DSL_SCHEMA.Query.controller(controllerId=controller.id).select(
                DSL_SCHEMA.Controller.zones.select(*get_selectors(Zone, ["past_runs"])),
            )
        )
        return deserialize(list[Zone], result["controller"]["zones"])

    async def get_zone(self, zone_id: int) -> Zone:
        """Retrieves a zone by its unique identifier.

        :param zone_id: The zone's unique identifier.
        :rtype: Zone
        """
        result = await self._query(
            DSL_SCHEMA.Query.zone(zoneId=zone_id).select(
                *get_selectors(Zone, ["past_runs"])
            )
        )
        return deserialize(Zone, result["zone"])

    async def start_zone(
        self,
        zone: Zone,
        mark_run_as_scheduled: bool = False,
        custom_run_duration: int = 0,
    ) -> None:
        """Starts a zone's run cycle.

        :param zone: The zone to start.
        :param mark_run_as_scheduled: Whether to mark the zone as having run as scheduled.
        :param custom_run_duration: Duration (in seconds) to run the zone. If not
            specified (or zero), will run for its default configured time.
        """
        kwargs = {
            "zoneId": zone.id,
            "markRunAsScheduled": mark_run_as_scheduled,
        }
        if custom_run_duration > 0:
            kwargs["customRunDuration"] = custom_run_duration

        await self._mutation(
            DSL_SCHEMA.Mutation.startZone.args(**kwargs).select(
                *get_selectors(StatusCodeAndSummary),
            )
        )

    async def stop_zone(self, zone: Zone) -> None:
        """Stops a zone.

        :param zone: The zone to stop.
        """
        await self._mutation(
            DSL_SCHEMA.Mutation.stopZone.args(zoneId=zone.id).select(
                *get_selectors(StatusCodeAndSummary),
            )
        )

    async def start_all_zones(
        self,
        controller: Controller,
        mark_run_as_scheduled: bool = False,
        custom_run_duration: int = 0,
    ) -> None:
        """Starts all zones attached to a controller.

        :param controller: The controller whose zones to start.
        :param mark_run_as_scheduled: Whether to mark the zones as having run as scheduled.
        :param custom_run_duration: Duration (in seconds) to run the zones. If not
            specified (or zero), will run for each zone's default configured time.
        """
        kwargs = {
            "controllerId": controller.id,
            "markRunAsScheduled": mark_run_as_scheduled,
        }
        if custom_run_duration > 0:
            kwargs["customRunDuration"] = custom_run_duration

        await self._mutation(
            DSL_SCHEMA.Mutation.startAllZones.args(**kwargs).select(
                *get_selectors(StatusCodeAndSummary),
            )
        )

    async def stop_all_zones(self, controller: Controller) -> None:
        """Stops all zones attached to a controller.

        :param controller: The controller whose zones to stop.
        """
        await self._mutation(
            DSL_SCHEMA.Mutation.stopAllZones.args(controllerId=controller.id).select(
                *get_selectors(StatusCodeAndSummary),
            )
        )

    async def suspend_zone(self, zone: Zone, until: datetime) -> None:
        """Suspends a zone's schedule.

        :param zone: The zone to suspend.
        :param until: When the suspension should end.
        """
        await self._mutation(
            DSL_SCHEMA.Mutation.suspendZone.args(
                zoneId=zone.id,
                until=DateTime.to_json(until).value,
            ).select(
                *get_selectors(StatusCodeAndSummary),
            )
        )

    async def resume_zone(self, zone: Zone) -> None:
        """Resumes a zone's schedule.

        :param zone: The zone whose schedule to resume.
        """
        await self._mutation(
            DSL_SCHEMA.Mutation.resumeZone.args(zoneId=zone.id).select(
                *get_selectors(StatusCodeAndSummary),
            )
        )

    async def suspend_all_zones(self, controller: Controller, until: datetime) -> None:
        """Suspends the schedule of all zones attached to a given controller.

        :param controller: The controller whose zones to suspend.
        :param until: When the suspension should end.
        """
        await self._mutation(
            DSL_SCHEMA.Mutation.suspendAllZones.args(
                controllerId=controller.id,
                until=DateTime.to_json(until).value,
            ).select(
                *get_selectors(StatusCodeAndSummary),
            )
        )

    async def resume_all_zones(self, controller: Controller) -> None:
        """Resumes the schedule of all zones attached to the given controller.

        :param controller: The controller whose zones to resume.
        """
        await self._mutation(
            DSL_SCHEMA.Mutation.resumeAllZones.args(controllerId=controller.id).select(
                *get_selectors(StatusCodeAndSummary),
            )
        )

    async def delete_zone_suspension(self, suspension: ZoneSuspension) -> None:
        """Removes a specific zone suspension.

        Useful when there are multiple suspensions for a zone in effect.

        :param suspension: The suspension to delete.
        """
        await self._mutation(
            DSL_SCHEMA.Mutation.deleteZoneSuspension.args(id=suspension.id).select()
        )

    async def get_sensors(self, controller: Controller) -> list[Sensor]:
        """Retrieves sensors associated with the given controller.

        :param controller: Controller whose sensors to fetch.
        :rtype: list[Sensor]
        """
        result = await self._query(
            DSL_SCHEMA.Query.controller(controllerId=controller.id).select(
                DSL_SCHEMA.Controller.sensors.select(*get_selectors(Sensor)),
            )
        )
        return deserialize(list[Sensor], result["controller"]["sensors"])

    async def update_master_valve(self, controller: Controller, zone: Zone) -> None:
        """Updates the controller's master valve.

        :param controller: Controller whose master valve to update.
        :param zone: Zone to use as the controller's master valve.
        """
        await self._mutation(
            DSL_SCHEMA.Mutation.updateControllerMasterValve.args(
                zoneNumber=zone.number.value, controllerId=controller.id
            ).select()
        )

    async def get_water_flow_summary(
        self, controller: Controller, sensor: Sensor, start: datetime, end: datetime
    ) -> SensorFlowSummary:
        """Retrieves the water flow summary for a given sensor.

        :param controller: Controller that controls the sensor.
        :param sensor: Sensor for which a water flow summary is fetched.
        :param start: Start time.
        :param end: End time.
        :rtype: SensorFlowSummary
        """
        result = await self._query(
            DSL_SCHEMA.Query.controller(controllerId=controller.id).select(
                DSL_SCHEMA.Controller.sensors.select(
                    *get_selectors(Sensor),
                    DSL_SCHEMA.Sensor.flowSummary(
                        start=int(start.timestamp()),
                        end=int(end.timestamp()),
                    ).select(*get_selectors(SensorFlowSummary)),
                ),
            )
        )

        # There is no way to query for one particular sensor through GraphQL. We need
        # to filter here instead. This should not really be a performance problem in
        # practice since it is unlikely for a controller to have more than one water
        # sensor.
        sensors = list(
            filter(lambda s: s["id"] == sensor.id, result["controller"]["sensors"])
        )
        if len(sensors) == 0:
            raise ValueError(f"Sensor with id={sensor.id} not found")
        if "flowSummary" not in sensors[0]:
            raise ValueError(
                f"Sensor with id={sensor.id} does not have any flow information"
            )
        if sensors[0]["flowSummary"] is None:
            return SensorFlowSummary(total_water_volume=LocalizedValueType(0.0, "gal"))
        return deserialize(SensorFlowSummary, sensors[0]["flowSummary"])

    async def get_watering_report(
        self, controller: Controller, start: datetime, end: datetime
    ) -> list[WateringReportEntry]:
        """Retrieves a watering report for the given controller and time period.

        :param controller: The controller whose watering report to generate.
        :param start: Start time.
        :param end: End time."""
        result = await self._query(
            DSL_SCHEMA.Query.controller(controllerId=controller.id).select(
                DSL_SCHEMA.Controller.reports.select(
                    DSL_SCHEMA.Reports.watering(
                        **{
                            "from": int(start.timestamp()),
                            "until": int(end.timestamp()),
                        }
                    ).select(*get_selectors(WateringReportEntry)),
                ),
            )
        )
        return _prune_watering_report_entries(
            deserialize(
                list[WateringReportEntry], result["controller"]["reports"]["watering"]
            ),
            start,
            end,
        )

    async def get_water_use_summary(
        self, controller: Controller, start: datetime, end: datetime
    ) -> ControllerWaterUseSummary:
        """Calculate the water use for the given controller and time period.

        :param controller: The controller whose water use to report.
        :param start: Start time
        :param end: End time."""
        has_flow_sensors = controller.sensors and any(
            s.model.sensor_type == CustomSensorTypeEnum.FLOW for s in controller.sensors
        )
        selectors = [
            # Request the watering report that contains both the
            # amount of water used as well as the watering time.
            DSL_SCHEMA.Controller.reports.select(
                DSL_SCHEMA.Reports.watering(
                    **{
                        "from": int(start.timestamp()),
                        "until": int(end.timestamp()),
                    }
                ).select(*get_selectors(WateringReportEntry)),
            )
        ]
        if has_flow_sensors:
            # Only request the flow summary in the presence of flow sensors
            selectors.append(
                DSL_SCHEMA.Controller.sensors.select(
                    *get_selectors(Sensor),
                    DSL_SCHEMA.Sensor.flowSummary(
                        start=int(start.timestamp()),
                        end=int(end.timestamp()),
                    ).select(*get_selectors(SensorFlowSummary)),
                )
            )
        result = await self._query(
            DSL_SCHEMA.Query.controller(controllerId=controller.id).select(*selectors)
        )

        # watering report entries
        entries = _prune_watering_report_entries(
            deserialize(
                list[WateringReportEntry], result["controller"]["reports"]["watering"]
            ),
            start,
            end,
        )

        # total active water use and time
        summary = ControllerWaterUseSummary()
        total_active_use = 0.0
        total_use = 0.0
        total_inactive_use = 0.0
        for entry in entries:
            if entry.run_event is None or entry.run_event.zone is None:
                continue

            if entry.run_event.reported_water_usage is not None and has_flow_sensors:
                active_use = entry.run_event.reported_water_usage.value
                if summary.unit is None:
                    summary.unit = entry.run_event.reported_water_usage.unit
                total_active_use += active_use
                summary.active_use_by_zone_id.setdefault(entry.run_event.zone.id, 0)
                summary.active_use_by_zone_id[entry.run_event.zone.id] += active_use

            active_time = entry.run_event.reported_duration
            summary.total_active_time += active_time
            summary.active_time_by_zone_id.setdefault(
                entry.run_event.zone.id, timedelta()
            )
            summary.active_time_by_zone_id[entry.run_event.zone.id] += active_time

        if not has_flow_sensors:
            return summary

        # total inactive water use
        for sensor_json in result["controller"]["sensors"]:
            sensor = deserialize(SensorWithFlowSummary, sensor_json)
            if (
                sensor.flow_summary
                and sensor.model.sensor_type == CustomSensorTypeEnum.FLOW
            ):
                total_use += sensor.flow_summary.total_water_volume.value
                if summary.unit is None:
                    summary.unit = sensor.flow_summary.total_water_volume.unit

        # Correct for inaccuracies. The watering report and flow summaries are not always
        # updated with the same frequency.
        if total_use > total_active_use:
            total_inactive_use = total_use - total_active_use
        else:
            total_use = total_active_use

        summary.total_use = total_use
        summary.total_active_use = total_active_use
        summary.total_inactive_use = total_inactive_use
        return summary

    async def set_standard_program_days(
        self,
        controller: Controller,
        program: StandardProgram,
        days: Iterable[DaysOfWeekEnum],
    ) -> None:
        """Updates the run days of a standard watering program.

        Fetches the program's current configuration (including conditional
        watering adjustments and zone run times) before calling
        ``updateStandardProgram`` so that existing settings are preserved.
        Only programs using the day-of-week (``"dow"``) day pattern are
        supported.

        :param controller: The controller that owns the program.
        :param program: The standard program to update.
        :param days: Weekdays on which the program should run. Pass an empty
            iterable to disable all days.
        :raises ValueError: If the program is not found, does not use the
            ``"dow"`` day pattern, or an invalid day is provided.
        """
        day_pattern = _days_to_day_pattern(days)
        if (
            program.standard_program_day_pattern
            and program.standard_program_day_pattern != "dow"
        ):
            raise ValueError(
                "Only 'dow' day pattern is supported, "
                f"got {program.standard_program_day_pattern!r}"
            )

        result = await self._query(
            DSL_SCHEMA.Query.controller(controllerId=controller.id).select(
                DSL_SCHEMA.Controller.programs.select(
                    DSLInlineFragment()
                    .on(DSL_SCHEMA.StandardProgram)
                    .select(
                        *get_selectors(StandardProgram),
                        DSL_SCHEMA.StandardProgram.conditionalWateringAdjustments(
                            controllerId=controller.id
                        ).select(*get_selectors(WateringProgramAdjustment)),
                        DSL_SCHEMA.StandardProgram.applications.select(
                            *get_selectors(
                                StandardProgramApplication, ["standard_program"]
                            )
                        ),
                    )
                )
            )
        )
        programs = (result.get("controller") or {}).get("programs") or []
        matched = [p for p in programs if p.get("id") == program.id]
        if not matched:
            raise ValueError(f"Standard program with id={program.id} not found")

        current = deserialize(_StandardProgramDetails, matched[0])
        if current.standard_program_day_pattern != "dow":
            raise ValueError(
                "Only 'dow' day pattern is supported, "
                f"got {current.standard_program_day_pattern!r}"
            )

        valid_from = (
            int(current.time_range.valid_from.timestamp())
            if current.time_range.valid_from is not None
            else None
        )
        valid_to = (
            int(current.time_range.valid_to.timestamp())
            if current.time_range.valid_to is not None
            else None
        )
        zone_run_times = [
            {
                "zoneNumber": app.zone.number.value,
                "runTimeGroupId": None,
                "runDuration": int(app.run_time_group.duration.total_seconds() // 60),
            }
            for app in current.applications
        ]

        await self._mutation(
            DSL_SCHEMA.Mutation.updateStandardProgram.args(
                programId=current.id,
                controllerId=controller.id,
                name=current.name,
                programType=current.scheduling_method.value,
                dayPattern=day_pattern,
                standardProgramDayPattern="dow",
                startTimes=[t.strftime("%H:%M") for t in current.start_times],
                zoneRunTimes=zone_run_times,
                scheduleAdjustmentIds=[
                    adj.id for adj in current.conditional_watering_adjustments
                ],
                seasonalAdjustmentFactors=current.monthly_watering_adjustments,
                validFrom=valid_from,
                validTo=valid_to,
                ignoreRainSensor=current.ignore_rain_sensor,
            ).select(DSL_SCHEMA.StandardProgram.id)
        )
