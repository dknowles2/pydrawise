"""Asynchronous client library for interacting with Hydrawise's REST API."""

from datetime import datetime, timedelta

import aiohttp

from pydrawise.schema import (
    ControllerWaterUseSummary,
    Sensor,
    SensorFlowSummary,
    WateringReportEntry,
)

from .auth import RestAuth
from .base import HydrawiseBase
from .schema import Controller, User, Zone, ZoneSuspension

_TIMEOUT = aiohttp.ClientTimeout(total=10)


class RestClient(HydrawiseBase):
    """Async client library for interacting with the Hydrawise v1 REST API.

    This should remain compatible with client.Hydrawise.
    """

    def __init__(self, auth: RestAuth) -> None:
        self._auth = auth
        self.next_poll = timedelta(0)

    async def _get(self, path: str, **kwargs) -> dict:
        json = await self._auth.get(path, **kwargs)
        if "nextpoll" in json:
            self.next_poll = timedelta(seconds=json["nextpoll"])
        return json

    async def get_user(self, fetch_zones: bool = True) -> User:
        """Retrieves the currently authenticated user.

        :param fetch_zones: When True, also fetch zones.
        :rtype: User
        """
        resp_json = await self._get("customerdetails.php")
        user = User(
            id=0,
            customer_id=resp_json["customer_id"],
            name="",
            email="",
            controllers=[Controller.from_json(c) for c in resp_json["controllers"]],
        )
        if fetch_zones:
            for controller in user.controllers:
                controller.zones = await self.get_zones(controller)
        return user

    async def get_controllers(self) -> list[Controller]:
        """Retrieves all controllers associated with the currently authenticated user.

        :rtype: list[Controller]
        """
        resp_json = await self._get("customerdetails.php", type="controllers")
        controllers = [Controller.from_json(c) for c in resp_json["controllers"]]
        for controller in controllers:
            controller.zones = await self.get_zones(controller)
        return controllers

    async def get_controller(self, controller_id: int) -> Controller:
        """Retrieves a single controller by its unique identifier.

        :param controller_id: Unique identifier for the controller to retrieve.
        :rtype: Controller
        """
        _ = controller_id  # unused
        raise NotImplementedError

    async def get_zones(self, controller: Controller) -> list[Zone]:
        """Retrieves zones associated with the given controller.

        :param controller: Controller whose zones to fetch.
        :rtype: list[Zone]
        """
        resp_json = await self._get("statusschedule.php", controller_id=controller.id)
        return [Zone.from_json(z) for z in resp_json["relays"]]

    async def get_zone(self, zone_id: int) -> Zone:
        """Retrieves a zone by its unique identifier.

        :param zone_id: The zone's unique identifier.
        :rtype: Zone
        """
        _ = zone_id  # unused
        raise NotImplementedError

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
        _ = mark_run_as_scheduled  # unused.
        params = {
            "action": "run",
            "relay_id": zone.id,
            "period_id": 999,
        }
        if custom_run_duration > 0:
            params["custom"] = custom_run_duration
        await self._get("setzone.php", **params)

    async def stop_zone(self, zone: Zone) -> None:
        """Stops a zone.

        :param zone: The zone to stop.
        """
        await self._get("setzone.php", action="stop", relay_id=zone.id)

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
        _ = mark_run_as_scheduled  # unused
        params = {
            "action": "runall",
            "controller_id": controller.id,
            "period_id": 999,
        }
        if custom_run_duration > 0:
            params["custom"] = custom_run_duration
        await self._get("setzone.php", **params)

    async def stop_all_zones(self, controller: Controller) -> None:
        """Stops all zones attached to a controller.

        :param controller: The controller whose zones to stop.
        """
        await self._get("setzone.php", action="stopall", controller_id=controller.id)

    async def suspend_zone(self, zone: Zone, until: datetime) -> None:
        """Suspends a zone's schedule.

        :param zone: The zone to suspend.
        :param until: When the suspension should end.
        """
        await self._get(
            "setzone.php",
            action="suspend",
            relay_id=zone.id,
            period_id=999,
            custom=int(until.timestamp()),
        )

    async def resume_zone(self, zone: Zone) -> None:
        """Resumes a zone's schedule.

        :param zone: The zone whose schedule to resume.
        """
        await self._get("setzone.php", action="suspend", relay_id=zone.id, period_id=0)

    async def suspend_all_zones(self, controller: Controller, until: datetime) -> None:
        """Suspends the schedule of all zones attached to a given controller.

        :param controller: The controller whose zones to suspend.
        :param until: When the suspension should end.
        """
        await self._get(
            "setzone.php",
            action="suspendall",
            controller_id=controller.id,
            period_id=999,
            custom=int(until.timestamp()),
        )

    async def resume_all_zones(self, controller: Controller) -> None:
        """Resumes the schedule of all zones attached to the given controller.

        :param controller: The controller whose zones to resume.
        """
        await self._get(
            "setzone.php", action="suspendall", period_id=0, controller_id=controller.id
        )

    async def delete_zone_suspension(self, suspension: ZoneSuspension) -> None:
        """Removes a specific zone suspension.

        Useful when there are multiple suspensions for a zone in effect.

        :param suspension: The suspension to delete.
        """
        _ = suspension  # unused
        raise NotImplementedError

    async def get_sensors(self, controller: Controller) -> list[Sensor]:
        raise NotImplementedError

    async def get_water_flow_summary(
        self, controller: Controller, sensor: Sensor, start: datetime, end: datetime
    ) -> SensorFlowSummary:
        raise NotImplementedError

    async def get_watering_report(
        self, controller: Controller, start: datetime, end: datetime
    ) -> list[WateringReportEntry]:
        raise NotImplementedError

    async def get_water_use_summary(
        self, controller: Controller, start: datetime, end: datetime
    ) -> ControllerWaterUseSummary:
        raise NotImplementedError
