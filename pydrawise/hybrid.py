"""Client library for interacting with Hydrawise APIs.

This utilizes both the GraphQL and REST APIs.
"""

import logging
from asyncio import Lock
from collections.abc import Awaitable, Callable, Coroutine
from dataclasses import dataclass
from datetime import datetime, timedelta
from functools import wraps
from typing import ParamSpec, TypeVar

from .auth import HybridAuth
from .base import HydrawiseBase
from .client import Hydrawise
from .const import DEFAULT_APP_ID
from .exceptions import NotAuthorizedError, ThrottledError
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

_LOGGER = logging.getLogger("pydrawise")


@dataclass
class Throttler:
    """Tracks a token budget for calls made within a recurring time window.

    :param epoch_interval: Length of each recurring time window.
    :param last_epoch: When the current window started.
    :param tokens_per_epoch: Maximum number of tokens that may be spent per window.
    :param tokens: Number of tokens already spent in the current window.
    """

    epoch_interval: timedelta
    last_epoch: datetime = datetime.min
    tokens_per_epoch: int = 1
    tokens: int = 0

    @property
    def next_epoch(self) -> datetime:
        """When the current window ends and a new one begins."""
        return self.last_epoch + self.epoch_interval

    def check(self, tokens: int = 1) -> bool:
        """Returns whether spending the given number of tokens is currently allowed.

        :param tokens: Number of tokens the caller wants to spend.
        """
        if datetime.now() > self.next_epoch:
            return tokens <= self.tokens_per_epoch
        return (self.tokens + tokens) <= self.tokens_per_epoch

    def mark(self) -> None:
        """Records that a token was spent, starting a new window if necessary."""
        if (now := datetime.now()) > self.next_epoch:
            self.last_epoch = now
            self.tokens = 1
            return
        self.tokens += 1

    @property
    def debug_str(self) -> str:
        """A human-readable summary of the throttler's current state."""
        next_epoch_delta = self.next_epoch - datetime.now()
        return f"{self.tokens}/{self.tokens_per_epoch} tokens used; next epoch in: {next_epoch_delta}"


T = TypeVar("T")
P = ParamSpec("P")


