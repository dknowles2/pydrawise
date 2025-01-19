from datetime import datetime, timedelta
from unittest.mock import create_autospec, patch

import pytest
from gql import Client
from gql.client import AsyncClientSession
from graphql import print_ast
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


async def test_get_user(api: Hydrawise, mock_session, user_json, zone_json):
    user_json["controllers"][0]["zones"] = [zone_json]
    mock_session.execute.return_value = {"me": user_json}
    user = await api.get_user()
    mock_session.execute.assert_awaited_once()
    [selector] = mock_session.execute.await_args.args
    query = print_ast(selector)
    assert "controllers {" in query
    assert query.count("zones {") == 2
    assert user.id == 1234
    assert user.customer_id == 2222
    assert user.name == "My Name"
    assert user.email == "me@asdf.com"
    assert len(user.controllers) == 1
    assert len(user.controllers[0].zones) == 1


async def test_get_user_no_zones(api: Hydrawise, mock_session, user_json):
    mock_session.execute.return_value = {"me": user_json}
    user = await api.get_user(fetch_zones=False)
    mock_session.execute.assert_awaited_once()
    [selector] = mock_session.execute.await_args.args
    query = print_ast(selector)
    assert "controllers {" in query
    assert query.count("zones {") == 1
    assert user.id == 1234
    assert user.customer_id == 2222
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
    assert controller.status is not None
    assert controller.status.actual_water_time.value == timedelta(minutes=10)


async def test_get_controllers_no_zones(api: Hydrawise, mock_session, controller_json):
    mock_session.execute.return_value = {"me": {"controllers": [controller_json]}}
    [controller] = await api.get_controllers(fetch_zones=False)
    mock_session.execute.assert_awaited_once()
    [selector] = mock_session.execute.await_args.args
    query = print_ast(selector)
    assert query.count("zones {") == 1
    assert controller.last_contact_time == datetime(2023, 1, 1, 0, 0, 0)
    assert controller.last_action == datetime(2023, 1, 1, 0, 0, 0)
    assert controller.status is not None
    assert controller.status.actual_water_time.value == timedelta(minutes=10)
    assert len(controller.zones) == 0


async def test_get_controllers_no_sensors(
    api: Hydrawise, mock_session, controller_json
):
    del controller_json["sensors"]
    mock_session.execute.return_value = {"me": {"controllers": [controller_json]}}
    [controller] = await api.get_controllers(fetch_sensors=False)
    mock_session.execute.assert_awaited_once()
    [selector] = mock_session.execute.await_args.args
    query = print_ast(selector)
    assert query.count("sensors {") == 0
    assert controller.last_contact_time == datetime(2023, 1, 1, 0, 0, 0)
    assert controller.last_action == datetime(2023, 1, 1, 0, 0, 0)
    assert controller.status is not None
    assert controller.status.actual_water_time.value == timedelta(minutes=10)
    assert len(controller.sensors) == 0


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
    assert controller.status is not None
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
    await api.get_zone(1)
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
    assert "zoneId: 266" in query
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
    assert "zoneId: 266" in query


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
    assert "zoneId: 266" in query
    assert 'until: "Sun, 01 Jan 23 00:12:00 +0000"' in query


async def test_resume_zone(api: Hydrawise, mock_session, zone_json):
    mock_session.execute.return_value = {"resumeZone": {"status": "OK"}}
    zone = deserialize(Zone, zone_json)
    await api.resume_zone(zone)
    mock_session.execute.assert_awaited_once()
    [selector] = mock_session.execute.await_args.args
    query = print_ast(selector)
    assert "resumeZone(" in query
    assert "zoneId: 266" in query


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
    await api.get_sensors(ctrl)
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
    await api.get_water_flow_summary(
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
    assert summary.active_time_by_zone_id[5955343] == timedelta(seconds=1200)
    assert summary.total_active_use == 34.000263855044786
    assert summary.total_inactive_use == (
        23100.679266065246 if flow_summary_json else 0.0
    )
    assert summary.total_active_time == timedelta(seconds=1200)
    assert summary.unit == "gal"


async def test_get_water_use_summary_without_sensor(
    api: Hydrawise,
    mock_session,
    controller_json,
    watering_report_without_sensor_json,
):
    mock_session.execute.return_value = {
        "controller": {
            "reports": watering_report_without_sensor_json,
        }
    }
    ctrl = deserialize(Controller, controller_json)
    ctrl.sensors = None
    summary = await api.get_water_use_summary(
        ctrl, datetime(2023, 12, 1, 0, 0, 0), datetime(2023, 12, 4, 0, 0, 0)
    )
    mock_session.execute.assert_awaited_once()
    [selector] = mock_session.execute.await_args.args
    query = print_ast(selector)
    assert "reports" in query
    assert "watering" in query
    assert 5955343 not in summary.active_use_by_zone_id
    assert summary.active_time_by_zone_id[5955343] == timedelta(seconds=1200)
    assert summary.total_active_use is None
    assert summary.total_inactive_use is None
    assert summary.total_active_time == timedelta(seconds=1200)
