from datetime import datetime, timedelta
import re
from unittest import mock

from aioresponses import aioresponses
from freezegun import freeze_time
from pytest import fixture

from pydrawise import legacy
from pydrawise.schema import Controller, Zone

API_KEY = "__api_key__"


@fixture
def customer_details():
    yield {
        "controller_id": 52496,
        "customer_id": 47076,
        "current_controller": "Home Controller",
        "controllers": [
            {
                "name": "Home Controller",
                "last_contact": 1693292420,
                "serial_number": "0310b36090",
                "controller_id": 52496,
                "status": "Unknown",
            },
            {
                "name": "Other Controller",
                "last_contact": 1693292420,
                "serial_number": "1310b36091",
                "controller_id": 63507,
                "status": "Unknown",
            },
        ],
    }


@fixture
def status_schedule():
    yield {
        "expanders": [],
        "master": 0,
        "master_post_timer": 0,
        "master_timer": 0,
        "message": "",
        "nextpoll": 60,
        "options": 1,
        "relays": [
            {
                "name": "Drips - House",
                "period": 259200,
                "relay": 1,
                "relay_id": 5965394,
                "run": 1800,
                "stop": 1,
                "time": 5400,
                "timestr": "Sat",
                "type": 1,
            },
            {
                "name": "Drips - Fence",
                "period": 259200,
                "relay": 2,
                "relay_id": 5965395,
                "run": 1788,
                "stop": 1,
                "time": 1,
                "timestr": "Now",
                "type": 106,
            },
            {
                "name": "Rotary - Front",
                "period": 259200,
                "relay": 3,
                "relay_id": 5965396,
                "run": 1800,
                "stop": 1,
                "time": 1576800000,
                "timestr": "Sat",
                "type": 1,
            },
            {
                "name": "Sprays - Side L",
                "period": 259200,
                "relay": 4,
                "relay_id": 5965397,
                "run": 180,
                "stop": 1,
                "time": 335997,
                "timestr": "Sat",
                "type": 1,
            },
            {
                "name": "Rotary - Back N",
                "period": 259200,
                "relay": 5,
                "relay_id": 5965398,
                "run": 1800,
                "stop": 1,
                "time": 336177,
                "timestr": "Sat",
                "type": 1,
            },
            {
                "name": "Rotary - Back C",
                "period": 259200,
                "relay": 6,
                "relay_id": 5965399,
                "run": 1800,
                "stop": 1,
                "time": 337977,
                "timestr": "Sat",
                "type": 1,
            },
            {
                "name": "Rotary - Back F",
                "period": 259200,
                "relay": 7,
                "relay_id": 5965400,
                "run": 1200,
                "stop": 1,
                "time": 339777,
                "timestr": "Sat",
                "type": 1,
            },
            {
                "name": "Sprays - Side R",
                "period": 259200,
                "relay": 8,
                "relay_id": 5965401,
                "run": 480,
                "stop": 1,
                "time": 340977,
                "timestr": "Sat",
                "type": 1,
            },
            {
                "name": "Sprays - Drivew",
                "period": 259200,
                "relay": 9,
                "relay_id": 5965402,
                "run": 900,
                "stop": 1,
                "time": 341457,
                "timestr": "Sat",
                "type": 1,
            },
        ],
        "sensors": [
            {
                "input": 0,
                "mode": 1,
                "offtimer": 0,
                "relays": [
                    {"id": 5965394},
                    {"id": 5965395},
                    {"id": 5965396},
                    {"id": 5965397},
                    {"id": 5965398},
                    {"id": 5965399},
                    {"id": 5965400},
                    {"id": 5965401},
                    {"id": 5965402},
                ],
                "timer": 0,
                "type": 1,
            }
        ],
        "simRelays": 1,
        "stupdate": 0,
        "time": 1693303803,
    }


@fixture
def success_status():
    yield {"message": "Successful message", "message_type": "info"}


@fixture
def mock_request(customer_details, status_schedule):
    with mock.patch("requests.get") as req:
        controller_info_resp = mock.Mock(return_code=200)
        controller_info_resp.json.return_value = customer_details
        controller_status_resp = mock.Mock(return_code=200)
        controller_status_resp.json.return_value = status_schedule
        req.side_effect = [controller_info_resp, controller_status_resp]
        yield req


