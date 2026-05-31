from datetime import timedelta

import pytest
from aioresponses import aioresponses
from freezegun import freeze_time
from pytest import fixture

from pydrawise import auth
from pydrawise.exceptions import NotAuthorizedError


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


async def test_hybrid_auth_check_validates_rest_api_key(token_payload):
    a = auth.HybridAuth("__username__", "__password__", "__api_key__")
    with aioresponses() as m:
        m.post(auth.TOKEN_URL, status=200, payload=token_payload)
        m.get(
            f"{auth.REST_URL}/customerdetails.php?api_key=__api_key__",
            status=200,
            payload={"customer_id": 123},
        )
        result = await a.check()
    assert result is True


async def test_hybrid_auth_check_raises_on_invalid_rest_api_key(token_payload):
    a = auth.HybridAuth("__username__", "__password__", "__bad_key__")
    with aioresponses() as m:
        m.post(auth.TOKEN_URL, status=200, payload=token_payload)
        m.get(
            f"{auth.REST_URL}/customerdetails.php?api_key=__bad_key__",
            status=404,
            body="API key not valid",
        )
        with pytest.raises(NotAuthorizedError):
            await a.check()
