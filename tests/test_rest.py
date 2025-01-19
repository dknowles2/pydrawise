import re
from datetime import datetime, timedelta
from unittest import mock

from aioresponses import aioresponses
from freezegun import freeze_time
from pytest import fixture, raises

from pydrawise import rest
from pydrawise.auth import RestAuth
from pydrawise.const import REQUEST_TIMEOUT
from pydrawise.exceptions import NotAuthorizedError
from pydrawise.schema import Controller, Zone

API_KEY = "__api_key__"


@fixture
def rest_auth():
    return RestAuth(API_KEY)


async def test_get_user_error(rest_auth: RestAuth) -> None:
    """Test that errors are handled correctly."""
    client = rest.RestClient(rest_auth)
    with freeze_time("2023-01-01 01:00:00"):
        with aioresponses() as m:
            m.get(
                f"https://api.hydrawise.com/api/v1/customerdetails.php?api_key={API_KEY}",
                status=404,
                body="API key not valid",
            )
            with raises(NotAuthorizedError):
                await client.get_user()


async def test_get_user(
    rest_auth: RestAuth, customer_details: dict, status_schedule: dict
) -> None:
    """Test the get_user method."""
    client = rest.RestClient(rest_auth)
    with freeze_time("2023-01-01 01:00:00"):
        with aioresponses() as m:
            m.get(
                f"https://api.hydrawise.com/api/v1/customerdetails.php?api_key={API_KEY}",
                status=200,
                payload=customer_details,
            )
            m.get(
                f"https://api.hydrawise.com/api/v1/statusschedule.php?api_key={API_KEY}&controller_id=9876",
                status=200,
                payload=status_schedule,
            )
            m.get(
                f"https://api.hydrawise.com/api/v1/statusschedule.php?api_key={API_KEY}&controller_id=63507",
                status=200,
                payload=status_schedule,
            )
            user = await client.get_user()
            assert user.customer_id == 2222
            assert [c.id for c in user.controllers] == [9876, 63507]
            want_zones = [0x10A, 0x10B, 0x10C, 0x10D, 0x10E, 0x10F]
            assert [z.id for z in user.controllers[0].zones] == want_zones
            assert [z.id for z in user.controllers[1].zones] == want_zones
            assert client.next_poll == timedelta(seconds=60)


async def test_get_controllers(
    rest_auth: RestAuth, customer_details: dict, status_schedule: dict
) -> None:
    """Test the get_controllers method."""
    client = rest.RestClient(rest_auth)
    with freeze_time("2023-01-01 01:00:00"):
        with aioresponses() as m:
            m.get(
                f"https://api.hydrawise.com/api/v1/customerdetails.php?api_key={API_KEY}&type=controllers",
                status=200,
                payload=customer_details,
            )
            m.get(
                f"https://api.hydrawise.com/api/v1/statusschedule.php?api_key={API_KEY}&controller_id=9876",
                status=200,
                payload=status_schedule,
            )
            m.get(
                f"https://api.hydrawise.com/api/v1/statusschedule.php?api_key={API_KEY}&controller_id=63507",
                status=200,
                payload=status_schedule,
            )
            controllers = await client.get_controllers()
            assert [c.id for c in controllers] == [9876, 63507]
            assert controllers[0].name == "Main Controller"
            assert controllers[1].name == "Other Controller"
            assert controllers[0].hardware.serial_number == "A0B1C2D3"
            assert controllers[1].hardware.serial_number == "1310b36091"
            want_last_contact_time = datetime(2023, 1, 1, 0, 0, 0)
            assert controllers[0].last_contact_time == want_last_contact_time
            assert controllers[1].last_contact_time == want_last_contact_time
            want_zones = [0x10A, 0x10B, 0x10C, 0x10D, 0x10E, 0x10F]
            assert [z.id for z in controllers[0].zones] == want_zones
            assert [z.id for z in controllers[1].zones] == want_zones


async def test_get_zones(rest_auth: RestAuth, status_schedule: dict) -> None:
    """Test the get_zones method."""
    client = rest.RestClient(rest_auth)
    with freeze_time("2023-01-01 01:00:00"):
        with aioresponses() as m:
            m.get(
                f"https://api.hydrawise.com/api/v1/statusschedule.php?api_key={API_KEY}&controller_id=12345",
                status=200,
                payload=status_schedule,
            )
            zones = await client.get_zones(Controller(id=12345))
            assert [z.id for z in zones] == [0x10A, 0x10B, 0x10C, 0x10D, 0x10E, 0x10F]
            assert zones[0].name == "Zone A"
            assert zones[0].number == 1
            assert zones[0].scheduled_runs.current_run is None
            next_run = zones[0].scheduled_runs.next_run
            assert next_run is not None
            assert next_run.start_time == datetime(2023, 1, 1, 2, 30)
            assert next_run.normal_duration == timedelta(seconds=1800)
            assert next_run.duration == timedelta(seconds=1800)

            assert zones[1].name == "Zone B"
            assert zones[1].number == 2
            current_run = zones[1].scheduled_runs.current_run
            assert current_run is not None
            assert current_run.start_time == datetime(2023, 1, 1, 1, 0, 0)
            assert current_run.end_time == datetime(2023, 1, 1, 1, 0, 0)
            assert current_run.normal_duration == timedelta(minutes=0)
            assert current_run.duration == timedelta(minutes=0)
            assert current_run.remaining_time == timedelta(seconds=1788)
            assert zones[1].scheduled_runs.next_run is None

            assert zones[2].name == "Zone C"
            assert zones[2].number == 3
            assert zones[2].scheduled_runs.current_run is None
            assert zones[2].scheduled_runs.next_run is None
            assert zones[2].status.suspended_until == datetime.max


