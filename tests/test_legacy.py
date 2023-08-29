from unittest import mock

from freezegun import freeze_time
from pytest import fixture

from pydrawise import legacy

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
            }
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
                "time": 330597,
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
                "time": 334197,
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


def test_update(mock_request, customer_details, status_schedule):
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


def test_attributes(mock_request, customer_details, status_schedule):
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
def test_attributes_not_initialized(mock_request):
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


def test_suspend_zone(mock_request, success_status):
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


def test_suspend_zone_unsuspend(mock_request, success_status):
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


def test_suspend_zone_all(mock_request, success_status):
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


def test_run_zone(mock_request, success_status):
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


def test_run_zone_all(mock_request, success_status):
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


def test_run_zone_stop(mock_request, success_status):
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


def test_run_zone_stop_all(mock_request, success_status):
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
