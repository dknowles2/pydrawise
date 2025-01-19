"""Client library for interacting with Hydrawise APIs.

This utilizes both the GraphQL and REST APIs.
"""

from asyncio import Lock
from dataclasses import dataclass
from datetime import datetime, timedelta
from functools import wraps
from typing import Awaitable, Callable, Coroutine, ParamSpec, TypeVar

from .auth import HybridAuth
from .base import HydrawiseBase
from .client import Hydrawise
from .const import DEFAULT_APP_ID
from .exceptions import ThrottledError
from .schema import (
    Controller,
    ControllerWaterUseSummary,
    Sensor,
    SensorFlowSummary,
    User,
    WateringReportEntry,
    Zone,
    ZoneSuspension,
)


@dataclass
class Throttler:
    epoch_interval: timedelta
    last_epoch: datetime = datetime.min
    tokens_per_epoch: int = 1
    tokens: int = 0

    def check(self, tokens: int = 1) -> bool:
        if datetime.now() > self.last_epoch + self.epoch_interval:
            return tokens <= self.tokens_per_epoch
        return (self.tokens + tokens) <= self.tokens_per_epoch

    def mark(self) -> None:
        if (now := datetime.now()) > self.last_epoch + self.epoch_interval:
            self.last_epoch = now
            self.tokens = 1
            return
        self.tokens += 1


T = TypeVar("T")
P = ParamSpec("P")


def throttle(fn: Callable[P, Awaitable[T]]) -> Callable[P, Coroutine[None, None, T]]:
    cache: dict[str, T] = {}

    @wraps(fn)
    async def wrapper(*args: P.args, **kwargs: P.kwargs) -> T:
        assert len(args) > 1
        assert isinstance(args[0], HybridClient)
        self: HybridClient = args[0]
        k = str(args[1].id if isinstance(args[1], Controller) else args[1])
        async with self._lock:
            if self._gql_throttle.check():
                v = await fn(*args, **kwargs)
                self._gql_throttle.mark()
                cache[k] = v
            elif k not in cache:
                raise ThrottledError
            return cache[k]

    return wrapper


