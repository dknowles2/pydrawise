from datetime import datetime, timedelta
from unittest.mock import create_autospec, patch

from gql import Client
from gql.client import AsyncClientSession
from graphql import print_ast
import pytest
from pytest import fixture

from pydrawise.auth import Auth
from pydrawise.client import Hydrawise
from pydrawise.schema import Controller, Sensor, Zone, ZoneSuspension
from pydrawise.schema_utils import deserialize


@fixture
def mock_auth():
    mock_auth = create_autospec(Auth, spec_set=True, instance=True)
    mock_auth.token.return_value = "__token__"
    yield mock_auth


@fixture
def mock_session():
    yield create_autospec(AsyncClientSession, spec_set=True, instance=True)


@fixture
def mock_client(mock_session):
    client = create_autospec(Client, spec_set=True, instance=True)
    client.__aenter__.return_value = mock_session
    yield client


@fixture
def api(mock_auth, mock_client):
    api = Hydrawise(mock_auth)
    with patch.object(api, "_client", return_value=mock_client):
        yield api


@fixture
def rain_sensor_json():
    yield {
        "id": 337844,
        "name": "Rain sensor ",
        "model": {
            "id": 3318,
            "name": "Rain Sensor (normally closed wire)",
            "active": True,
            "offLevel": 1,
            "offTimer": 0,
            "delay": 0,
            "divisor": 0,
            "flowRate": 0,
            "sensorType": "LEVEL_CLOSED",
        },
        "status": {
            "waterFlow": None,
            "active": False,
        },
    }


@fixture
def flow_sensor_json():
    yield {
        "id": 337845,
        "name": "Flow meter",
        "model": {
            "id": 3324,
            "name": "1, 1½ or 2 inch NPT Flow Meter",
            "active": True,
            "offLevel": 0,
            "offTimer": 0,
            "delay": 0,
            "divisor": 0.52834,
            "flowRate": 3.7854,
            "sensorType": "FLOW",
        },
        "status": {
            "waterFlow": {
                "value": 542.0042035155608,
                "unit": "gal",
            },
            "active": None,
        },
    }


@fixture
def flow_summary_json(request):
    if request.param:
        yield {"totalWaterVolume": {"value": 23134.67952992029, "unit": "gal"}}
    else:
        yield None


@fixture
def controller_json(rain_sensor_json, flow_sensor_json):
    yield {
        "id": 9876,
        "name": "Main Controller",
        "softwareVersion": "s0",
        "hardware": {
            "serialNumber": "A0B1C2D3",
            "version": "1.0",
            "status": "All good!",
            "model": {
                "name": "HPC 10",
                "description": "HPC 10 Station Controller",
            },
            "firmware": [{"type": "A", "version": "1.0"}],
        },
        "lastContactTime": {
            "timestamp": 1672531200,
            "value": "Sun, 01 Jan 23 00:12:00",
        },
        "lastAction": {
            "timestamp": 1672531200,
            "value": "Sun, 01 Jan 23 00:12:00",
        },
        "online": True,
        "sensors": [rain_sensor_json, flow_sensor_json],
        "permittedProgramStartTimes": [],
        "status": {
            "summary": "All good!",
            "online": True,
            "actualWaterTime": {"value": 10},
            "normalWaterTime": {"value": 10},
            "lastContact": {
                "timestamp": 1672531200,
                "value": "Sun, 01 Jan 23 00:12:00",
            },
        },
    }


@fixture
def zone_json():
    yield {
        "id": 1,
        "number": {
            "value": 1,
            "label": "One",
        },
        "name": "Zone A",
        "wateringSettings": {
            "fixedWateringAdjustment": 100,
            "cycleAndSoakSettings": None,
            "advancedProgram": {
                "id": 4729361,
                "name": "",
                "schedulingMethod": {"value": 0, "label": "Time Based"},
                "monthlyWateringAdjustments": [
                    100,
                    100,
                    100,
                    100,
                    100,
                    100,
                    100,
                    100,
                    100,
                    100,
                    100,
                    100,
                ],
                "appliesToZones": [
                    {
                        "id": 5955343,
                        "number": {"value": 1, "label": "Zone 1"},
                        "name": "Front Lawn",
                    }
                ],
                "zoneSpecific": True,
                "advancedProgramId": 5655942,
                "wateringFrequency": {
                    "label": "Frequency",
                    "period": {
                        "value": None,
                        "label": "Every Program Start Time",
                    },
                    "description": "Every Program Start Time unless modified by your Watering Triggers",
                },
                "runTimeGroup": {
                    "id": 49923604,
                    "name": None,
                    "duration": 20,
                },
            },
        },
        "scheduledRuns": {
            "summary": "",
            "currentRun": None,
            "nextRun": None,
            "status": None,
        },
        "pastRuns": {"lastRun": None, "runs": []},
        "status": {
            "relativeWaterBalance": 0,
            "suspendedUntil": {
                "timestamp": 1672531200,
                "value": "Sun, 01 Jan 23 00:12:00",
            },
        },
        "suspensions": [],
    }


