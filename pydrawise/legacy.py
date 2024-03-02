""""API for interacting with Hydrawise sprinkler controllers.

This library should remain compatible with https://github.com/ptcryan/hydrawiser.
 """

from datetime import datetime, timedelta
import time

import aiohttp
import requests

from .base import HydrawiseBase
from .exceptions import NotInitializedError, UnknownError
from .schema import (
    Controller,
    ControllerHardware,
    ScheduledZoneRun,
    ScheduledZoneRuns,
    User,
    Zone,
    ZoneStatus,
    ZoneSuspension,
)

_BASE_URL = "https://api.hydrawise.com/api/v1"
_TIMEOUT = 10  # seconds


class LegacyHydrawiseAsync(HydrawiseBase):
    """Async client library for interacting with the Hydrawise v1 API.

    This should remain compatible with client.Hydrawise.
    """

    def __init__(self, user_token: str) -> None:
        self._api_key = user_token

    async def _get(self, path: str, **kwargs) -> dict:
        url = f"{_BASE_URL}/{path}"
        params = {"api_key": self._api_key}
        params.update(kwargs)
        async with aiohttp.ClientSession() as session:
            async with session.get(url, params=params, timeout=_TIMEOUT) as resp:
                resp.raise_for_status()
                return await resp.json()

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
            controllers=[_controller_from_json(c) for c in resp_json["controllers"]],
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
        controllers = [_controller_from_json(c) for c in resp_json["controllers"]]
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
        return [_zone_from_json(z) for z in resp_json["relays"]]

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


def _controller_from_json(controller_json: dict) -> Controller:
    return Controller(
        id=controller_json["controller_id"],
        name=controller_json["name"],
        hardware=ControllerHardware(
            serial_number=controller_json["serial_number"],
        ),
        last_contact_time=datetime.fromtimestamp(controller_json["last_contact"]),
        online=True,
    )


def _zone_from_json(zone_json: dict) -> Zone:
    current_run = None
    next_run = None
    suspended_until = None
    if zone_json["time"] == 1:
        current_run = ScheduledZoneRun(
            remaining_time=timedelta(seconds=zone_json["run"]),
        )
    elif zone_json["time"] == 1576800000:
        suspended_until = ZoneSuspension(end_time=datetime.max)
    else:
        now = datetime.now().replace(microsecond=0)
        start_time = now + timedelta(seconds=zone_json["time"])
        duration = timedelta(seconds=zone_json["run"])
        next_run = ScheduledZoneRun(
            start_time=start_time,
            end_time=start_time + duration,
            normal_duration=duration,
            duration=duration,
        )
    return Zone(
        id=zone_json["relay_id"],
        number=zone_json["relay"],
        name=zone_json["name"],
        scheduled_runs=ScheduledZoneRuns(
            current_run=current_run,
            next_run=next_run,
        ),
        status=ZoneStatus(
            suspended_until=suspended_until,
        ),
    )


class LegacyHydrawise:
    """Client library for interacting with Hydrawise v1 API.

    This should remain (mostly) compatible with https://github.com/ptcryan/hydrawiser
    """

    def __init__(self, user_token: str, load_on_init: bool = True) -> None:
        self._api_key = user_token
        self.controller_info = {}
        self.controller_status = {}
        if load_on_init:
            self.update_controller_info()

    @property
    def current_controller(self) -> dict:
        controllers = self.controller_info.get("controllers", [])
        if not controllers:
            return {}
        return controllers[0]

    @property
    def status(self) -> str | None:
        return self.current_controller.get("status")

    @property
    def controller_id(self) -> int | None:
        return self.current_controller.get("controller_id")

    @property
    def customer_id(self) -> int | None:
        return self.controller_info.get("customer_id")

    @property
    def num_relays(self) -> int:
        return len(self.controller_status.get("relays", []))

    @property
    def relays(self) -> list[dict]:
        relays = self.controller_status.get("relays", [])
        return sorted(relays, key=lambda r: r["relay"])

    @property
    def relays_by_id(self) -> dict[int, dict]:
        return {r["relay_id"]: r for r in self.controller_status.get("relays", [])}

    @property
    def relays_by_zone_number(self) -> dict[int, dict]:
        return {r["relay"]: r for r in self.controller_status.get("relays", [])}

    @property
    def name(self) -> str | None:
        return self.current_controller.get("name")

    @property
    def sensors(self) -> list[dict]:
        return self.controller_status.get("sensors", [])

    @property
    def running(self) -> str | None:
        return self.controller_status.get("running")

    def update_controller_info(self) -> bool:
        self.controller_info = self._get_controller_info()
        self.controller_status = self._get_controller_status()
        return True

    def _get(self, path: str, **kwargs) -> dict:
        url = f"{_BASE_URL}/{path}"
        params = {"api_key": self._api_key}
        params.update(kwargs)
        resp = requests.get(url, params=params, timeout=_TIMEOUT)

        if resp.status_code != 200:
            resp.raise_for_status()

        resp_json = resp.json()
        if "error_message" in resp_json:
            raise UnknownError(resp_json["error_message"])

        return resp_json

    def _get_controller_info(self) -> dict:
        return self._get("customerdetails.php", type="controllers")

    def _get_controller_status(self) -> dict:
        return self._get("statusschedule.php")

    def suspend_zone(self, days: int, zone: int | None = None) -> dict:
        params = {}

        if days > 0:
            params["custom"] = int(time.time() + (days * 24 * 60 * 60))
            params["period_id"] = 999
        else:
            params["period_id"] = 0

        if zone is None:
            params["action"] = "suspendall"
            return self._get("setzone.php", **params)

        if not self.relays:
            raise NotInitializedError("No zones loaded")

        params["action"] = "suspend"
        params["relay_id"] = self.relays_by_zone_number[zone]["relay_id"]
        return self._get("setzone.php", **params)

    def run_zone(self, minutes: int, zone: int | None = None) -> dict:
        params = {}

        if zone is not None:
            if not self.relays:
                raise NotInitializedError("No zones loaded")
            params["relay_id"] = self.relays_by_zone_number[zone]["relay_id"]
            params["action"] = "run" if minutes > 0 else "stop"
        else:
            params["action"] = "runall" if minutes > 0 else "stopall"

        if minutes > 0:
            params["custom"] = minutes * 60
            params["period_id"] = 999
        else:
            params["period_id"] = 0

        return self._get("setzone.php", **params)
