from unittest import mock

from freezegun import freeze_time

from pydrawise import legacy

API_KEY = "__api_key__"


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
    assert client.controller_id == 9876
    assert client.customer_id == 2222
    assert client.num_relays == 6
    assert client.relays == status_schedule["relays"]
    assert list(client.relays_by_id.keys()) == [
        0x10A,
        0x10B,
        0x10C,
        0x10D,
        0x10E,
        0x10F,
    ]
    assert list(client.relays_by_zone_number.keys()) == [1, 2, 3, 4, 5, 6]
    assert client.name == "Main Controller"
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

    with freeze_time("2023-01-01 00:00:00"):
        assert client.suspend_zone(1, 1) == success_status
        mock_request.assert_called_once_with(
            "https://api.hydrawise.com/api/v1/setzone.php",
            params={
                "api_key": API_KEY,
                "action": "suspend",
                "custom": 1672617600,
                "period_id": 999,
                "relay_id": 0x10A,
            },
            timeout=10,
        )


def test_suspend_zone_unsuspend(mock_request, success_status):
    client = legacy.LegacyHydrawise(API_KEY)
    mock_request.reset_mock(return_value=True, side_effect=True)

    mock_request.return_value.status_code = 200
    mock_request.return_value.json.return_value = success_status

    with freeze_time("2023-01-01 00:00:00"):
        assert client.suspend_zone(0, 1) == success_status
        mock_request.assert_called_once_with(
            "https://api.hydrawise.com/api/v1/setzone.php",
            params={
                "api_key": API_KEY,
                "action": "suspend",
                "period_id": 0,
                "relay_id": 0x10A,
            },
            timeout=10,
        )


def test_suspend_zone_all(mock_request, success_status):
    client = legacy.LegacyHydrawise(API_KEY)
    mock_request.reset_mock(return_value=True, side_effect=True)

    mock_request.return_value.status_code = 200
    mock_request.return_value.json.return_value = success_status

    with freeze_time("2023-01-01 00:00:00"):
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

    with freeze_time("2023-01-01 00:00:00"):
        assert client.run_zone(1, 1) == success_status
        mock_request.assert_called_once_with(
            "https://api.hydrawise.com/api/v1/setzone.php",
            params={
                "api_key": API_KEY,
                "action": "run",
                "custom": 60,
                "period_id": 999,
                "relay_id": 0x10A,
            },
            timeout=10,
        )


def test_run_zone_all(mock_request, success_status):
    client = legacy.LegacyHydrawise(API_KEY)
    mock_request.reset_mock(return_value=True, side_effect=True)

    mock_request.return_value.status_code = 200
    mock_request.return_value.json.return_value = success_status

    with freeze_time("2023-01-01 00:00:00"):
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

    with freeze_time("2023-01-01 00:00:00"):
        assert client.run_zone(0, 1) == success_status
        mock_request.assert_called_once_with(
            "https://api.hydrawise.com/api/v1/setzone.php",
            params={
                "api_key": API_KEY,
                "action": "stop",
                "period_id": 0,
                "relay_id": 0x10A,
            },
            timeout=10,
        )


def test_run_zone_stop_all(mock_request, success_status):
    client = legacy.LegacyHydrawise(API_KEY)
    mock_request.reset_mock(return_value=True, side_effect=True)

    mock_request.return_value.status_code = 200
    mock_request.return_value.json.return_value = success_status

    with freeze_time("2023-01-01 00:00:00"):
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
