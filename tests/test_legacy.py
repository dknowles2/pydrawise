from unittest import mock

from freezegun import freeze_time
from pytest import fixture

from pydrawise import legacy

API_KEY = "__api_key__"


@fixture
def customer_details():
    yield {
        "boc_topology_desired": {"boc_gateways": []},
        "boc_topology_actual": {"boc_gateways": []},
        "controllers": [
            {
                "name": "Home Controller",
                "last_contact": 1519572810,
                "serial_number": "05fc9d5a",
                "controller_id": 52496,
                "sw_version": "2.18",
                "hardware": "hydrawise76",
                "is_boc": False,
                "address": "122 Chadwick Dr, Peachtree City, GA 30269, USA",
                "timezone": "America\/New_York",
                "device_id": 52496,
                "parent_device_id": None,
                "image": "https:\/\/app.hydrawise.com\/config\/images\/pro-hc.png",
                "description": "Pro HC 6 Station Controller",
                "customer_id": 47076,
                "latitude": 33.357814788818,
                "longitude": -84.53751373291,
                "last_contact_readable": "Feb 25, 2018 at 10:33 am",
                "status": "All good!",
                "status_icon": "ok.png",
                "online": True,
                "tags": [
                    "05fc9d5a",
                    "Home Controller",
                    "id=52496",
                    "sw=2.18",
                    "online",
                ],
            }
        ],
        "current_controller": "Home Controller",
        "is_boc": False,
        "tandc": 0,
        "controller_id": 52496,
        "customer_id": 47076,
        "session_id": "bvs3gj23sod6iolh4rq6f9sji0",
        "hardwareVersion": "hydrawise76",
        "device_id": 52496,
        "tandc_version": 2,
        "features": {
            "plan_array": [
                {
                    "id": "0",
                    "planType": "Home",
                    "planType_key": "plan.name.home",
                    "sku": None,
                    "discount": "0",
                    "cost": "0",
                    "cost_us": "0",
                    "cost_au": "0",
                    "cost_eu": "0",
                    "cost_ca": "0",
                    "cost_uk": "0",
                    "active": "1",
                    "controller_qty": "3",
                    "rainfall": "1",
                    "sms_qty": "0",
                    "scheduled_reports": "0",
                    "email_alerts": "0",
                    "define_sensor": "1",
                    "add_user": "0",
                    "contractor": "0",
                    "description": "The Home plan is free and includes -\n<ul>\n<li>Internet control from your iPhone, Android or web browser<\/li>\n<li>Hydrawise Predictive Watering based on forecast temperature and probability of rainfall - don't water when it's going to rain or is cold!<\/li>\n<li>Support for 1 Airport Based Weather Station with rainfall updated daily<\/li>\n<li>Up to 3 Hydrawise controllers per account<\/li>\n<\/ul>",
                    "sensor_pack": "0",
                    "filelimit": "25",
                    "filetypeall": "0",
                    "plan_type": "0",
                    "push_notification": "1",
                    "weather_qty": "0",
                    "weather_free_qty": "1",
                    "reporting_days": "30",
                    "weather_hourly_updates": "0",
                    "free_enthusiast_plans": "0",
                    "visible": "0",
                    "contractor_purchasable": "0",
                    "boc": "0",
                    "expiry": "1656373907",
                    "start": "1498693907",
                    "customerplan_id": "72966",
                }
            ],
            "id": None,
            "planType": "Home",
            "planType_key": "plan.name.home",
            "sku": None,
            "discount": "0",
            "cost": "0",
            "cost_us": "0",
            "cost_au": "0",
            "cost_eu": "0",
            "cost_ca": "0",
            "cost_uk": "0",
            "active": "1",
            "controller_qty": "3",
            "rainfall": "1",
            "sms_qty": "0",
            "scheduled_reports": "0",
            "email_alerts": "0",
            "define_sensor": "1",
            "add_user": "0",
            "contractor": "0",
            "description": None,
            "sensor_pack": "0",
            "filelimit": "25",
            "filetypeall": "0",
            "plan_type": "0",
            "push_notification": "1",
            "weather_qty": "0",
            "weather_free_qty": "1",
            "reporting_days": "30",
            "weather_hourly_updates": "0",
            "free_enthusiast_plans": "0",
            "visible": "0",
            "contractor_purchasable": None,
            "boc": 0,
            "expiry": None,
            "start": None,
            "customerplan_id": "72966",
            "sms_used": 0,
        },
    }


