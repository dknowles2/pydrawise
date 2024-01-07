"""Client library for interacting with Hydrawise's cloud API."""

from datetime import datetime
from functools import cache
from importlib import resources
import logging

from apischema.graphql import graphql_schema
from gql import Client
from gql.dsl import DSLField, DSLMutation, DSLQuery, DSLSchema, DSLSelectable, dsl_gql
from gql.transport.aiohttp import AIOHTTPTransport, log as gql_log
from graphql import GraphQLSchema, build_ast_schema, parse

from .auth import Auth
from .base import HydrawiseBase
from .exceptions import MutationError
from .schema import (
    Controller,
    ControllerWaterUseSummary,
    DateTime,
    LocalizedValueType,
    Sensor,
    SensorFlowSummary,
    StatusCodeAndSummary,
    User,
    WateringReportEntry,
    Zone,
    ZoneSuspension,
)
from .schema_utils import deserialize, get_selectors

# GQL is quite chatty in logs by default.
gql_log.setLevel(logging.ERROR)

API_URL = "https://app.hydrawise.com/api/v2/graph"


@cache
def _get_schema() -> GraphQLSchema:
    schema_text = resources.files(__package__).joinpath("hydrawise.graphql").read_text()
    return build_ast_schema(parse(schema_text))


def _prune_watering_report_entries(
    entries: list[WateringReportEntry], start: datetime, end: datetime
) -> list[WateringReportEntry]:
    """Prune watering report entries to make sure they all fall inside the [start, end] time interval.

    The call to watering() can return events outside of the provided time interval.
    Filter out events that happen before or after the provided time interval.
    """
    return list(
        filter(
            lambda entry: entry.run_event is not None
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
            ),
            entries,
        )
    )