class HybridClient(HydrawiseBase):
    def __init__(
        self,
        auth: HybridAuth,
        app_id: str = DEFAULT_APP_ID,
        gql_client: Hydrawise | None = None,
    ) -> None:
        if gql_client is None:
            gql_client = Hydrawise(auth, app_id)
        self._gql_client = gql_client
        self._auth = auth
        self._lock = Lock()
        self._user: User | None = None
        self._controllers: dict[int, Controller] = {}
        self._zones: dict[int, Zone] = {}
        self._gql_throttle = Throttler(
            epoch_interval=timedelta(minutes=30), tokens_per_epoch=2
        )
        self._rest_throttle = Throttler(
            epoch_interval=timedelta(minutes=1), tokens_per_epoch=2
        )

    async def get_user(self, fetch_zones: bool = True) -> User:
        async with self._lock:
            if self._user is None or self._gql_throttle.check():
                self._user = await self._gql_client.get_user(fetch_zones=fetch_zones)
                self._gql_throttle.mark()
                for controller in self._user.controllers:
                    self._controllers[controller.id] = controller
                    for zone in controller.zones:
                        self._zones[zone.id] = zone
            elif fetch_zones:
                # If we're not fetching zones, there's nothing to update.
                # The REST API doesn't return anything useful for a User.
                await self._update_zones()

            return self._user

    async def get_controllers(
        self, fetch_zones: bool = True, fetch_sensors: bool = True
    ) -> list[Controller]:
        async with self._lock:
            if not self._controllers or self._gql_throttle.check():
                controllers = await self._gql_client.get_controllers(
                    fetch_zones, fetch_sensors
                )
                self._gql_throttle.mark()
                for controller in controllers:
                    self._controllers[controller.id] = controller
                    for zone in controller.zones:
                        self._zones[zone.id] = zone
            elif fetch_zones:
                # If we're not fetching zones, there's nothing to update.
                # The REST API doesn't return anything useful for a User.
                await self._update_zones()
        return list(self._controllers.values())

    async def get_controller(self, controller_id: int) -> Controller:
        async with self._lock:
            if not self._controllers.get(controller_id) or self._gql_throttle.check():
                self._controllers[
                    controller_id
                ] = await self._gql_client.get_controller(controller_id)
                self._gql_throttle.mark()
        return self._controllers[controller_id]

    async def get_zones(self, controller: Controller) -> list[Zone]:
        async with self._lock:
            if not self._controllers.get(controller.id) or self._gql_throttle.check():
                zones = await self._gql_client.get_zones(controller)
                self._gql_throttle.mark()
                if controller.id not in self._controllers:
                    self._controllers[controller.id] = controller
                self._controllers[controller.id].zones = zones
                for zone in zones:
                    self._zones[zone.id] = zone
            else:
                await self._update_zones(controller)

        return self._controllers[controller.id].zones

    async def _update_zones(self, controller: Controller | None = None):
        if controller:
            controller_ids = [controller.id]
        else:
            controller_ids = list(self._controllers.keys())

        if not self._rest_throttle.check(len(controller_ids)):
            # We don't have enough quota to update everything, so update nothing.
            return

        for controller_id in controller_ids:
            json = await self._auth.get(
                "statusschedule.php", controller_id=controller_id
            )
            self._rest_throttle.mark()
            self._rest_throttle.epoch_interval = timedelta(seconds=json["nextpoll"])
            for zone_json in json["relays"]:
                if zone := self._zones.get(zone_json["relay_id"]):
                    zone.update_with_json(zone_json)
                else:
                    # Not an ideal case. This means we discovered a Zone from the
                    # REST API, which means we get incomplete data.
                    self._zones[zone_json["relay_id"]] = Zone.from_json(zone_json)

    @throttle
    async def get_zone(self, zone_id: int) -> Zone:
        # The REST API doesn't allow us to fetch a single zone, so we'll just
        # query the GraphQL API instead.
        #
        # Since we don't know what controller a particular zone is associated
        # with without inspecting each controller, we don't bother with updating
        # the _zones cache.
        #
        # This method isn't used by HomeAssistant, so the inconsistency is
        # probably fine.
        return await self._gql_client.get_zone(zone_id)

    async def start_zone(
        self,
        zone: Zone,
        mark_run_as_scheduled: bool = False,
        custom_run_duration: int = 0,
    ) -> None:
        return await self._gql_client.start_zone(
            zone, mark_run_as_scheduled, custom_run_duration
        )

    async def stop_zone(self, zone: Zone) -> None:
        return await self._gql_client.stop_zone(zone)

    async def start_all_zones(
        self,
        controller: Controller,
        mark_run_as_scheduled: bool = False,
        custom_run_duration: int = 0,
    ) -> None:
        return await self._gql_client.start_all_zones(
            controller, mark_run_as_scheduled, custom_run_duration
        )

    async def stop_all_zones(self, controller: Controller) -> None:
        return await self._gql_client.stop_all_zones(controller)

    async def suspend_zone(self, zone: Zone, until: datetime) -> None:
        return await self._gql_client.suspend_zone(zone, until)

    async def resume_zone(self, zone: Zone) -> None:
        return await self._gql_client.resume_zone(zone)

    async def suspend_all_zones(self, controller: Controller, until: datetime) -> None:
        return await self._gql_client.suspend_all_zones(controller, until)

    async def resume_all_zones(self, controller: Controller) -> None:
        return await self._gql_client.resume_all_zones(controller)

    async def delete_zone_suspension(self, suspension: ZoneSuspension) -> None:
        return await self._gql_client.delete_zone_suspension(suspension)

    @throttle
    async def get_sensors(self, controller: Controller) -> list[Sensor]:
        return await self._gql_client.get_sensors(controller)

    async def get_water_flow_summary(
        self, controller: Controller, sensor: Sensor, start: datetime, end: datetime
    ) -> SensorFlowSummary:
        return await self._gql_client.get_water_flow_summary(
            controller, sensor, start, end
        )

    async def get_watering_report(
        self, controller: Controller, start: datetime, end: datetime
    ) -> list[WateringReportEntry]:
        return await self._gql_client.get_watering_report(controller, start, end)

    async def get_water_use_summary(
        self, controller: Controller, start: datetime, end: datetime
    ) -> ControllerWaterUseSummary:
        return await self._gql_client.get_water_use_summary(controller, start, end)
