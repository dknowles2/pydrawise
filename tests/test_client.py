from copy import deepcopy
from datetime import datetime, timedelta
from unittest.mock import create_autospec, patch

import pytest
from gql import Client
from gql.client import AsyncClientSession
from gql.transport.aiohttp import AIOHTTPTransport
from graphql import print_ast
from pytest import fixture

from pydrawise.auth import Auth
from pydrawise.client import Hydrawise
from pydrawise.const import DEFAULT_APP_ID, GRAPHQL_URL
from pydrawise.exceptions import MutationError
from pydrawise.schema import DSL_SCHEMA, Controller, Sensor, Zone, ZoneSuspension
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
    query = print_ast(selector.document)
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
    query = print_ast(selector.document)
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
    query = print_ast(selector.document)
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
    query = print_ast(selector.document)
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
    query = print_ast(selector.document)
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
    query = print_ast(selector.document)
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
    [_zone] = await api.get_zones(ctrl)
    mock_session.execute.assert_awaited_once()
    [selector] = mock_session.execute.await_args.args
    query = print_ast(selector.document)
    assert "controller(" in query
    assert "controllerId: 9876" in query


async def test_get_zone(api: Hydrawise, mock_session, zone_json):
    mock_session.execute.return_value = {"zone": zone_json}
    await api.get_zone(1)
    mock_session.execute.assert_awaited_once()
    [selector] = mock_session.execute.await_args.args
    query = print_ast(selector.document)
    assert "zone(" in query
    assert "zoneId: 1" in query


async def test_start_zone(api: Hydrawise, mock_session, zone_json):
    mock_session.execute.return_value = {"startZone": {"status": "OK"}}
    zone = deserialize(Zone, zone_json)
    await api.start_zone(zone, custom_run_duration=10)
    mock_session.execute.assert_awaited_once()
    [selector] = mock_session.execute.await_args.args
    query = print_ast(selector.document)
    assert "startZone(" in query
    assert "zoneId: 266" in query
    assert "markRunAsScheduled: false" in query
    assert "customRunDuration: 10" in query


async def test_start_zone_warning(api: Hydrawise, mock_session, zone_json):
    zone = deserialize(Zone, zone_json)
    mock_session.execute.return_value = {
        "startZone": {
            "status": "WARNING",
            "summary": f"Starting {zone.name} in 5 seconds",
        }
    }
    await api.start_zone(zone, custom_run_duration=10)
    mock_session.execute.assert_awaited_once()
    [selector] = mock_session.execute.await_args.args
    query = print_ast(selector.document)
    assert "startZone(" in query
    assert "zoneId: 266" in query
    assert "markRunAsScheduled: false" in query
    assert "customRunDuration: 10" in query


async def test_start_zone_error(api: Hydrawise, mock_session, zone_json):
    mock_session.execute.return_value = {
        "startZone": {"status": "ERROR", "summary": "LOL ERROR"}
    }
    zone = deserialize(Zone, zone_json)
    with pytest.raises(MutationError, match="LOL ERROR"):
        await api.start_zone(zone, custom_run_duration=10)

    mock_session.execute.assert_awaited_once()
    [selector] = mock_session.execute.await_args.args
    query = print_ast(selector.document)
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
    query = print_ast(selector.document)
    assert "stopZone(" in query
    assert "zoneId: 266" in query


async def test_start_all_zones(api: Hydrawise, mock_session, controller_json):
    mock_session.execute.return_value = {"startAllZones": {"status": "OK"}}
    ctrl = deserialize(Controller, controller_json)
    await api.start_all_zones(ctrl, custom_run_duration=10)
    mock_session.execute.assert_awaited_once()
    [selector] = mock_session.execute.await_args.args
    query = print_ast(selector.document)
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
    query = print_ast(selector.document)
    assert "stopAllZones(" in query
    assert "controllerId: 9876" in query


async def test_suspend_zone(api: Hydrawise, mock_session, zone_json):
    mock_session.execute.return_value = {"suspendZone": {"status": "OK"}}
    zone = deserialize(Zone, zone_json)
    await api.suspend_zone(zone, until=datetime(2023, 1, 1, 0, 0, 0))
    mock_session.execute.assert_awaited_once()
    [selector] = mock_session.execute.await_args.args
    query = print_ast(selector.document)
    assert "suspendZone(" in query
    assert "zoneId: 266" in query
    assert 'until: "Sun, 01 Jan 23 00:00:00 +0000"' in query