@fixture
def watering_report_json():
    yield {
        "watering": [
            {
                "runEvent": {
                    "id": "35220026902",
                    "zone": {
                        "id": 5955343,
                        "number": {"value": 1, "label": "Zone 1"},
                        "name": "Front Lawn",
                    },
                    "standardProgram": {
                        "id": 343434,
                        "name": "",
                    },
                    "advancedProgram": {"id": 4729361, "name": ""},
                    "reportedStartTime": {
                        "value": "Fri, 01 Dec 23 04:00:00 -0800",
                        "timestamp": 1701432000,
                    },
                    "reportedEndTime": {
                        "value": "Fri, 01 Dec 23 04:20:00 -0800",
                        "timestamp": 1701433200,
                    },
                    "reportedDuration": 1200,
                    "reportedStatus": {
                        "value": 1,
                        "label": "Normal watering cycle",
                    },
                    "reportedWaterUsage": {
                        "value": 34.000263855044786,
                        "unit": "gal",
                    },
                    "reportedStopReason": {
                        "finishedNormally": True,
                        "description": ["Finished normally"],
                    },
                    "reportedCurrent": {"value": 280, "unit": "mA"},
                }
            },
            {
                "runEvent": {
                    "id": "35220026903",
                    "zone": {
                        "id": 5955345,
                        "number": {"value": 2, "label": "Zone 2"},
                        "name": "Front Trees",
                    },
                    "standardProgram": None,
                    "advancedProgram": {"id": 4729362, "name": ""},
                    "reportedStartTime": {
                        "value": "Fri, 01 Nov 23 04:19:59 -0800",
                        "timestamp": 1698797999,
                    },
                    "reportedEndTime": {
                        "value": "Fri, 01 Nov 23 04:39:59 -0800",
                        "timestamp": 1698799199,
                    },
                    "reportedDuration": 1200,
                    "reportedStatus": {
                        "value": 1,
                        "label": "Normal watering cycle",
                    },
                    "reportedWaterUsage": {
                        "value": 49.00048126864295,
                        "unit": "gal",
                    },
                    "reportedStopReason": {
                        "finishedNormally": True,
                        "description": ["Finished normally"],
                    },
                    "reportedCurrent": {"value": 280, "unit": "mA"},
                }
            },
        ]
    }


async def test_get_user(api: Hydrawise, mock_session, controller_json, zone_json):
    controller_json["zones"] = [zone_json]
    mock_session.execute.return_value = {
        "me": {
            "id": 1234,
            "customerId": 1,
            "name": "My Name",
            "email": "me@asdf.com",
            "controllers": [controller_json],
        }
    }
    user = await api.get_user()
    mock_session.execute.assert_awaited_once()
    [selector] = mock_session.execute.await_args.args
    query = print_ast(selector)
    assert "controllers {" in query
    assert query.count("zones {") == 2
    assert user.id == 1234
    assert user.name == "My Name"
    assert user.email == "me@asdf.com"
    assert len(user.controllers) == 1
    assert len(user.controllers[0].zones) == 1


async def test_get_user_no_zones(api: Hydrawise, mock_session, controller_json):
    mock_session.execute.return_value = {
        "me": {
            "id": 1234,
            "customerId": 1,
            "name": "My Name",
            "email": "me@asdf.com",
            "controllers": [controller_json],
        }
    }
    user = await api.get_user(fetch_zones=False)
    mock_session.execute.assert_awaited_once()
    [selector] = mock_session.execute.await_args.args
    query = print_ast(selector)
    assert "controllers {" in query
    assert query.count("zones {") == 1
    assert user.id == 1234
    assert user.name == "My Name"
    assert user.email == "me@asdf.com"
    assert len(user.controllers) == 1
    assert len(user.controllers[0].zones) == 0


async def test_get_controllers(api: Hydrawise, mock_session, controller_json):
    mock_session.execute.return_value = {"me": {"controllers": [controller_json]}}
    [controller] = await api.get_controllers()
    mock_session.execute.assert_awaited_once()
    [selector] = mock_session.execute.await_args.args
    query = print_ast(selector)
    assert query.count("zones {") == 2
    assert controller.last_contact_time == datetime(2023, 1, 1, 0, 0, 0)
    assert controller.last_action == datetime(2023, 1, 1, 0, 0, 0)
    assert controller.status.actual_water_time.value == timedelta(minutes=10)