class Hydrawise(HydrawiseBase):
    """Client library for interacting with Hydrawise sprinkler controllers.

    Should be instantiated with an Auth object that handles authentication and low-level transport.
    """

    def __init__(self, auth: Auth) -> None:
        """Initializes the client.

        :param auth: Handles authentication and transport.
        """
        self._auth = auth
        self._schema = DSLSchema(_get_schema())

    async def _client(self) -> Client:
        headers = {"Authorization": await self._auth.token()}
        transport = AIOHTTPTransport(url=API_URL, headers=headers)
        return Client(transport=transport, parse_results=True)

    async def _query(self, selector: DSLSelectable) -> dict:
        async with await self._client() as session:
            return await session.execute(dsl_gql(DSLQuery(selector)))

    async def _mutation(self, selector: DSLField) -> None:
        async with await self._client() as session:
            result = await session.execute(dsl_gql(DSLMutation(selector)))
            resp = result[selector.name]
            if isinstance(resp, dict):
                if resp["status"] != "OK":
                    raise MutationError(resp["summary"])
                return
            elif not resp:
                # Assume bool response
                raise MutationError

    async def get_user(self, fetch_zones: bool = True) -> User:
        """Retrieves the currently authenticated user.

        :param fetch_zones: Not used in this implementation.
        :rtype: User
        """
        skip = [] if fetch_zones else ["controllers.zones"]
        selector = self._schema.Query.me.select(
            *get_selectors(self._schema, User, skip)
        )
        result = await self._query(selector)
        return deserialize(User, result["me"])

    async def get_controllers(self) -> list[Controller]:
        """Retrieves all controllers associated with the currently authenticated user.

        :rtype: list[Controller]
        """
        selector = self._schema.Query.me.select(
            self._schema.User.controllers.select(
                *get_selectors(self._schema, Controller)
            ),
        )
        result = await self._query(selector)
        return deserialize(list[Controller], result["me"]["controllers"])

    async def get_controller(self, controller_id: int) -> Controller:
        """Retrieves a single controller by its unique identifier.

        :param controller_id: Unique identifier for the controller to retrieve.
        :rtype: Controller
        """
        selector = self._schema.Query.controller(controllerId=controller_id).select(
            *get_selectors(self._schema, Controller),
        )
        result = await self._query(selector)
        return deserialize(Controller, result["controller"])

    async def get_zones(self, controller: Controller) -> list[Zone]:
        """Retrieves zones associated with the given controller.

        :param controller: Controller whose zones to fetch.
        :rtype: list[Zone]
        """
        selector = self._schema.Query.controller(controllerId=controller.id).select(
            self._schema.Controller.zones.select(*get_selectors(self._schema, Zone)),
        )
        result = await self._query(selector)
        return deserialize(list[Zone], result["controller"]["zones"])

    async def get_zone(self, zone_id: int) -> Zone:
        """Retrieves a zone by its unique identifier.

        :param zone_id: The zone's unique identifier.
        :rtype: Zone
        """
        selector = self._schema.Query.zone(zoneId=zone_id).select(
            *get_selectors(self._schema, Zone)
        )
        result = await self._query(selector)
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

        selector = self._schema.Mutation.startZone.args(**kwargs).select(
            *get_selectors(self._schema, StatusCodeAndSummary),
        )
        await self._mutation(selector)

    async def stop_zone(self, zone: Zone) -> None:
        """Stops a zone.

        :param zone: The zone to stop.
        """
        selector = self._schema.Mutation.stopZone.args(zoneId=zone.id).select(
            *get_selectors(self._schema, StatusCodeAndSummary),
        )
        await self._mutation(selector)

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

        selector = self._schema.Mutation.startAllZones.args(**kwargs).select(
            *get_selectors(self._schema, StatusCodeAndSummary),
        )
        await self._mutation(selector)

    async def stop_all_zones(self, controller: Controller) -> None:
        """Stops all zones attached to a controller.

        :param controller: The controller whose zones to stop.
        """
        selector = self._schema.Mutation.stopAllZones.args(
            controllerId=controller.id
        ).select(
            *get_selectors(self._schema, StatusCodeAndSummary),
        )
        await self._mutation(selector)

    async def suspend_zone(self, zone: Zone, until: datetime) -> None:
        """Suspends a zone's schedule.

        :param zone: The zone to suspend.
        :param until: When the suspension should end.
        """
        selector = self._schema.Mutation.suspendZone.args(
            zoneId=zone.id,
            until=DateTime.to_json(until).value,
        ).select(
            *get_selectors(self._schema, StatusCodeAndSummary),
        )
        await self._mutation(selector)

    async def resume_zone(self, zone: Zone) -> None:
        """Resumes a zone's schedule.

        :param zone: The zone whose schedule to resume.
        """
        selector = self._schema.Mutation.resumeZone.args(zoneId=zone.id).select(
            *get_selectors(self._schema, StatusCodeAndSummary),
        )
        await self._mutation(selector)

    async def suspend_all_zones(self, controller: Controller, until: datetime) -> None:
        """Suspends the schedule of all zones attached to a given controller.

        :param controller: The controller whose zones to suspend.
        :param until: When the suspension should end.
        """
        selector = self._schema.Mutation.suspendAllZones.args(
            controllerId=controller.id,
            until=DateTime.to_json(until).value,
        ).select(
            *get_selectors(self._schema, StatusCodeAndSummary),
        )
        await self._mutation(selector)

    async def resume_all_zones(self, controller: Controller) -> None:
        """Resumes the schedule of all zones attached to the given controller.

        :param controller: The controller whose zones to resume.
        """
        selector = self._schema.Mutation.resumeAllZones.args(
            controllerId=controller.id
        ).select(
            *get_selectors(self._schema, StatusCodeAndSummary),
        )
        await self._mutation(selector)

    async def delete_zone_suspension(self, suspension: ZoneSuspension) -> None:
        """Removes a specific zone suspension.

        Useful when there are multiple suspensions for a zone in effect.

        :param suspension: The suspension to delete.
        """
        selector = self._schema.Mutation.deleteZoneSuspension.args(
            id=suspension.id
        ).select()
        await self._mutation(selector)

    async def get_sensors(self, controller: Controller) -> list[Sensor]:
        """Retrieves sensors associated with the given controller.

        :param controller: Controller whose sensors to fetch.
        :rtype: list[Sensor]
        """
        selector = self._schema.Query.controller(controllerId=controller.id).select(
            self._schema.Controller.sensors.select(
                *get_selectors(self._schema, Sensor)
            ),
        )

        result = await self._query(selector)
        return deserialize(list[Sensor], result["controller"]["sensors"])

    async def get_water_flow_summary(
        self, controller: Controller, sensor: Sensor, start: datetime, end: datetime
    ) -> SensorFlowSummary:
        """Retrieves the water flow summary for a given sensor.

        :param controller: Controller that controls the sensor.
        :param sensor: Sensor for which a water flow summary is fetched.
        :param start:
        :param end:
        :rtype: list[Sensor]
        """
        selector = self._schema.Query.controller(controllerId=controller.id).select(
            self._schema.Controller.sensors.select(
                *get_selectors(self._schema, Sensor),
                self._schema.Sensor.flowSummary(
                    start=int(start.timestamp()),
                    end=int(end.timestamp()),
                ).select(*get_selectors(self._schema, SensorFlowSummary)),
            ),
        )

        result = await self._query(selector)

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
        selector = self._schema.Query.controller(controllerId=controller.id).select(
            self._schema.Controller.reports.select(
                self._schema.Reports.watering(
                    **{
                        "from": int(start.timestamp()),
                        "until": int(end.timestamp()),
                    }
                ).select(*get_selectors(self._schema, WateringReportEntry)),
            ),
        )
        result = await self._query(selector)
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
        selector = self._schema.Query.controller(controllerId=controller.id).select(
            self._schema.Controller.sensors.select(
                *get_selectors(self._schema, Sensor),
                self._schema.Sensor.flowSummary(
                    start=int(start.timestamp()),
                    end=int(end.timestamp()),
                ).select(*get_selectors(self._schema, SensorFlowSummary)),
            ),
            self._schema.Controller.reports.select(
                self._schema.Reports.watering(
                    **{
                        "from": int(start.timestamp()),
                        "until": int(end.timestamp()),
                    }
                ).select(*get_selectors(self._schema, WateringReportEntry)),
            ),
        )
        result = await self._query(selector)
        summary = ControllerWaterUseSummary()

        # watering report entries
        entries = _prune_watering_report_entries(
            deserialize(
                list[WateringReportEntry], result["controller"]["reports"]["watering"]
            ),
            start,
            end,
        )

        # total active water use
        for entry in entries:
            if (
                entry.run_event is not None
                and entry.run_event.zone is not None
                and entry.run_event.reported_water_usage is not None
            ):
                active_use = entry.run_event.reported_water_usage.value
                if summary.unit == "":
                    summary.unit = entry.run_event.reported_water_usage.unit
                summary.total_active_use += active_use
                summary.active_use_by_zone_id.setdefault(entry.run_event.zone.id, 0)
                summary.active_use_by_zone_id[entry.run_event.zone.id] += active_use

        # total active and inactive water use
        for sensor in result["controller"]["sensors"]:
            if (
                "FLOW" in sensor["model"]["sensorType"]
                and "flowSummary" in sensor
                and (flow_summary := sensor["flowSummary"]) is not None
            ):
                summary.total_use += flow_summary["totalWaterVolume"]["value"]
                if summary.unit == "":
                    summary.unit = flow_summary["totalWaterVolume"]["unit"]

        # Correct for inaccuracies. The watering report and flow summaries are not always
        # updated with the same frequency.
        if summary.total_use > summary.total_active_use:
            summary.total_inactive_use = summary.total_use - summary.total_active_use
        else:
            summary.total_use = summary.total_active_use

        return summary