async def test_resume_zone(api: Hydrawise, mock_session, zone_json):
    mock_session.execute.return_value = {"resumeZone": {"status": "OK"}}
    zone = deserialize(Zone, zone_json)
    await api.resume_zone(zone)
    mock_session.execute.assert_awaited_once()
    [selector] = mock_session.execute.await_args.args
    query = print_ast(selector.document)
    assert "resumeZone(" in query
    assert "zoneId: 266" in query


async def test_suspend_all_zones(api: Hydrawise, mock_session, controller_json):
    mock_session.execute.return_value = {"suspendAllZones": {"status": "OK"}}
    ctrl = deserialize(Controller, controller_json)
    await api.suspend_all_zones(ctrl, until=datetime(2023, 1, 1, 0, 0, 0))
    mock_session.execute.assert_awaited_once()
    [selector] = mock_session.execute.await_args.args
    query = print_ast(selector.document)
    assert "suspendAllZones(" in query
    assert "controllerId: 9876" in query
    assert 'until: "Sun, 01 Jan 23 00:00:00 +0000"' in query


async def test_resume_all_zones(api: Hydrawise, mock_session, controller_json):
    mock_session.execute.return_value = {"resumeAllZones": {"status": "OK"}}
    ctrl = deserialize(Controller, controller_json)
    await api.resume_all_zones(ctrl)
    mock_session.execute.assert_awaited_once()
    [selector] = mock_session.execute.await_args.args
    query = print_ast(selector.document)
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
    query = print_ast(selector.document)
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
    query = print_ast(selector.document)
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
    query = print_ast(selector.document)
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
    query = print_ast(selector.document)
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
    query = print_ast(selector.document)
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
    query = print_ast(selector.document)
    assert "reports" in query
    assert "watering" in query
    assert 5955343 not in summary.active_use_by_zone_id
    assert summary.active_time_by_zone_id[5955343] == timedelta(seconds=1200)
    assert summary.total_active_use is None
    assert summary.total_inactive_use is None
    assert summary.total_active_time == timedelta(seconds=1200)


async def test_mutation_falsy_response_raises(api: Hydrawise, mock_session, zone_json):
    """A mutation returning a falsy non-dict is treated as a failed boolean result."""
    mock_session.execute.return_value = {"stopZone": False}
    zone = deserialize(Zone, zone_json)
    with pytest.raises(MutationError):
        await api.stop_zone(zone)


async def test_mutation_truthy_bool_response_succeeds(
    api: Hydrawise, mock_session, zone_json
):
    """A truthy non-dict response is a successful boolean mutation."""
    mock_session.execute.return_value = {"stopZone": True}
    zone = deserialize(Zone, zone_json)
    await api.stop_zone(zone)
    mock_session.execute.assert_awaited_once()


async def test_update_master_valve(
    api: Hydrawise, mock_session, controller_json, zone_json
):
    mock_session.execute.return_value = {
        "updateControllerMasterValve": {"status": "OK"}
    }
    ctrl = deserialize(Controller, controller_json)
    zone = deserialize(Zone, zone_json)
    await api.update_master_valve(ctrl, zone)
    mock_session.execute.assert_awaited_once()
    [selector] = mock_session.execute.await_args.args
    query = print_ast(selector.document)
    assert "updateControllerMasterValve(" in query
    assert f"controllerId: {ctrl.id}" in query
    assert f"zoneNumber: {zone.number.value}" in query


async def test_get_water_flow_summary_unknown_sensor(
    api: Hydrawise, mock_session, controller_json, flow_sensor_json
):
    """Asking for a sensor the controller doesn't have is an error, not an empty result."""
    mock_session.execute.return_value = {"controller": {"sensors": []}}
    ctrl = deserialize(Controller, controller_json)
    sensor = deserialize(Sensor, flow_sensor_json)
    with pytest.raises(ValueError, match=f"id={sensor.id} not found"):
        await api.get_water_flow_summary(
            ctrl, sensor, datetime(2023, 11, 1), datetime(2023, 11, 30)
        )