async def test_get_controller(api: Hydrawise, mock_session, controller_json):
    mock_session.execute.return_value = {"controller": controller_json}
    controller = await api.get_controller(9876)
    mock_session.execute.assert_awaited_once()
    [selector] = mock_session.execute.await_args.args
    query = print_ast(selector)
    assert "controller(" in query
    assert "controllerId: 9876" in query
    assert query.count("zones {") == 2

    assert controller.last_contact_time == datetime(2023, 1, 1, 0, 0, 0)
    assert controller.last_action == datetime(2023, 1, 1, 0, 0, 0)
    assert controller.status.actual_water_time.value == timedelta(minutes=10)


async def test_get_zones(api: Hydrawise, mock_session, controller_json, zone_json):
    mock_session.execute.return_value = {"controller": {"zones": [zone_json]}}
    ctrl = deserialize(Controller, controller_json)
    [zone] = await api.get_zones(ctrl)
    mock_session.execute.assert_awaited_once()
    [selector] = mock_session.execute.await_args.args
    query = print_ast(selector)
    assert "controller(" in query
    assert "controllerId: 9876" in query


async def test_get_zone(api: Hydrawise, mock_session, zone_json):
    mock_session.execute.return_value = {"zone": zone_json}
    zone = await api.get_zone(1)
    mock_session.execute.assert_awaited_once()
    [selector] = mock_session.execute.await_args.args
    query = print_ast(selector)
    assert "zone(" in query
    assert "zoneId: 1" in query


async def test_start_zone(api: Hydrawise, mock_session, zone_json):
    mock_session.execute.return_value = {"startZone": {"status": "OK"}}
    zone = deserialize(Zone, zone_json)
    await api.start_zone(zone, custom_run_duration=10)
    mock_session.execute.assert_awaited_once()
    [selector] = mock_session.execute.await_args.args
    query = print_ast(selector)
    assert "startZone(" in query
    assert "zoneId: 1" in query
    assert "markRunAsScheduled: false" in query
    assert "customRunDuration: 10" in query


async def test_stop_zone(api: Hydrawise, mock_session, zone_json):
    mock_session.execute.return_value = {"stopZone": {"status": "OK"}}
    zone = deserialize(Zone, zone_json)
    await api.stop_zone(zone)
    mock_session.execute.assert_awaited_once()
    [selector] = mock_session.execute.await_args.args
    query = print_ast(selector)
    assert "stopZone(" in query
    assert "zoneId: 1" in query


async def test_start_all_zones(api: Hydrawise, mock_session, controller_json):
    mock_session.execute.return_value = {"startAllZones": {"status": "OK"}}
    ctrl = deserialize(Controller, controller_json)
    await api.start_all_zones(ctrl, custom_run_duration=10)
    mock_session.execute.assert_awaited_once()
    [selector] = mock_session.execute.await_args.args
    query = print_ast(selector)
    assert "startAllZones(" in query
    assert "controllerId: 9876" in query
    assert "markRunAsScheduled: false" in query
    assert "customRunDuration: 10" in query


async def test_stop_all_zones(api: Hydrawise, mock_session, controller_json):
    mock_session.execute.return_value = {"stopAllZones": {"status": "OK"}}
    ctrl = deserialize(Controller, controller_json)
    await api.stop_all_zones(ctrl)
    mock_session.execute.assert_awaited_once()
    [selector] = mock_session.execute.await_args.args
    query = print_ast(selector)
    assert "stopAllZones(" in query
    assert "controllerId: 9876" in query


async def test_suspend_zone(api: Hydrawise, mock_session, zone_json):
    mock_session.execute.return_value = {"suspendZone": {"status": "OK"}}
    zone = deserialize(Zone, zone_json)
    await api.suspend_zone(zone, until=datetime(2023, 1, 1, 0, 0, 0))
    mock_session.execute.assert_awaited_once()
    [selector] = mock_session.execute.await_args.args
    query = print_ast(selector)
    assert "suspendZone(" in query
    assert "zoneId: 1" in query
    assert 'until: "Sun, 01 Jan 23 00:12:00 +0000"' in query


async def test_resume_zone(api: Hydrawise, mock_session, zone_json):
    mock_session.execute.return_value = {"resumeZone": {"status": "OK"}}
    zone = deserialize(Zone, zone_json)
    await api.resume_zone(zone)
    mock_session.execute.assert_awaited_once()
    [selector] = mock_session.execute.await_args.args
    query = print_ast(selector)
    assert "resumeZone(" in query
    assert "zoneId: 1" in query