def throttle(fn: Callable[P, Awaitable[T]]) -> Callable[P, Coroutine[None, None, T]]:
    """Decorator that throttles a HybridClient GraphQL-backed method.

    Calls are keyed by their first positional argument (a Controller's id, or
    the argument itself if it isn't a Controller). While the GraphQL throttle
    has budget, the wrapped method is called and its result cached. Once the
    throttle is exhausted, the cached result for that key is returned instead;
    if there is no cached result yet, ThrottledError is raised.

    :param fn: The bound HybridClient method to wrap.
    """
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
    """Client library that uses both the GraphQL and REST Hydrawise APIs.

    Prefers the GraphQL API, but falls back to (and caches results from) the
    REST API when GraphQL requests are throttled. This is useful for
    applications that poll frequently and want to stay within Hydrawise's
    GraphQL rate limits.

    Should be instantiated with a HybridAuth object that handles
    authentication and low-level transport for both APIs.
    """

    def __init__(
        self,
        auth: HybridAuth,
        app_id: str = DEFAULT_APP_ID,
        gql_client: Hydrawise | None = None,
        gql_throttle: Throttler | None = None,
        rest_throttle: Throttler | None = None,
    ) -> None:
        """Initializes the client.

        :param auth: Handles authentication and transport for both APIs.
        :param app_id: Unique identifier for the application accessing the Hydrawise API.
        :param gql_client: GraphQL client to use. If not specified, one will be created.
        :param gql_throttle: Throttler controlling how often the GraphQL API may be called.
        :param rest_throttle: Throttler controlling how often the REST API may be called.
        """
        if gql_client is None:
            gql_client = Hydrawise(auth, app_id)
        self._gql_client = gql_client
        self._auth = auth
        self._lock = Lock()
        self._user: User | None = None
        self._controllers: dict[int, Controller] = {}
        self._zones: dict[int, Zone] = {}
        if gql_throttle is None:
            gql_throttle = Throttler(
                epoch_interval=timedelta(minutes=30), tokens_per_epoch=5
            )
        self._gql_throttle: Throttler = gql_throttle
        if rest_throttle is None:
            rest_throttle = Throttler(
                epoch_interval=timedelta(minutes=1), tokens_per_epoch=2
            )
        self._rest_throttle: Throttler = rest_throttle

    async def get_user(self, fetch_zones: bool = True) -> User:
        """Retrieves the currently authenticated user.

        Uses the GraphQL API while it has throttle budget, refreshing zones
        from the REST API otherwise.

        :param fetch_zones: Whether to include zones in the controller response.
        :rtype: User
        """
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
            else:
                _LOGGER.debug(
                    "GQL get_user throttled: %s", self._gql_throttle.debug_str
                )

            return self._user

    async def get_controllers(
        self, fetch_zones: bool = True, fetch_sensors: bool = True
    ) -> list[Controller]:
        """Retrieves all controllers associated with the currently authenticated user.

        Uses the GraphQL API while it has throttle budget, refreshing zones
        from the REST API otherwise. Results are cached and returned from the
        cache on subsequent calls once throttled.

        :param fetch_zones: Whether to include zones in the response.
        :param fetch_sensors: Whether to include sensors in the response.
        :rtype: list[Controller]
        """
        async with self._lock:
            if not self._controllers or self._gql_throttle.check():
                controllers = await self._gql_client.get_controllers(
                    fetch_zones, fetch_sensors
                )
                self._gql_throttle.mark()
                # Make sure we have enough tokens to refresh the user info & all controllers.
                self._rest_throttle.tokens_per_epoch = len(controllers) + 1
                for controller in controllers:
                    self._controllers[controller.id] = controller
                    for zone in controller.zones:
                        self._zones[zone.id] = zone
            elif fetch_zones:
                # If we're not fetching zones, there's nothing to update.
                # The REST API doesn't return anything useful for a User.
                await self._update_zones()
            else:
                _LOGGER.debug(
                    "GQL get_controllers() throttled: %s", self._gql_throttle.debug_str
                )
        return list(self._controllers.values())

    async def get_controller(self, controller_id: int) -> Controller:
        """Retrieves a single controller by its unique identifier.

        Uses the GraphQL API while it has throttle budget; otherwise returns
        the cached controller.

        :param controller_id: Unique identifier for the controller to retrieve.
        :rtype: Controller
        """
        async with self._lock:
            if not self._controllers.get(controller_id) or self._gql_throttle.check():
                self._controllers[
                    controller_id
                ] = await self._gql_client.get_controller(controller_id)
                self._gql_throttle.mark()
            else:
                _LOGGER.debug(
                    "GQL get_controller() throttled: %s", self._gql_throttle.debug_str
                )
        return self._controllers[controller_id]

    async def get_zones(self, controller: Controller) -> list[Zone]:
        """Retrieves zones associated with the given controller.

        Uses the GraphQL API while it has throttle budget, refreshing from
        the REST API otherwise.

        :param controller: Controller whose zones to fetch.
        :rtype: list[Zone]
        """
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
                _LOGGER.debug(
                    "GQL get_zones() throttled: %s", self._gql_throttle.debug_str
                )
                await self._update_zones(controller)

        return self._controllers[controller.id].zones

    async def _update_zones(self, controller: Controller | None = None):
        if controller:
            controller_ids = [controller.id]
        else:
            controller_ids = list(self._controllers.keys())

        if not self._rest_throttle.check(len(controller_ids)):
            # We don't have enough quota to update everything, so update nothing.
            _LOGGER.debug(
                "REST _update_zones() throttled: %s", self._rest_throttle.debug_str
            )
            return

        last_err: NotAuthorizedError | None = None
        succeeded = 0
        for controller_id in controller_ids:
            try:
                json = await self._auth.get(
                    "statusschedule.php", controller_id=controller_id
                )
            except NotAuthorizedError as e:
                # The REST API key is only valid for one controller. For multi-controller
                # setups, secondary controllers will return "API key not valid". We track
                # success across iterations so that if at least one controller succeeds,
                # failures on others are treated as expected and suppressed.
                _LOGGER.debug(
                    "REST update skipped for controller %s (likely secondary): %s",
                    controller_id,
                    e,
                )
                last_err = e
                continue
            self._rest_throttle.mark()
            self._rest_throttle.epoch_interval = timedelta(seconds=json["nextpoll"])
            zones = []
            for zone_json in json["relays"]:
                if zone := self._zones.get(zone_json["relay_id"]):
                    # This zone was last populated by the GraphQL API (or by a
                    # prior REST update layered on top of one), so it's a more
                    # reliable source of truth than this REST poll alone.
                    zone.update_with_json(zone_json, trust_suspension_sentinel=False)
                else:
                    # Not an ideal case. This means we discovered a Zone from the
                    # REST API, which means we get incomplete data.
                    self._zones[zone_json["relay_id"]] = Zone.from_json(zone_json)
                zones.append(self._zones[zone_json["relay_id"]])
            self._controllers[controller_id].zones = zones
            succeeded += 1
        if succeeded == 0 and last_err is not None:
            raise last_err

    @throttle
    async def get_zone(self, zone_id: int) -> Zone:
        """Retrieves a zone by its unique identifier.

        Always uses the GraphQL API (the REST API has no way to fetch a
        single zone), throttled: once the GraphQL throttle is exhausted, the
        last result for this zone id is returned instead, or ThrottledError
        is raised if there is none yet.

        :param zone_id: The zone's unique identifier.
        :rtype: Zone
        """
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
        """Starts a zone's run cycle. Always uses the GraphQL API.

        :param zone: The zone to start.
        :param mark_run_as_scheduled: Whether to mark the zone as having run as scheduled.
        :param custom_run_duration: Duration (in seconds) to run the zone. If not
            specified (or zero), will run for its default configured time.
        """
        return await self._gql_client.start_zone(
            zone, mark_run_as_scheduled, custom_run_duration
        )

    async def stop_zone(self, zone: Zone) -> None:
        """Stops a zone. Always uses the GraphQL API.

        :param zone: The zone to stop.
        """
        return await self._gql_client.stop_zone(zone)

    async def start_all_zones(
        self,
        controller: Controller,
        mark_run_as_scheduled: bool = False,
        custom_run_duration: int = 0,
    ) -> None:
        """Starts all zones attached to a controller. Always uses the GraphQL API.

        :param controller: The controller whose zones to start.
        :param mark_run_as_scheduled: Whether to mark the zones as having run as scheduled.
        :param custom_run_duration: Duration (in seconds) to run the zones. If not
            specified (or zero), will run for each zone's default configured time.
        """
        return await self._gql_client.start_all_zones(
            controller, mark_run_as_scheduled, custom_run_duration
        )

    async def stop_all_zones(self, controller: Controller) -> None:
        """Stops all zones attached to a controller. Always uses the GraphQL API.

        :param controller: The controller whose zones to stop.
        """
        return await self._gql_client.stop_all_zones(controller)

    async def suspend_zone(self, zone: Zone, until: datetime) -> None:
        """Suspends a zone's schedule. Always uses the GraphQL API.

        :param zone: The zone to suspend.
        :param until: When the suspension should end.
        """
        return await self._gql_client.suspend_zone(zone, until)

    async def resume_zone(self, zone: Zone) -> None:
        """Resumes a zone's schedule. Always uses the GraphQL API.

        :param zone: The zone whose schedule to resume.
        """
        return await self._gql_client.resume_zone(zone)

    async def suspend_all_zones(self, controller: Controller, until: datetime) -> None:
        """Suspends the schedule of all zones attached to a given controller.

        Always uses the GraphQL API.

        :param controller: The controller whose zones to suspend.
        :param until: When the suspension should end.
        """
        return await self._gql_client.suspend_all_zones(controller, until)

    async def resume_all_zones(self, controller: Controller) -> None:
        """Resumes the schedule of all zones attached to the given controller.

        Always uses the GraphQL API.

        :param controller: The controller whose zones to resume.
        """
        return await self._gql_client.resume_all_zones(controller)

    async def delete_zone_suspension(self, suspension: ZoneSuspension) -> None:
        """Removes a specific zone suspension. Always uses the GraphQL API.

        Useful when there are multiple suspensions for a zone in effect.

        :param suspension: The suspension to delete.
        """
        return await self._gql_client.delete_zone_suspension(suspension)

    @throttle
    async def get_sensors(self, controller: Controller) -> list[Sensor]:
        """Retrieves sensors associated with the given controller.

        Always uses the GraphQL API, throttled: once the GraphQL throttle is
        exhausted, the last result for this controller is returned instead,
        or ThrottledError is raised if there is none yet.

        :param controller: Controller whose sensors to fetch.
        :rtype: list[Sensor]
        """
        return await self._gql_client.get_sensors(controller)

    async def get_water_flow_summary(
        self, controller: Controller, sensor: Sensor, start: datetime, end: datetime
    ) -> SensorFlowSummary:
        """Retrieves the water flow summary for a given sensor. Always uses the GraphQL API.

        :param controller: Controller that controls the sensor.
        :param sensor: Sensor for which a water flow summary is fetched.
        :param start:
        :param end:
        :rtype: SensorFlowSummary
        """
        return await self._gql_client.get_water_flow_summary(
            controller, sensor, start, end
        )

    async def get_watering_report(
        self, controller: Controller, start: datetime, end: datetime
    ) -> list[WateringReportEntry]:
        """Retrieves a watering report for the given controller and time period.

        Always uses the GraphQL API.

        :param controller: The controller whose watering report to generate.
        :param start: Start time.
        :param end: End time.
        """
        return await self._gql_client.get_watering_report(controller, start, end)

    async def get_water_use_summary(
        self, controller: Controller, start: datetime, end: datetime
    ) -> ControllerWaterUseSummary:
        """Calculate the water use for the given controller and time period.

        Always uses the GraphQL API.

        :param controller: The controller whose water use to report.
        :param start: Start time
        :param end: End time.
        """
        return await self._gql_client.get_water_use_summary(controller, start, end)
