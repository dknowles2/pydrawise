"""Base class for the Hydrawise client API."""

from abc import ABC, abstractmethod
from datetime import datetime

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


class BaseAuth(ABC):
    """Base class for Authentication objects."""

    @abstractmethod
    async def check(self) -> bool:
        """Validates that the credentials are valid.

        Returns True on success, otherwise should raise NotAuthorizedError.
        """


class HydrawiseBase(ABC):
    """Base class for Hydrawise client APIs."""

    @abstractmethod
    async def get_user(self, fetch_zones: bool = True) -> User:
        """Retrieves the currently authenticated user.

        :param fetch_zones: When True, also fetch zones.
        :rtype: User
        """

    @abstractmethod
    async def get_controllers(self) -> list[Controller]:
        """Retrieves all controllers associated with the currently authenticated user.

        :rtype: list[Controller]
        """

    @abstractmethod
    async def get_controller(self, controller_id: int) -> Controller:
        """Retrieves a single controller by its unique identifier.

        :param controller_id: Unique identifier for the controller to retrieve.
        :rtype: Controller
        """

    @abstractmethod
    async def get_zones(self, controller: Controller) -> list[Zone]:
        """Retrieves zones associated with the given controller.

        :param controller: Controller whose zones to fetch.
        :rtype: list[Zone]
        """

    @abstractmethod
    async def get_zone(self, zone_id: int) -> Zone:
        """Retrieves a zone by its unique identifier.

        :param zone_id: The zone's unique identifier.
        :rtype: Zone
        """

    @abstractmethod
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

    @abstractmethod
    async def stop_zone(self, zone: Zone) -> None:
        """Stops a zone.

        :param zone: The zone to stop.
        """

    @abstractmethod
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

    @abstractmethod
    async def stop_all_zones(self, controller: Controller) -> None:
        """Stops all zones attached to a controller.

        :param controller: The controller whose zones to stop.
        """

    @abstractmethod
    async def suspend_zone(self, zone: Zone, until: datetime) -> None:
        """Suspends a zone's schedule.

        :param zone: The zone to suspend.
        :param until: When the suspension should end.
        """

    @abstractmethod
    async def resume_zone(self, zone: Zone) -> None:
        """Resumes a zone's schedule.

        :param zone: The zone whose schedule to resume.
        """

    @abstractmethod
    async def suspend_all_zones(self, controller: Controller, until: datetime) -> None:
        """Suspends the schedule of all zones attached to a given controller.

        :param controller: The controller whose zones to suspend.
        :param until: When the suspension should end.
        """

    @abstractmethod
    async def resume_all_zones(self, controller: Controller) -> None:
        """Resumes the schedule of all zones attached to the given controller.

        :param controller: The controller whose zones to resume.
        """

    @abstractmethod
    async def delete_zone_suspension(self, suspension: ZoneSuspension) -> None:
        """Removes a specific zone suspension.

        Useful when there are multiple suspensions for a zone in effect.

        :param suspension: The suspension to delete.
        """

    @abstractmethod
    async def get_sensors(self, controller: Controller) -> list[Sensor]:
        """Retrieves sensors associated with the given controller.

        :param controller: Controller whose sensors to fetch.
        :rtype: list[Sensor]
        """

    @abstractmethod
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

    @abstractmethod
    async def get_watering_report(
        self, controller: Controller, start: datetime, end: datetime
    ) -> list[WateringReportEntry]:
        """Retrieves a watering report for the given controller and time period.

        :param controller: The controller whose watering report to generate.
        :param start: Start time.
        :param end: End time."""

    @abstractmethod
    async def get_water_use_summary(
        self, controller: Controller, start: datetime, end: datetime
    ) -> ControllerWaterUseSummary:
        """Calculate the water use for the given controller and time period.

        :param controller: The controller whose water use to report.
        :param start: Start time
        :param end: End time."""
