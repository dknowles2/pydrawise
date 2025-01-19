from copy import deepcopy
from datetime import datetime, timedelta
from unittest.mock import create_autospec

from freezegun import freeze_time
from pytest import fixture

from pydrawise import hybrid
from pydrawise.auth import HybridAuth
from pydrawise.client import Hydrawise

FROZEN_TIME = "2023-01-01 01:00:00"


@fixture
def hybrid_auth():
    mock_auth = create_autospec(HybridAuth, instance=True, api_key="__api_key__")
    mock_auth.token.return_value = "__token__"
    yield mock_auth


@fixture
def mock_gql_client():
    yield create_autospec(Hydrawise, instance=True, spec_set=True)


@fixture
def api(hybrid_auth, mock_gql_client):
    yield hybrid.HybridClient(hybrid_auth, gql_client=mock_gql_client)


def test_throttler():
    with freeze_time(FROZEN_TIME) as frozen_time:
        throttle = hybrid.Throttler(epoch_interval=timedelta(seconds=60))
        assert throttle.check()
        throttle.mark()
        assert not throttle.check()

        # Increasing tokens_per_epoch allows another token to be consumed
        throttle.tokens_per_epoch = 2
        assert throttle.check()

        # Advancing time resets the throttler, allowing 2 tokens again
        frozen_time.tick(timedelta(seconds=61))
        assert throttle.check(2)


async def test_get_user(api, hybrid_auth, mock_gql_client, user, zone, status_schedule):
    with freeze_time(FROZEN_TIME):
        user.controllers[0].zones = [zone]
        assert user.controllers[0].zones[0].status.suspended_until != datetime.max

        # First fetch should query the GraphQL API
        mock_gql_client.get_user.return_value = deepcopy(user)
        assert await api.get_user() == user
        mock_gql_client.get_user.assert_awaited_once_with(fetch_zones=True)

        # Second fetch should also query the GraphQL API
        mock_gql_client.get_user.reset_mock()
        assert await api.get_user() == user
        mock_gql_client.get_user.assert_awaited_once_with(fetch_zones=True)

        # Third fetch should query the REST API because we're out of tokens
        mock_gql_client.get_user.reset_mock()
        status_schedule["relays"] = [status_schedule["relays"][0]]
        status_schedule["relays"][0]["time"] = 1576800000
        status_schedule["relays"][0]["name"] = "Zone A from REST API"
        hybrid_auth.get.return_value = status_schedule
        user2 = await api.get_user()
        mock_gql_client.get_user.assert_not_awaited()
        hybrid_auth.get.assert_awaited_once_with(
            "statusschedule.php", controller_id=user.controllers[0].id
        )
        assert user2.controllers[0].zones[0].status.suspended_until == datetime.max
        assert user2.controllers[0].zones[0].name == "Zone A"

        # Fourth fetch should query the REST API again
        hybrid_auth.get.reset_mock()
        assert await api.get_user() == user2
        mock_gql_client.get_user.assert_not_awaited()
        hybrid_auth.get.assert_awaited_once_with(
            "statusschedule.php", controller_id=user.controllers[0].id
        )

        # Fifth fetch should not make any calls and instead return cached data
        hybrid_auth.get.reset_mock()
        assert await api.get_user() == user2
        mock_gql_client.get_user.assert_not_awaited()
        hybrid_auth.get.assert_not_awaited()