async def test_get_water_flow_summary_sensor_without_flow(
    api: Hydrawise, mock_session, controller_json, flow_sensor_json
):
    """A sensor that reports no flow information at all is an error."""
    mock_session.execute.return_value = {"controller": {"sensors": [flow_sensor_json]}}
    ctrl = deserialize(Controller, controller_json)
    sensor = deserialize(Sensor, flow_sensor_json)
    with pytest.raises(ValueError, match="does not have any flow information"):
        await api.get_water_flow_summary(
            ctrl, sensor, datetime(2023, 11, 1), datetime(2023, 11, 30)
        )


@pytest.mark.parametrize("flow_summary_json", (True,), indirect=True)
async def test_get_water_use_summary_ignores_malformed_report_entries(
    api: Hydrawise,
    mock_session,
    controller_json,
    watering_report_json,
    flow_sensor_json,
    flow_summary_json,
):
    """Entries missing a run event or a zone must not corrupt the per-zone totals.

    They are dropped by _prune_watering_report_entries rather than by the
    `zone is None` guard in the summing loop: apischema's fall_back_on_default
    turns a null runEvent/zone into a default object, never None, so such an
    entry arrives with no reported start or end time and is pruned.
    """
    report = deepcopy(watering_report_json)
    [real_entry] = report["watering"]
    report["watering"] = [
        {"runEvent": None},
        deepcopy(real_entry) | {"runEvent": deepcopy(real_entry["runEvent"])},
        real_entry,
    ]
    report["watering"][1]["runEvent"]["zone"] = None

    mock_session.execute.return_value = {
        "controller": {
            "reports": report,
            "sensors": [flow_sensor_json | {"flowSummary": flow_summary_json}],
        }
    }
    ctrl = deserialize(Controller, controller_json)
    summary = await api.get_water_use_summary(
        ctrl, datetime(2023, 12, 1, 0, 0, 0), datetime(2023, 12, 4, 0, 0, 0)
    )
    # Only the one well-formed entry is counted.
    assert summary.active_time_by_zone_id == {5955343: timedelta(seconds=1200)}
    assert summary.total_active_time == timedelta(seconds=1200)
    assert summary.total_active_use == 34.000263855044786


@pytest.mark.parametrize("flow_summary_json", (True,), indirect=True)
async def test_get_water_use_summary_takes_unit_from_flow_sensor(
    api: Hydrawise,
    mock_session,
    controller_json,
    flow_sensor_json,
    flow_summary_json,
):
    """A flow sensor supplies the unit when no watering happened in the window.

    All measured use is then inactive -- water passed the meter without any
    zone running.
    """
    mock_session.execute.return_value = {
        "controller": {
            "reports": {"watering": []},
            "sensors": [flow_sensor_json | {"flowSummary": flow_summary_json}],
        }
    }
    ctrl = deserialize(Controller, controller_json)
    summary = await api.get_water_use_summary(
        ctrl, datetime(2023, 12, 1, 0, 0, 0), datetime(2023, 12, 4, 0, 0, 0)
    )
    assert summary.unit == "gal"
    assert summary.total_active_use == 0.0
    assert summary.total_active_time == timedelta()
    assert summary.total_inactive_use == summary.total_use == 23134.67952992029


async def test_client_sends_bearer_token_and_targets_the_graphql_url(mock_auth):
    """The gql client is built with the auth token in the Authorization header."""
    api = Hydrawise(mock_auth)
    client = await api._client()
    transport = client.transport
    assert isinstance(transport, AIOHTTPTransport)
    assert transport.url == GRAPHQL_URL
    assert transport.headers == {"Authorization": "__token__"}
    mock_auth.token.assert_awaited_once()


async def test_client_app_id_is_sent_as_a_query_param(api: Hydrawise, mock_session):
    """app_id rides along on queries as the appVersion param."""
    mock_session.execute.return_value = {"me": {}}
    await api._query(DSL_SCHEMA.Query.me.select(DSL_SCHEMA.User.id))
    assert mock_session.execute.await_args.kwargs["extra_args"] == {
        "params": {"appVersion": DEFAULT_APP_ID}
    }


async def test_client_without_app_id_sends_no_extra_params(mock_auth, mock_client):
    """An empty app_id omits the param entirely rather than sending a blank one."""
    api = Hydrawise(mock_auth, app_id="")
    with patch.object(api, "_client", return_value=mock_client):
        session = mock_client.__aenter__.return_value
        session.execute.return_value = {"me": {}}
        await api._query(DSL_SCHEMA.Query.me.select(DSL_SCHEMA.User.id))
        assert session.execute.await_args.kwargs["extra_args"] == {}
