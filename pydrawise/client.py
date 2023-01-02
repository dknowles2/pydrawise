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
        self._schema = get_schema()

    async def get_user(self) -> User:
        ds = DSLSchema(self._schema)
        selector = ds.Query.me.select(*get_selectors(ds, User))
        result = await self._auth.query(selector)
        user = deserialize(User, result["me"])
        user._auth = self._auth
        return user

    async def get_controllers(self) -> list[Controller]:
        ds = DSLSchema(self._schema)
        selector = ds.Query.me.select(
            ds.User.controllers.select(*get_selectors(ds, Controller)),
        )
        result = await self._auth.query(selector)
        controllers = deserialize(list[Controller], result["me"]["controllers"])
        for controller in controllers:
            controller._auth = self._auth
        return controllers

    async def get_controller(self, controller_id: int) -> Controller:
        ds = DSLSchema(self._schema)
        selector = ds.Query.controller(controllerId=controller_id).select(
            *get_selectors(ds, Controller),
        )
        result = await self._auth.query(selector)
        controller = deserialize(Controller, result["controller"])
        controller._auth = self._auth
        return controller

    async def get_zones(self, controller_id: int) -> list[Zone]:
        ds = DSLSchema(self._schema)
        selector = ds.Query.controller(controllerId=controller_id).select(
            ds.Controller.zones.select(*get_selectors(ds, Zone)),
        )
        result = await self._auth.query(selector)
        zones = deserialize(list[Zone], result["controller"]["zones"])
        for zone in zones:
            zone._auth = self._auth
        return zones

    async def get_zone(self, zone_id: int) -> Zone:
        ds = DSLSchema(self._schema)
        selector = ds.Query.zone(zoneId=zone_id).select(*get_selectors(ds, Zone))
        result = await self._auth.query(selector)
        zone = deserialize(Zone, result["zone"])
        zone._auth = self._auth
        return zone

    async def start_zone(
        self,
        zone_id: int,
        mark_run_as_scheduled: bool = False,
        custom_run_duration: int = 0,
    ):
        ds = DSLSchema(self._schema)
        kwargs = {
            "zoneId": zone_id,
            "markRunAsScheduled": mark_run_as_scheduled,
        }
        if custom_run_duration > 0:
            kwargs["customRunDuration"] = custom_run_duration

        selector = ds.Mutation.startZone.args(**kwargs).select(
            *get_selectors(ds, StatusCodeAndSummary),
        )
        await self._auth.mutation(selector)

    async def stop_zone(self, zone_id: int):
        ds = DSLSchema(self._schema)
        selector = ds.Mutation.stopZone.args(zoneId=zone_id).select(
            *get_selectors(ds, StatusCodeAndSummary),
        )
        await self._auth.mutation(selector)

    async def start_all_zones(
        self,
        controller_id: int,
        mark_run_as_scheduled: bool = False,
        custom_run_duration: int = 0,
    ):
        ds = DSLSchema(self._schema)
        kwargs = {
            "controllerId": controller_id,
            "markRunAsScheduled": mark_run_as_scheduled,
        }
        if custom_run_duration > 0:
            kwargs["customRunDuration"] = custom_run_duration

        selector = ds.Mutation.startAllZones.args(**kwargs).select(
            *get_selectors(ds, StatusCodeAndSummary),
        )
        await self._auth.mutation(selector)

    async def stop_all_zones(self, controller_id: int):
        ds = DSLSchema(self._schema)
        selector = ds.Mutation.stopAllZones.args(controllerId=controller_id).select(
            *get_selectors(ds, StatusCodeAndSummary),
        )
        await self._auth.mutation(selector)

    async def suspend_zone(self, zone_id: int, until: datetime):
        ds = DSLSchema(self._schema)
        selector = ds.Mutation.suspendZone.args(
            zoneId=zone_id,
            until=DateTime.to_json(until).value,
        ).select(
            *get_selectors(ds, StatusCodeAndSummary),
        )
        await self._auth.mutation(selector)

    async def resume_zone(self, zone_id: int):
        ds = DSLSchema(self._schema)
        selector = ds.Mutation.resumeZone.args(zoneId=zone_id).select(
            *get_selectors(ds, StatusCodeAndSummary),
        )
        await self._auth.mutation(selector)

    async def suspend_all_zones(self, controller_id: int, until: datetime):
        ds = DSLSchema(self._schema)
        selector = ds.Mutation.suspendZone.args(
            controllerId=controller_id,
            until=DateTime.to_json(until).value,
        ).select(
            *get_selectors(ds, StatusCodeAndSummary),
        )
        await self._auth.mutation(selector)

    async def resume_all_zones(self, controller_id: int):
        ds = DSLSchema(self._schema)
        selector = ds.Mutation.resumeAllZones.args(controllerId=controller_id).select(
            *get_selectors(ds, StatusCodeAndSummary),
        )
        await self._auth.mutation(selector)