class TestLegacyHydrawiseAsync:
    """Test the LegacyHydrawiseAsync class."""

    async def test_get_user(
        self, customer_details: dict, status_schedule: dict
    ) -> None:
        """Test the get_user method."""
        client = legacy.LegacyHydrawiseAsync(API_KEY)
        with freeze_time("2023-01-01 01:00:00") as t:
            with aioresponses() as m:
                m.get(
                    f"https://api.hydrawise.com/api/v1/customerdetails.php?api_key={API_KEY}",
                    status=200,
                    payload=customer_details,
                )
                m.get(
                    f"https://api.hydrawise.com/api/v1/statusschedule.php?api_key={API_KEY}&controller_id=52496",
                    status=200,
                    payload=status_schedule,
                )
                m.get(
                    f"https://api.hydrawise.com/api/v1/statusschedule.php?api_key={API_KEY}&controller_id=63507",
                    status=200,
                    payload=status_schedule,
                )
                user = await client.get_user()
                assert user.customer_id == 47076
                assert [c.id for c in user.controllers] == [52496, 63507]
                want_zones = [
                    5965394,
                    5965395,
                    5965396,
                    5965397,
                    5965398,
                    5965399,
                    5965400,
                    5965401,
                    5965402,
                ]
                assert [z.id for z in user.controllers[0].zones] == want_zones
                assert [z.id for z in user.controllers[1].zones] == want_zones

    async def test_get_controllers(
        self, customer_details: dict, status_schedule: dict
    ) -> None:
        """Test the get_controllers method."""
        client = legacy.LegacyHydrawiseAsync(API_KEY)
        with freeze_time("2023-01-01 01:00:00") as t:
            with aioresponses() as m:
                m.get(
                    f"https://api.hydrawise.com/api/v1/customerdetails.php?api_key={API_KEY}&type=controllers",
                    status=200,
                    payload=customer_details,
                )
                m.get(
                    f"https://api.hydrawise.com/api/v1/statusschedule.php?api_key={API_KEY}&controller_id=52496",
                    status=200,
                    payload=status_schedule,
                )
                m.get(
                    f"https://api.hydrawise.com/api/v1/statusschedule.php?api_key={API_KEY}&controller_id=63507",
                    status=200,
                    payload=status_schedule,
                )
                controllers = await client.get_controllers()
                assert [c.id for c in controllers] == [52496, 63507]
                assert controllers[0].name == "Home Controller"
                assert controllers[1].name == "Other Controller"
                assert controllers[0].hardware.serial_number == "0310b36090"
                assert controllers[1].hardware.serial_number == "1310b36091"
                want_last_contact_time = datetime(2023, 8, 29, 7, 0, 20)
                assert controllers[0].last_contact_time == want_last_contact_time
                assert controllers[1].last_contact_time == want_last_contact_time
                want_zones = [
                    5965394,
                    5965395,
                    5965396,
                    5965397,
                    5965398,
                    5965399,
                    5965400,
                    5965401,
                    5965402,
                ]
                assert [z.id for z in controllers[0].zones] == want_zones
                assert [z.id for z in controllers[1].zones] == want_zones

    async def test_get_zones(self, status_schedule: dict) -> None:
        """Test the get_zones method."""
        client = legacy.LegacyHydrawiseAsync(API_KEY)
        with freeze_time("2023-01-01 01:00:00") as t:
            with aioresponses() as m:
                m.get(
                    f"https://api.hydrawise.com/api/v1/statusschedule.php?api_key={API_KEY}&controller_id=12345",
                    status=200,
                    payload=status_schedule,
                )
                zones = await client.get_zones(Controller(id=12345))
                assert [z.id for z in zones] == [
                    5965394,
                    5965395,
                    5965396,
                    5965397,
                    5965398,
                    5965399,
                    5965400,
                    5965401,
                    5965402,
                ]
                assert zones[0].name == "Drips - House"
                assert zones[0].number == 1
                assert zones[0].scheduled_runs.current_run is None
                next_run = zones[0].scheduled_runs.next_run
                assert next_run.start_time == datetime(2023, 1, 1, 2, 30)
                assert next_run.normal_duration == timedelta(seconds=1800)
                assert next_run.duration == timedelta(seconds=1800)

                assert zones[1].name == "Drips - Fence"
                assert zones[1].number == 2
                current_run = zones[1].scheduled_runs.current_run
                assert current_run.start_time == datetime(2023, 1, 1, 1, 0, 0)
                assert current_run.end_time == datetime(2023, 1, 1, 1, 0, 0)
                assert current_run.normal_duration == timedelta(minutes=0)
                assert current_run.duration == timedelta(minutes=0)
                assert current_run.remaining_time == timedelta(seconds=1788)
                assert zones[1].scheduled_runs.next_run is None

                assert zones[2].name == "Rotary - Front"
                assert zones[2].number == 3
                assert zones[2].scheduled_runs.current_run is None
                assert zones[2].scheduled_runs.next_run is None
                assert zones[2].status.suspended_until.end_time == datetime.max

    async def test_start_zone(self, success_status: dict) -> None:
        """Test the start_zone method."""
        client = legacy.LegacyHydrawiseAsync(API_KEY)
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
                timeout=10,
            )

    async def test_stop_zone(self, success_status: dict) -> None:
        """Test the stop_zone method."""
        client = legacy.LegacyHydrawiseAsync(API_KEY)
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
                timeout=10,
            )

    async def test_start_all_zones(self, success_status: dict) -> None:
        """Test the start_all_zones method."""
        client = legacy.LegacyHydrawiseAsync(API_KEY)
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
                timeout=10,
            )

    async def test_stop_all_zones(self, success_status: dict) -> None:
        """Test the stop_all_zones method."""
        client = legacy.LegacyHydrawiseAsync(API_KEY)
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
                timeout=10,
            )

    async def test_suspend_zone(self, success_status: dict) -> None:
        """Test the suspend_zone method."""
        client = legacy.LegacyHydrawiseAsync(API_KEY)
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
                timeout=10,
            )

    async def test_resume_zone(self, success_status: dict) -> None:
        """Test the resume_zone method."""
        client = legacy.LegacyHydrawiseAsync(API_KEY)
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
                timeout=10,
            )

    async def test_suspend_all_zones(self, success_status: dict) -> None:
        """Test the suspend_zone method."""
        client = legacy.LegacyHydrawiseAsync(API_KEY)
        with aioresponses() as m:
            m.get(
                re.compile("https://api.hydrawise.com/api/v1/setzone.php"),
                status=200,
                payload=success_status,
            )
            await client.suspend_all_zones(
                Controller(id=1111), datetime(2023, 1, 2, 1, 0)
            )
            m.assert_called_once_with(
                "https://api.hydrawise.com/api/v1/setzone.php",
                params={
                    "api_key": API_KEY,
                    "action": "suspendall",
                    "period_id": 999,
                    "custom": 1672621200,
                    "controller_id": 1111,
                },
                timeout=10,
            )

    async def test_resume_all_zones(self, success_status: dict) -> None:
        """Test the suspend_zone method."""
        client = legacy.LegacyHydrawiseAsync(API_KEY)
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
                timeout=10,
            )