async def test_suspend_all_zones(api: Hydrawise, mock_session, controller_json):
    mock_session.execute.return_value = {"suspendAllZones": {"status": "OK"}}
    ctrl = deserialize(Controller, controller_json)
    await api.suspend_all_zones(ctrl, until=datetime(2023, 1, 1, 0, 0, 0))
    mock_session.execute.assert_awaited_once()
    [selector] = mock_session.execute.await_args.args
    query = print_ast(selector)
    assert "suspendAllZones(" in query
    assert "controllerId: 9876" in query
    assert 'until: "Sun, 01 Jan 23 00:12:00 +0000"' in query


async def test_resume_all_zones(api: Hydrawise, mock_session, controller_json):
    mock_session.execute.return_value = {"resumeAllZones": {"status": "OK"}}
    ctrl = deserialize(Controller, controller_json)
    await api.resume_all_zones(ctrl)
    mock_session.execute.assert_awaited_once()
    [selector] = mock_session.execute.await_args.args
    query = print_ast(selector)
    assert "resumeAllZones(" in query
    assert "controllerId: 9876" in query


async def test_delete_zone_suspension(api: Hydrawise, mock_session):
    mock_session.execute.return_value = {"deleteZoneSuspension": True}
    suspension = ZoneSuspension(
        id=2222,
        start_time=datetime(2023, 1, 1, 0, 0, 0),
        end_time=datetime(2023, 1, 2, 0, 0, 0),
    )
    await api.delete_zone_suspension(suspension)
    mock_session.execute.assert_awaited_once()
    [selector] = mock_session.execute.await_args.args
    query = print_ast(selector)
    assert "deleteZoneSuspension(" in query
    assert "id: 2222" in query


async def test_get_sensors(
    api: Hydrawise,
    mock_session,
    rain_sensor_json,
    flow_sensor_json,
    controller_json,
):
    mock_session.execute.return_value = {
        "controller": {"sensors": [rain_sensor_json, flow_sensor_json]}
    }
    ctrl = deserialize(Controller, controller_json)
    sensors = await api.get_sensors(ctrl)
    mock_session.execute.assert_awaited_once()
    [selector] = mock_session.execute.await_args.args
    query = print_ast(selector)
    assert "sensors {" in query


@pytest.mark.parametrize("flow_summary_json", (True, False), indirect=True)
async def test_get_water_flow_summary(
    api: Hydrawise,
    mock_session,
    controller_json,
    flow_sensor_json,
    flow_summary_json,
):
    mock_session.execute.return_value = {
        "controller": {
            "sensors": [flow_sensor_json | {"flowSummary": flow_summary_json}]
        }
    }

    ctrl = deserialize(Controller, controller_json)
    sensor = deserialize(Sensor, flow_sensor_json)
    water_flow_summary = await api.get_water_flow_summary(
        ctrl,
        sensor,
        datetime(2023, 11, 1, 0, 0, 0),
        datetime(2023, 11, 30, 0, 0, 0),
    )
    mock_session.execute.assert_awaited_once()
    [selector] = mock_session.execute.await_args.args
    query = print_ast(selector)
    assert "flowSummary(" in query


async def test_get_watering_report(
    api: Hydrawise, mock_session, controller_json, watering_report_json
):
    mock_session.execute.return_value = {
        "controller": {"reports": watering_report_json}
    }
    ctrl = deserialize(Controller, controller_json)
    report = await api.get_watering_report(
        ctrl, datetime(2023, 12, 1, 0, 0, 0), datetime(2023, 12, 4, 0, 0, 0)
    )
    mock_session.execute.assert_awaited_once()
    [selector] = mock_session.execute.await_args.args
    query = print_ast(selector)
    assert "reports" in query
    assert "watering" in query
    assert len(report) == 1


@pytest.mark.parametrize("flow_summary_json", (True, False), indirect=True)
async def test_get_water_use_summary(
    api: Hydrawise,
    mock_session,
    controller_json,
    watering_report_json,
    flow_sensor_json,
    flow_summary_json,
):
    mock_session.execute.return_value = {
        "controller": {
            "reports": watering_report_json,
            "sensors": [flow_sensor_json | {"flowSummary": flow_summary_json}],
        }
    }
    ctrl = deserialize(Controller, controller_json)
    summary = await api.get_water_use_summary(
        ctrl, datetime(2023, 12, 1, 0, 0, 0), datetime(2023, 12, 4, 0, 0, 0)
    )
    mock_session.execute.assert_awaited_once()
    [selector] = mock_session.execute.await_args.args
    query = print_ast(selector)
    assert "reports" in query
    assert "watering" in query
    assert "flowSummary(" in query
    assert summary.active_use_by_zone_id[5955343] == 34.000263855044786
    assert summary.total_active_use == 34.000263855044786
    assert summary.total_inactive_use == (
        23100.679266065246 if flow_summary_json else 0.0
    )
    assert summary.unit == "gal"