@fixture
def status_schedule():
    yield {
        "controller_id": 52496,
        "customer_id": 47076,
        "user_id": 49841,
        "nextpoll": 300,
        "sensors": [
            {
                "input": 0,
                "type": 1,
                "mode": 1,
                "timer": 0,
                "offtimer": 0,
                "name": "Rain",
                "offlevel": 1,
                "active": 1,
                "relays": [
                    {"id": 428639},
                    {"id": 428641},
                    {"id": 428642},
                    {"id": 428643},
                    {"id": 428651},
                    {"id": 428653},
                ],
            }
        ],
        "message": "",
        "obs_rain": "0.0 in",
        "obs_rain_week": "0.0 in",
        "obs_maxtemp": "",
        "obs_rain_upgrade": 0,
        "obs_rain_text": "Yesterday",
        "obs_currenttemp": "",
        "watering_time": "0  min",
        "water_saving": 100,
        "last_contact": "41 seconds ago",
        "forecast": [
            {
                "temp_hi": "66 F",
                "temp_lo": "66 F",
                "conditions": "Rain",
                "day": "Sunday",
                "pop": 90,
                "humidity": 86,
                "wind": "8 m\/h",
                "icon": "http:\/\/icons.wxug.com\/i\/c\/k\/rain.gif",
                "icon_local": "images\/wug\/rain.gif",
            },
            {
                "temp_hi": "71 F",
                "temp_lo": "71 F",
                "conditions": "Rain",
                "day": "Monday",
                "pop": 100,
                "humidity": 74,
                "wind": "7 m\/h",
                "icon": "http:\/\/icons.wxug.com\/i\/c\/k\/rain.gif",
                "icon_local": "images\/wug\/rain.gif",
            },
            {
                "temp_hi": "70 F",
                "temp_lo": "70 F",
                "conditions": "Clear",
                "day": "Tuesday",
                "pop": 10,
                "humidity": 63,
                "wind": "9 m\/h",
                "icon": "http:\/\/icons.wxug.com\/i\/c\/k\/clear.gif",
                "icon_local": "images\/wug\/clear.gif",
            },
            {
                "temp_hi": "65 F",
                "temp_lo": "60 F",
                "conditions": "Rain",
                "day": "Wednesday",
                "pop": 100,
                "humidity": 92,
                "wind": "7 m\/h",
                "icon": "http:\/\/icons.wxug.com\/i\/c\/k\/rain.gif",
                "icon_local": "images\/wug\/rain.gif",
            },
        ],
        "status": "All good!",
        "status_icon": "ok.png",
        "name": "Home Controller",
        "relays": [
            {
                "relay_id": 428639,
                "relay": 1,
                "name": "Right yard",
                "icon": "leaf.png",
                "lastwater": "Never",
                "message": "Suspended for 1 month 29 days",
                "suspended": "1524675721",
                "time": 157680000,
                "run": "",
                "type": 110,
                "id": "428639",
                "nicetime": "Not scheduled",
            },
            {
                "relay_id": 428641,
                "relay": 2,
                "name": "Far right yard",
                "icon": "leaf.png",
                "lastwater": "Never",
                "message": "Suspended for 1 month 29 days",
                "suspended": "1524675721",
                "time": 157680000,
                "run": "",
                "type": 110,
                "id": "428641",
                "nicetime": "Not scheduled",
            },
            {
                "relay_id": 428642,
                "relay": 3,
                "name": "Backyard",
                "icon": "leaf.png",
                "lastwater": "Never",
                "message": "Suspended for 1 month 29 days",
                "suspended": "1524675721",
                "time": 157680000,
                "run": "",
                "type": 110,
                "id": "428642",
                "nicetime": "Not scheduled",
            },
            {
                "relay_id": 428643,
                "relay": 4,
                "name": "Driveway",
                "icon": "leaf.png",
                "lastwater": "Never",
                "message": "Suspended for 1 month 29 days",
                "suspended": "1524675721",
                "time": 157680000,
                "run": "",
                "type": 110,
                "id": "428643",
                "nicetime": "Not scheduled",
            },
            {
                "relay_id": 428651,
                "relay": 5,
                "name": "Far left yard",
                "icon": "leaf.png",
                "lastwater": "Never",
                "message": "Suspended for 1 month 29 days",
                "suspended": "1524675721",
                "time": 157680000,
                "run": "",
                "type": 110,
                "id": "428651",
                "nicetime": "Not scheduled",
            },
            {
                "relay_id": 428653,
                "relay": 6,
                "name": "Left yard",
                "icon": "leaf.png",
                "lastwater": "Never",
                "message": "Suspended for 1 month 29 days",
                "suspended": "1524675721",
                "time": 157680000,
                "run": "",
                "type": 110,
                "id": "428653",
                "nicetime": "Not scheduled",
            },
        ],
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
    assert client.status == "All good!"
    assert client.controller_id == 52496
    assert client.customer_id == 47076
    assert client.num_relays == 6
    assert client.relays == status_schedule["relays"]
    assert list(client.relays_by_id.keys()) == [
        428639,
        428641,
        428642,
        428643,
        428651,
        428653,
    ]
    assert list(client.relays_by_zone_number.keys()) == [1, 2, 3, 4, 5, 6]
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

    with freeze_time("1970-01-01 00:00:00") as t:
        assert client.suspend_zone(1, 1) == success_status
        mock_request.assert_called_once_with(
            "https://api.hydrawise.com/api/v1/setzone.php",
            params={
                "api_key": API_KEY,
                "action": "suspend",
                "custom": 86400,
                "period_id": 999,
                "relay_id": 428639,
            },
            timeout=10,
        )


def test_suspend_zone_unsuspend(mock_request, success_status):
    client = legacy.LegacyHydrawise(API_KEY)
    mock_request.reset_mock(return_value=True, side_effect=True)

    mock_request.return_value.status_code = 200
    mock_request.return_value.json.return_value = success_status

    with freeze_time("1970-01-01 00:00:00") as t:
        assert client.suspend_zone(0, 1) == success_status
        mock_request.assert_called_once_with(
            "https://api.hydrawise.com/api/v1/setzone.php",
            params={
                "api_key": API_KEY,
                "action": "suspend",
                "period_id": 0,
                "relay_id": 428639,
            },
            timeout=10,
        )


def test_suspend_zone_all(mock_request, success_status):
    client = legacy.LegacyHydrawise(API_KEY)
    mock_request.reset_mock(return_value=True, side_effect=True)

    mock_request.return_value.status_code = 200
    mock_request.return_value.json.return_value = success_status

    with freeze_time("1970-01-01 00:00:00") as t:
        assert client.suspend_zone(1) == success_status
        mock_request.assert_called_once_with(
            "https://api.hydrawise.com/api/v1/setzone.php",
            params={
                "api_key": API_KEY,
                "action": "suspendall",
                "custom": 86400,
                "period_id": 999,
            },
            timeout=10,
        )


def test_run_zone(mock_request, success_status):
    client = legacy.LegacyHydrawise(API_KEY)
    mock_request.reset_mock(return_value=True, side_effect=True)

    mock_request.return_value.status_code = 200
    mock_request.return_value.json.return_value = success_status

    with freeze_time("1970-01-01 00:00:00") as t:
        assert client.run_zone(1, 1) == success_status
        mock_request.assert_called_once_with(
            "https://api.hydrawise.com/api/v1/setzone.php",
            params={
                "api_key": API_KEY,
                "action": "run",
                "custom": 60,
                "period_id": 999,
                "relay_id": 428639,
            },
            timeout=10,
        )


def test_run_zone_all(mock_request, success_status):
    client = legacy.LegacyHydrawise(API_KEY)
    mock_request.reset_mock(return_value=True, side_effect=True)

    mock_request.return_value.status_code = 200
    mock_request.return_value.json.return_value = success_status

    with freeze_time("1970-01-01 00:00:00") as t:
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

    with freeze_time("1970-01-01 00:00:00") as t:
        assert client.run_zone(0, 1) == success_status
        mock_request.assert_called_once_with(
            "https://api.hydrawise.com/api/v1/setzone.php",
            params={
                "api_key": API_KEY,
                "action": "stop",
                "period_id": 0,
                "relay_id": 428639,
            },
            timeout=10,
        )


def test_run_zone_stop_all(mock_request, success_status):
    client = legacy.LegacyHydrawise(API_KEY)
    mock_request.reset_mock(return_value=True, side_effect=True)

    mock_request.return_value.status_code = 200
    mock_request.return_value.json.return_value = success_status

    with freeze_time("1970-01-01 00:00:00") as t:
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
