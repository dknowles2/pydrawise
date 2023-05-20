from datetime import datetime, timedelta
from unittest.mock import create_autospec, patch

from gql import Client
from gql.client import AsyncClientSession
from graphql import print_ast
from pytest import fixture

from pydrawise.auth import Auth
from pydrawise.client import Hydrawise
from pydrawise.schema import Controller, Zone, ZoneSuspension
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
def controller_json():
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
        "sensors": [],
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
            "fixedWateringAdjustment": 0,
            "cycleAndSoakSettings": None,
            "advancedProgram": None,
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


async def test_get_user(api: Hydrawise, mock_session):
    mock_session.execute.return_value = {
        "me": {
            "id": 1234,
            "customerId": 1,
            "name": "My Name",
            "email": "me@asdf.com",
        }
    }
    user = await api.get_user()
    assert user.id == 1234
    assert user.name == "My Name"
    assert user.email == "me@asdf.com"


async def test_get_controllers(api: Hydrawise, mock_session, controller_json):
    mock_session.execute.return_value = {"me": {"controllers": [controller_json]}}
    [controller] = await api.get_controllers()
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
