"""Client library for interacting with Hydrawise's cloud API."""

from datetime import datetime

from gql.dsl import DSLSchema

from .auth import Auth
from .schema import (
    Controller,
    DateTime,
    StatusCodeAndSummary,
    User,
    Zone,
    deserialize,
    get_schema,
    get_selectors,
)


class Hydrawise:
    def __init__(self, auth: Auth) -> None:
        self._auth = auth
        self._schema = DSLSchema(get_schema())

    async def get_user(self) -> User:
        selector = self._schema.Query.me.select(*get_selectors(self._schema, User))
        result = await self._auth.query(selector)
        return deserialize(User, result["me"])

    async def get_controllers(self) -> list[Controller]:
        selector = self._schema.Query.me.select(
            self._schema.User.controllers.select(
                *get_selectors(self._schema, Controller)
            ),
        )
        result = await self._auth.query(selector)
        return deserialize(list[Controller], result["me"]["controllers"])

    async def get_controller(self, controller_id: int) -> Controller:
        selector = self._schema.Query.controller(controllerId=controller_id).select(
            *get_selectors(self._schema, Controller),
        )
        result = await self._auth.query(selector)
        return deserialize(Controller, result["controller"])

    async def get_zones(self, controller: Controller) -> list[Zone]:
        selector = self._schema.Query.controller(controllerId=controller.id).select(
            self._schema.Controller.zones.select(*get_selectors(self._schema, Zone)),
        )
        result = await self._auth.query(selector)
        return deserialize(list[Zone], result["controller"]["zones"])

    async def get_zone(self, zone_id: int) -> Zone:
        selector = self._schema.Query.zone(zoneId=zone_id).select(
            *get_selectors(self._schema, Zone)
        )
        result = await self._auth.query(selector)
        return deserialize(Zone, result["zone"])

    async def start_zone(
        self,
        zone: Zone,
        mark_run_as_scheduled: bool = False,
        custom_run_duration: int = 0,
    ):
        kwargs = {
            "zoneId": zone.id,
            "markRunAsScheduled": mark_run_as_scheduled,
        }
        if custom_run_duration > 0:
            kwargs["customRunDuration"] = custom_run_duration

        selector = self._schema.Mutation.startZone.args(**kwargs).select(
            *get_selectors(self._schema, StatusCodeAndSummary),
        )
        await self._auth.mutation(selector)

    async def stop_zone(self, zone: Zone):
        selector = self._schema.Mutation.stopZone.args(zoneId=zone.id).select(
            *get_selectors(self._schema, StatusCodeAndSummary),
        )
        await self._auth.mutation(selector)

    async def start_all_zones(
        self,
        controller: Controller,
        mark_run_as_scheduled: bool = False,
        custom_run_duration: int = 0,
    ):
        kwargs = {
            "controllerId": controller.id,
            "markRunAsScheduled": mark_run_as_scheduled,
        }
        if custom_run_duration > 0:
            kwargs["customRunDuration"] = custom_run_duration

        selector = self._schema.Mutation.startAllZones.args(**kwargs).select(
            *get_selectors(self._schema, StatusCodeAndSummary),
        )
        await self._auth.mutation(selector)

    async def stop_all_zones(self, controller: Controller):
        selector = self._schema.Mutation.stopAllZones.args(
            controllerId=controller.id
        ).select(
            *get_selectors(self._schema, StatusCodeAndSummary),
        )
        await self._auth.mutation(selector)

    async def suspend_zone(self, zone: Zone, until: datetime):
        selector = self._schema.Mutation.suspendZone.args(
            zoneId=zone.id,
            until=DateTime.to_json(until).value,
        ).select(
            *get_selectors(self._schema, StatusCodeAndSummary),
        )
        await self._auth.mutation(selector)

    async def resume_zone(self, zone: Zone):
        selector = self._schema.Mutation.resumeZone.args(zoneId=zone.id).select(
            *get_selectors(self._schema, StatusCodeAndSummary),
        )
        await self._auth.mutation(selector)

    async def suspend_all_zones(self, controller: Controller, until: datetime):
        selector = self._schema.Mutation.suspendZone.args(
            controllerId=controller.id,
            until=DateTime.to_json(until).value,
        ).select(
            *get_selectors(self._schema, StatusCodeAndSummary),
        )
        await self._auth.mutation(selector)

    async def resume_all_zones(self, controller: Controller):
        selector = self._schema.Mutation.resumeAllZones.args(
            controllerId=controller.id
        ).select(
            *get_selectors(self._schema, StatusCodeAndSummary),
        )
        await self._auth.mutation(selector)
