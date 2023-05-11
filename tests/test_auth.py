from datetime import timedelta

from aioresponses import aioresponses
from freezegun import freeze_time
from pytest import fixture

from pydrawise import auth


@fixture
def token_payload():
    return {
        "access_token": "__access-token__",
        "refresh_token": "__refresh-token__",
        "token_type": "bearer",
        "expires_in": 360,  # 6 minutes
    }


@fixture
def mock_token_fetch(token_payload):
    with aioresponses() as m:
        m.post(
            auth.TOKEN_URL,
            status=200,
            payload=token_payload,
        )
        yield m


async def test_check_token_fetch_and_refresh(token_payload):
    a = auth.Auth("__username__", "__password__")
    with freeze_time("2023-01-01 01:00:00") as t:
        # Initial fetch
        with aioresponses() as m:
            m.post(auth.TOKEN_URL, status=200, payload=token_payload)
            await a.check_token()
            m.assert_called_once_with(
                auth.TOKEN_URL,
                method="POST",
                data={
                    "client_id": auth.CLIENT_ID,
                    "client_secret": auth.CLIENT_SECRET,
                    "grant_type": "password",
                    "scope": "all",
                    "username": "__username__",
                    "password": "__password__",
                },
                headers={"Content-Type": "application/x-www-form-urlencoded"},
                timeout=auth.DEFAULT_TIMEOUT,
            )

        # Token refresh
        t.tick(delta=timedelta(minutes=2))
        with aioresponses() as m:
            m.post(auth.TOKEN_URL, status=200, payload=token_payload)
            await a.check_token()
            m.assert_called_once_with(
                auth.TOKEN_URL,
                method="POST",
                data={
                    "client_id": auth.CLIENT_ID,
                    "client_secret": auth.CLIENT_SECRET,
                    "grant_type": "refresh_token",
                    "refresh_token": "__refresh-token__",
                },
                headers={"Content-Type": "application/x-www-form-urlencoded"},
                timeout=auth.DEFAULT_TIMEOUT,
            )


async def test_token(mock_token_fetch):
    a = auth.Auth("__username__", "__password__")
    token = await a.token()
    assert token == "bearer __access-token__"
