"""Client library for interacting with Hydrawise's REST API.

This library should remain compatible with https://github.com/ptcryan/hydrawiser.
"""

import time
from typing import Any

import requests

from .auth import RestAuth
from .const import REST_URL
from .exceptions import NotInitializedError, UnknownError
from .rest import RestClient

_TIMEOUT = 10  # seconds


class LegacyHydrawiseAsync(RestClient):
    """Async client library for interacting with the Hydrawise v1 API.

    This is for compatibility with previous pydrawise versions. Please
    prefer to use rest.RestClient instead.
    """

    def __init__(self, user_token: str) -> None:
        """Initializer.

        :param user_token: The API key to use for authenticating with the Hydrawise service.
        """
        super().__init__(RestAuth(user_token))


class LegacyHydrawise:
    """Client library for interacting with Hydrawise v1 API.

    This should remain (mostly) compatible with https://github.com/ptcryan/hydrawiser
    """

    def __init__(self, user_token: str, load_on_init: bool = True) -> None:
        """Initializer.

        :param user_token: The API key to use for authenticating with the Hydrawise service.
        :param load_on_init: Whether to synchronously fetch controller info and
            status as part of initialization.
        """
        self._api_key = user_token
        self.controller_info: dict[str, Any] = {}
        self.controller_status: dict[str, Any] = {}
        if load_on_init:
            self.update_controller_info()

    @property
    def current_controller(self) -> dict:
        """The raw JSON for the account's first (or only) controller.

        Empty if no controller info has been loaded yet.
        """
        controllers = self.controller_info.get("controllers", [])
        if not controllers:
            return {}
        return controllers[0]

    @property
    def status(self) -> str | None:
        """Human-readable status string for the current controller (e.g. "All good!")."""
        return self.current_controller.get("status")

    @property
    def controller_id(self) -> int | None:
        """Unique identifier of the current controller."""
        return self.current_controller.get("controller_id")

    @property
    def customer_id(self) -> int | None:
        """Unique identifier of the authenticated customer account."""
        return self.controller_info.get("customer_id")

    @property
    def num_relays(self) -> int:
        """Number of zones (relays) attached to the current controller."""
        return len(self.controller_status.get("relays", []))

    @property
    def relays(self) -> list[dict]:
        """Raw JSON for each zone (relay) attached to the current controller.

        Sorted by zone number.
        """
        relays = self.controller_status.get("relays", [])
        return sorted(relays, key=lambda r: r["relay"])

    @property
    def relays_by_id(self) -> dict[int, dict]:
        """Raw zone JSON keyed by each zone's unique relay id."""
        return {r["relay_id"]: r for r in self.controller_status.get("relays", [])}

    @property
    def relays_by_zone_number(self) -> dict[int, dict]:
        """Raw zone JSON keyed by zone (relay) number."""
        return {r["relay"]: r for r in self.controller_status.get("relays", [])}

    @property
    def name(self) -> str | None:
        """Name of the current controller."""
        return self.current_controller.get("name")

    @property
    def sensors(self) -> list[dict]:
        """Raw JSON for the sensors attached to the current controller."""
        return self.controller_status.get("sensors", [])

    @property
    def running(self) -> str | None:
        """Raw JSON describing the zone that is currently running, if any."""
        return self.controller_status.get("running")

    def update_controller_info(self) -> bool:
        """Refreshes controller info and status from the Hydrawise service.

        :rtype: bool
        """
        self.controller_info = self._get_controller_info()
        self.controller_status = self._get_controller_status()
        return True

    def _get(self, path: str, **kwargs) -> dict:
        url = f"{REST_URL}/{path}"
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
        """Suspends a zone's (or all zones') schedule for a number of days.

        :param days: Number of days to suspend for, starting now. If not
            positive, any existing suspension is cleared instead.
        :param zone: Zone (relay) number to suspend. If not specified, all
            zones on the current controller are suspended.
        :rtype: dict
        """
        params: dict[str, Any] = {}

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
        """Starts or stops a zone's (or all zones') run cycle.

        :param minutes: Number of minutes to run for. If not positive, the
            zone(s) are stopped instead.
        :param zone: Zone (relay) number to run or stop. If not specified,
            all zones on the current controller are run or stopped.
        :rtype: dict
        """
        params: dict[str, Any] = {}

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