async def test_get_controllers(
    api, hybrid_auth, mock_gql_client, controller, zone, status_schedule
):
    with freeze_time(FROZEN_TIME) as frozen_time:
        controller.zones = [deepcopy(zone)]
        assert controller.zones[0].status.suspended_until != datetime.max

        # First fetch should query the GraphQL API
        mock_gql_client.get_controllers.return_value = [deepcopy(controller)]
        assert await api.get_controllers() == [controller]
        mock_gql_client.get_controllers.assert_awaited_once_with(True, True)

        # Second fetch should also query the GraphQL API
        mock_gql_client.get_controllers.reset_mock()
        assert await api.get_controllers() == [controller]
        mock_gql_client.get_controllers.assert_awaited_once_with(True, True)

        # Third fetch should query the REST API because we're out of tokens
        mock_gql_client.get_controllers.reset_mock()
        status_schedule["relays"] = [status_schedule["relays"][0]]
        status_schedule["relays"][0]["time"] = 1576800000
        status_schedule["relays"][0]["name"] = "Zone A from REST API"
        hybrid_auth.get.return_value = status_schedule
        [controller2] = await api.get_controllers()
        mock_gql_client.get_controllers.assert_not_awaited()
        hybrid_auth.get.assert_awaited_once_with(
            "statusschedule.php", controller_id=controller.id
        )
        assert controller2.zones[0].status.suspended_until == datetime.max
        assert controller2.zones[0].name == "Zone A"

        # Fourth fetch should query the REST API again
        hybrid_auth.get.reset_mock()
        assert await api.get_controllers() == [controller2]
        mock_gql_client.get_controllers.assert_not_awaited()
        hybrid_auth.get.assert_awaited_once_with(
            "statusschedule.php", controller_id=controller.id
        )

        # Fifth fetch should not make any calls and instead return cached data
        hybrid_auth.get.reset_mock()
        assert await api.get_controllers() == [controller2]
        mock_gql_client.get_controllers.assert_not_awaited()
        hybrid_auth.get.assert_not_awaited()

        # After 1 minute, we can query the REST API again.
        # But it thinks we're polling too fast and tells us to back off.
        # Make sure that we listen.
        frozen_time.tick(timedelta(seconds=61))
        hybrid_auth.get.reset_mock()
        status_schedule["nextpoll"] = 120
        assert await api.get_controllers() == [controller2]
        mock_gql_client.get_controllers.assert_not_awaited()
        hybrid_auth.get.assert_awaited_once_with(
            "statusschedule.php", controller_id=controller.id
        )
        # We can still make one more call
        hybrid_auth.get.reset_mock()
        assert await api.get_controllers() == [controller2]
        mock_gql_client.get_controllers.assert_not_awaited()
        hybrid_auth.get.assert_awaited_once_with(
            "statusschedule.php", controller_id=controller.id
        )
        # Now we have to return cached data until the throttler resets.
        hybrid_auth.get.reset_mock()
        assert await api.get_controllers() == [controller2]
        mock_gql_client.get_controllers.assert_not_awaited()
        hybrid_auth.get.assert_not_awaited()

        # Allow the throttler to refresh. Now we can make more calls.
        frozen_time.tick(timedelta(seconds=121))
        hybrid_auth.get.reset_mock()
        assert await api.get_controllers() == [controller2]
        mock_gql_client.get_controllers.assert_not_awaited()
        hybrid_auth.get.assert_awaited_once_with(
            "statusschedule.php", controller_id=controller.id
        )


async def test_get_controller(api, hybrid_auth, mock_gql_client, controller, zone):
    with freeze_time(FROZEN_TIME):
        controller.zones = [deepcopy(zone)]
        assert controller.zones[0].status.suspended_until != datetime.max

        # First fetch should query the GraphQL API
        mock_gql_client.get_controller.return_value = deepcopy(controller)
        assert await api.get_controller(controller.id) == controller
        mock_gql_client.get_controller.assert_awaited_once_with(controller.id)

        # Second fetch should also query the GraphQL API
        mock_gql_client.get_controller.reset_mock()
        assert await api.get_controller(controller.id) == controller
        mock_gql_client.get_controller.assert_awaited_once_with(controller.id)

        # Third fetch should not make any calls and instead return cached data
        mock_gql_client.get_controller.reset_mock()
        assert await api.get_controller(controller.id) == controller
        mock_gql_client.get_controller.assert_not_awaited()
        hybrid_auth.get.assert_not_awaited()