class TestLegacyHydrawise:
    def test_update(self, mock_request, customer_details, status_schedule):
        client = legacy.LegacyHydrawise(API_KEY)
        mock_request.assert_has_calls(
            [
                mock.call(
                    "https://api.hydrawise.com/api/v1/customerdetails.php",
                    params={"api_key": API_KEY, "type": "controllers"},
                    timeout=10,
                ),
                mock.call(
                    "https://api.hydrawise.com/api/v1/statusschedule.php",
                    params={"api_key": API_KEY},
                    timeout=10,
                ),
            ]
        )
        assert client.controller_info == customer_details
        assert client.controller_status == status_schedule

    def test_attributes(self, mock_request, customer_details, status_schedule):
        client = legacy.LegacyHydrawise(API_KEY)
        assert client.current_controller == customer_details["controllers"][0]
        assert client.status == "Unknown"
        assert client.controller_id == 52496
        assert client.customer_id == 47076
        assert client.num_relays == 9
        assert client.relays == status_schedule["relays"]
        assert list(client.relays_by_id.keys()) == [
            5965394,
            5965395,
            5965396,
            5965397,
            5965398,
            5965399,
            5965400,
            5965401,
            5965402,
        ]
        assert list(client.relays_by_zone_number.keys()) == [1, 2, 3, 4, 5, 6, 7, 8, 9]
        assert client.name == "Home Controller"
        assert client.sensors == status_schedule["sensors"]
        assert client.running is None

    @mock.patch("requests.get")
    def test_attributes_not_initialized(self, mock_request):
        mock_request.side_effect = NotImplementedError
        client = legacy.LegacyHydrawise(API_KEY, load_on_init=False)
        assert client.controller_info == {}
        assert client.controller_status == {}
        assert client.current_controller == {}
        assert client.status is None
        assert client.controller_id is None
        assert client.customer_id is None
        assert client.num_relays == 0
        assert client.relays == []
        assert client.relays_by_id == {}
        assert client.relays_by_zone_number == {}
        assert client.name is None
        assert client.sensors == []
        assert client.running is None

    def test_suspend_zone(self, mock_request, success_status):
        client = legacy.LegacyHydrawise(API_KEY)
        mock_request.reset_mock(return_value=True, side_effect=True)

        mock_request.return_value.status_code = 200
        mock_request.return_value.json.return_value = success_status

        with freeze_time("2023-01-01 00:00:00") as t:
            assert client.suspend_zone(1, 1) == success_status
            mock_request.assert_called_once_with(
                "https://api.hydrawise.com/api/v1/setzone.php",
                params={
                    "api_key": API_KEY,
                    "action": "suspend",
                    "custom": 1672617600,
                    "period_id": 999,
                    "relay_id": 5965394,
                },
                timeout=10,
            )

    def test_suspend_zone_unsuspend(self, mock_request, success_status):
        client = legacy.LegacyHydrawise(API_KEY)
        mock_request.reset_mock(return_value=True, side_effect=True)

        mock_request.return_value.status_code = 200
        mock_request.return_value.json.return_value = success_status

        with freeze_time("2023-01-01 00:00:00") as t:
            assert client.suspend_zone(0, 1) == success_status
            mock_request.assert_called_once_with(
                "https://api.hydrawise.com/api/v1/setzone.php",
                params={
                    "api_key": API_KEY,
                    "action": "suspend",
                    "period_id": 0,
                    "relay_id": 5965394,
                },
                timeout=10,
            )

    def test_suspend_zone_all(self, mock_request, success_status):
        client = legacy.LegacyHydrawise(API_KEY)
        mock_request.reset_mock(return_value=True, side_effect=True)

        mock_request.return_value.status_code = 200
        mock_request.return_value.json.return_value = success_status

        with freeze_time("2023-01-01 00:00:00") as t:
            assert client.suspend_zone(1) == success_status
            mock_request.assert_called_once_with(
                "https://api.hydrawise.com/api/v1/setzone.php",
                params={
                    "api_key": API_KEY,
                    "action": "suspendall",
                    "custom": 1672617600,
                    "period_id": 999,
                },
                timeout=10,
            )

    def test_run_zone(self, mock_request, success_status):
        client = legacy.LegacyHydrawise(API_KEY)
        mock_request.reset_mock(return_value=True, side_effect=True)

        mock_request.return_value.status_code = 200
        mock_request.return_value.json.return_value = success_status

        with freeze_time("2023-01-01 00:00:00") as t:
            assert client.run_zone(1, 1) == success_status
            mock_request.assert_called_once_with(
                "https://api.hydrawise.com/api/v1/setzone.php",
                params={
                    "api_key": API_KEY,
                    "action": "run",
                    "custom": 60,
                    "period_id": 999,
                    "relay_id": 5965394,
                },
                timeout=10,
            )

    def test_run_zone_all(self, mock_request, success_status):
        client = legacy.LegacyHydrawise(API_KEY)
        mock_request.reset_mock(return_value=True, side_effect=True)

        mock_request.return_value.status_code = 200
        mock_request.return_value.json.return_value = success_status

        with freeze_time("2023-01-01 00:00:00") as t:
            assert client.run_zone(1) == success_status
            mock_request.assert_called_once_with(
                "https://api.hydrawise.com/api/v1/setzone.php",
                params={
                    "api_key": API_KEY,
                    "action": "runall",
                    "custom": 60,
                    "period_id": 999,
                },
                timeout=10,
            )

    def test_run_zone_stop(self, mock_request, success_status):
        client = legacy.LegacyHydrawise(API_KEY)
        mock_request.reset_mock(return_value=True, side_effect=True)

        mock_request.return_value.status_code = 200
        mock_request.return_value.json.return_value = success_status

        with freeze_time("2023-01-01 00:00:00") as t:
            assert client.run_zone(0, 1) == success_status
            mock_request.assert_called_once_with(
                "https://api.hydrawise.com/api/v1/setzone.php",
                params={
                    "api_key": API_KEY,
                    "action": "stop",
                    "period_id": 0,
                    "relay_id": 5965394,
                },
                timeout=10,
            )

    def test_run_zone_stop_all(self, mock_request, success_status):
        client = legacy.LegacyHydrawise(API_KEY)
        mock_request.reset_mock(return_value=True, side_effect=True)

        mock_request.return_value.status_code = 200
        mock_request.return_value.json.return_value = success_status

        with freeze_time("2023-01-01 00:00:00") as t:
            assert client.run_zone(0) == success_status
            mock_request.assert_called_once_with(
                "https://api.hydrawise.com/api/v1/setzone.php",
                params={
                    "api_key": API_KEY,
                    "action": "stopall",
                    "period_id": 0,
                },
                timeout=10,
            )
