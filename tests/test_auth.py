from datetime import timedelta

import pytest
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


@fixture(autouse=True)
def patch_urls(mock_server, monkeypatch):
    monkeypatch.setattr(auth, "TOKEN_URL", mock_server.url("/oauth/access-token"))
    monkeypatch.setattr(auth, "REST_URL", mock_server.url("/api/v1").rstrip("/"))


@fixture
def mock_token_fetch(mock_server, token_payload):
    mock_server.add("POST", "/oauth/access-token", status=200, payload=token_payload)


async def test_check_token_fetch_and_refresh(mock_server, request_spy, token_payload):
    a = auth.Auth("__username__", "__password__")
    with freeze_time("2023-01-01 01:00:00") as t:
        # Initial fetch
        mock_server.add(
            "POST", "/oauth/access-token", status=200, payload=token_payload
        )
        await a.check_token()
        assert len(request_spy) == 1
        call = request_spy[0]
        assert call.args[0] == "POST"
        assert call.args[1] == auth.TOKEN_URL
        assert call.kwargs["data"] == {
            "client_id": auth.CLIENT_ID,
            "client_secret": auth.CLIENT_SECRET,
            "grant_type": "password",
            "scope": "all",
            "username": "__username__",
            "password": "__password__",
        }
        assert call.kwargs["headers"] == {
            "Content-Type": "application/x-www-form-urlencoded"
        }
        assert call.kwargs["timeout"] == auth.DEFAULT_TIMEOUT

        # Token refresh
        t.tick(delta=timedelta(minutes=2))
        request_spy.clear()
        await a.check_token()
        assert len(request_spy) == 1
        call = request_spy[0]
        assert call.args[0] == "POST"
        assert call.args[1] == auth.TOKEN_URL
        assert call.kwargs["data"] == {
            "client_id": auth.CLIENT_ID,
            "client_secret": auth.CLIENT_SECRET,
            "grant_type": "refresh_token",
            "refresh_token": "__refresh-token__",
        }
        assert call.kwargs["headers"] == {
            "Content-Type": "application/x-www-form-urlencoded"
        }
        assert call.kwargs["timeout"] == auth.DEFAULT_TIMEOUT


async def test_token(mock_token_fetch):
    a = auth.Auth("__username__", "__password__")
    token = await a.token()
    assert token == "bearer __access-token__"


async def test_hybrid_auth_check_validates_rest_api_key(mock_server, token_payload):
    a = auth.HybridAuth("__username__", "__password__", "__api_key__")
    mock_server.add("POST", "/oauth/access-token", status=200, payload=token_payload)
    mock_server.add(
        "GET", "/api/v1/customerdetails.php", status=200, payload={"customer_id": 123}
    )
    result = await a.check()
    assert result is True


async def test_hybrid_auth_check_raises_on_invalid_rest_api_key(
    mock_server, token_payload
):
    a = auth.HybridAuth("__username__", "__password__", "__bad_key__")
    mock_server.add("POST", "/oauth/access-token", status=200, payload=token_payload)
    mock_server.add(
        "GET",
        "/api/v1/customerdetails.php",
        status=404,
        body="API key not valid",
    )
    with pytest.raises(NotAuthorizedError):
        await a.check()