async def test_start_zone(rest_auth: RestAuth, success_status: dict) -> None:
    """Test the start_zone method."""
    client = rest.RestClient(rest_auth)
    with aioresponses() as m:
        m.get(
            re.compile("https://api.hydrawise.com/api/v1/setzone.php"),
            status=200,
            payload=success_status,
        )
        zone = mock.create_autospec(Zone)
        zone.id = 12345
        await client.start_zone(zone)
        m.assert_called_once_with(
            "https://api.hydrawise.com/api/v1/setzone.php",
            params={
                "api_key": API_KEY,
                "action": "run",
                "relay_id": 12345,
                "period_id": 999,
            },
            timeout=REQUEST_TIMEOUT,
        )


async def test_stop_zone(rest_auth: RestAuth, success_status: dict) -> None:
    """Test the stop_zone method."""
    client = rest.RestClient(rest_auth)
    with aioresponses() as m:
        m.get(
            re.compile("https://api.hydrawise.com/api/v1/setzone.php"),
            status=200,
            payload=success_status,
        )
        zone = mock.create_autospec(Zone)
        zone.id = 12345
        await client.stop_zone(zone)
        m.assert_called_once_with(
            "https://api.hydrawise.com/api/v1/setzone.php",
            params={"api_key": API_KEY, "action": "stop", "relay_id": 12345},
            timeout=REQUEST_TIMEOUT,
        )


async def test_start_all_zones(rest_auth: RestAuth, success_status: dict) -> None:
    """Test the start_all_zones method."""
    client = rest.RestClient(rest_auth)
    with aioresponses() as m:
        m.get(
            re.compile("https://api.hydrawise.com/api/v1/setzone.php"),
            status=200,
            payload=success_status,
        )
        await client.start_all_zones(Controller(id=1111))
        m.assert_called_once_with(
            "https://api.hydrawise.com/api/v1/setzone.php",
            params={
                "api_key": API_KEY,
                "action": "runall",
                "period_id": 999,
                "controller_id": 1111,
            },
            timeout=REQUEST_TIMEOUT,
        )


async def test_stop_all_zones(rest_auth: RestAuth, success_status: dict) -> None:
    """Test the stop_all_zones method."""
    client = rest.RestClient(rest_auth)
    with aioresponses() as m:
        m.get(
            re.compile("https://api.hydrawise.com/api/v1/setzone.php"),
            status=200,
            payload=success_status,
        )
        await client.stop_all_zones(Controller(id=1111))
        m.assert_called_once_with(
            "https://api.hydrawise.com/api/v1/setzone.php",
            params={"api_key": API_KEY, "action": "stopall", "controller_id": 1111},
            timeout=REQUEST_TIMEOUT,
        )


async def test_suspend_zone(rest_auth: RestAuth, success_status: dict) -> None:
    """Test the suspend_zone method."""
    client = rest.RestClient(rest_auth)
    with aioresponses() as m:
        m.get(
            re.compile("https://api.hydrawise.com/api/v1/setzone.php"),
            status=200,
            payload=success_status,
        )
        zone = mock.create_autospec(Zone)
        zone.id = 12345
        await client.suspend_zone(zone, datetime(2023, 1, 2, 1, 0))
        m.assert_called_once_with(
            "https://api.hydrawise.com/api/v1/setzone.php",
            params={
                "api_key": API_KEY,
                "action": "suspend",
                "relay_id": 12345,
                "period_id": 999,
                "custom": 1672621200,
            },
            timeout=REQUEST_TIMEOUT,
        )


async def test_resume_zone(rest_auth: RestAuth, success_status: dict) -> None:
    """Test the resume_zone method."""
    client = rest.RestClient(rest_auth)
    with aioresponses() as m:
        m.get(
            re.compile("https://api.hydrawise.com/api/v1/setzone.php"),
            status=200,
            payload=success_status,
        )
        zone = mock.create_autospec(Zone)
        zone.id = 12345
        await client.resume_zone(zone)
        m.assert_called_once_with(
            "https://api.hydrawise.com/api/v1/setzone.php",
            params={
                "api_key": API_KEY,
                "action": "suspend",
                "relay_id": 12345,
                "period_id": 0,
            },
            timeout=REQUEST_TIMEOUT,
        )


async def test_suspend_all_zones(rest_auth: RestAuth, success_status: dict) -> None:
    """Test the suspend_zone method."""
    client = rest.RestClient(rest_auth)
    with aioresponses() as m:
        m.get(
            re.compile("https://api.hydrawise.com/api/v1/setzone.php"),
            status=200,
            payload=success_status,
        )
        await client.suspend_all_zones(Controller(id=1111), datetime(2023, 1, 2, 1, 0))
        m.assert_called_once_with(
            "https://api.hydrawise.com/api/v1/setzone.php",
            params={
                "api_key": API_KEY,
                "action": "suspendall",
                "period_id": 999,
                "custom": 1672621200,
                "controller_id": 1111,
            },
            timeout=REQUEST_TIMEOUT,
        )


async def test_resume_all_zones(rest_auth: RestAuth, success_status: dict) -> None:
    """Test the suspend_zone method."""
    client = rest.RestClient(rest_auth)
    with aioresponses() as m:
        m.get(
            re.compile("https://api.hydrawise.com/api/v1/setzone.php"),
            status=200,
            payload=success_status,
        )
        await client.resume_all_zones(Controller(id=1111))
        m.assert_called_once_with(
            "https://api.hydrawise.com/api/v1/setzone.php",
            params={
                "api_key": API_KEY,
                "action": "suspendall",
                "period_id": 0,
                "controller_id": 1111,
            },
            timeout=REQUEST_TIMEOUT,
        )