async def test_get_zones(
    api, hybrid_auth, mock_gql_client, controller, zone, status_schedule
):
    with freeze_time(FROZEN_TIME):
        assert zone.status.suspended_until != datetime.max

        # First fetch should query the GraphQL API
        mock_gql_client.get_zones.return_value = [deepcopy(zone)]
        assert await api.get_zones(controller) == [zone]
        mock_gql_client.get_zones.assert_awaited_once_with(controller)

        # Second fetch should also query the GraphQL API
        mock_gql_client.get_zones.reset_mock()
        assert await api.get_zones(controller) == [zone]
        mock_gql_client.get_zones.assert_awaited_once_with(controller)

        # Third fetch should query the REST API because we're out of tokens
        mock_gql_client.get_zones.reset_mock()
        status_schedule["relays"] = [status_schedule["relays"][0]]
        status_schedule["relays"][0]["time"] = 1576800000
        status_schedule["relays"][0]["name"] = "Zone A from REST API"
        hybrid_auth.get.return_value = status_schedule
        [zone2] = await api.get_zones(controller)
        mock_gql_client.get_zones.assert_not_awaited()
        hybrid_auth.get.assert_awaited_once_with(
            "statusschedule.php", controller_id=controller.id
        )
        assert zone2.status.suspended_until == datetime.max
        assert zone2.name == "Zone A"

        # Fourth fetch should query the REST API again
        hybrid_auth.get.reset_mock()
        assert await api.get_zones(controller) == [zone2]
        mock_gql_client.get_zones.assert_not_awaited()
        hybrid_auth.get.assert_awaited_once_with(
            "statusschedule.php", controller_id=controller.id
        )

        # Fifth fetch should not make any calls and instead return cached data
        hybrid_auth.get.reset_mock()
        assert await api.get_zones(controller) == [zone2]
        mock_gql_client.get_zones.assert_not_awaited()
        hybrid_auth.get.assert_not_awaited()


async def test_get_zone(api, hybrid_auth, mock_gql_client, zone):
    with freeze_time(FROZEN_TIME):
        assert zone.status.suspended_until != datetime.max

        # First fetch should query the GraphQL API
        mock_gql_client.get_zone.return_value = deepcopy(zone)
        assert await api.get_zone(zone.id) == zone
        mock_gql_client.get_zone.assert_awaited_once_with(zone.id)

        # Second fetch should also query the GraphQL API
        mock_gql_client.get_zone.reset_mock()
        assert await api.get_zone(zone.id) == zone
        mock_gql_client.get_zone.assert_awaited_once_with(zone.id)

        # Third fetch should not make any calls and instead return cached data
        mock_gql_client.get_zone.reset_mock()
        assert await api.get_zone(zone.id) == zone
        mock_gql_client.get_zone.assert_not_awaited()
        hybrid_auth.get.assert_not_awaited()


async def test_get_sensors(api, hybrid_auth, mock_gql_client, controller, rain_sensor):
    sensor = rain_sensor
    with freeze_time(FROZEN_TIME):
        # First fetch should query the GraphQL API
        mock_gql_client.get_sensors.return_value = [deepcopy(sensor)]
        assert await api.get_sensors(controller) == [sensor]
        mock_gql_client.get_sensors.assert_awaited_once_with(controller)

        # Second fetch should also query the GraphQL API
        mock_gql_client.get_sensors.reset_mock()
        assert await api.get_sensors(controller) == [sensor]
        mock_gql_client.get_sensors.assert_awaited_once_with(controller)

        # Third fetch should not make any calls and instead return cached data
        mock_gql_client.get_sensors.reset_mock()
        assert await api.get_sensors(controller) == [sensor]
        mock_gql_client.get_sensors.assert_not_awaited()
        hybrid_auth.get.assert_not_awaited()
