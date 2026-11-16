from datetime import timedelta

import pytest
from aiohttp import ClientError, ClientResponseError, ClientSession, ClientTimeout
from freezegun import freeze_time
from pytest import fixture

from pydrawise import auth
from pydrawise.exceptions import APIError, Error, NotAuthorizedError


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


async def test_token_fetch_error_uses_message(mock_server):
    """An error response's human-readable message becomes the exception text."""
    a = auth.Auth("__username__", "__bad_password__")
    mock_server.add(
        "POST",
        "/oauth/access-token",
        status=400,
        payload={"error": "invalid_grant", "message": "Bad credentials"},
    )
    with pytest.raises(NotAuthorizedError, match="Bad credentials"):
        await a.check_token()


async def test_token_fetch_error_without_message_falls_back_to_error_code(mock_server):
    """Not every error response carries a "message"; the error code is used instead."""
    a = auth.Auth("__username__", "__bad_password__")
    mock_server.add(
        "POST",
        "/oauth/access-token",
        status=400,
        payload={"error": "invalid_grant"},
    )
    with pytest.raises(NotAuthorizedError, match="invalid_grant"):
        await a.check_token()


async def test_token_fetch_error_clears_any_existing_token(mock_server, token_payload):
    """A failed refresh must not leave a stale token behind."""
    a = auth.Auth("__username__", "__password__")
    with freeze_time("2023-01-01 01:00:00") as t:
        mock_server.add(
            "POST", "/oauth/access-token", status=200, payload=token_payload
        )
        await a.check_token()
        assert a._token is not None

        # Advance past the refresh window so the next check refreshes.
        t.tick(timedelta(minutes=2))
        mock_server.add(
            "POST",
            "/oauth/access-token",
            status=400,
            payload={"error": "invalid_grant", "message": "Refresh rejected"},
        )
        with pytest.raises(NotAuthorizedError):
            await a.check_token()
        assert a._token is None


async def test_rest_auth_check_validates_the_api_key(mock_server, request_spy):
    a = auth.RestAuth("__api_key__")
    mock_server.add(
        "GET", "/api/v1/customerdetails.php", status=200, payload={"customer_id": 123}
    )
    assert await a.check() is True
    [call] = request_spy
    assert call.kwargs["params"]["api_key"] == "__api_key__"


async def test_rest_auth_check_raises_on_invalid_api_key(mock_server):
    a = auth.RestAuth("__bad_key__")
    mock_server.add(
        "GET", "/api/v1/customerdetails.php", status=404, body="API key not valid"
    )
    with pytest.raises(NotAuthorizedError, match="API key not valid"):
        await a.check()


async def test_rest_auth_raises_api_error_for_other_http_errors(mock_server):
    """A non-404 failure is a request failure, not a bad API key."""
    a = auth.RestAuth("__api_key__")
    mock_server.add("GET", "/api/v1/customerdetails.php", status=500, body="boom")
    with pytest.raises(APIError, match="HTTP 500") as exc_info:
        await a.check()
    assert isinstance(exc_info.value.__cause__, ClientResponseError)


async def test_rest_auth_raises_not_authorized_on_401(mock_server):
    """401 is the one status that means the API key itself was rejected."""
    a = auth.RestAuth("__api_key__")
    mock_server.add(
        "GET", "/api/v1/customerdetails.php", status=401, body="Unauthorized"
    )
    with pytest.raises(NotAuthorizedError, match="HTTP 401"):
        await a.check()


async def test_rest_auth_raises_api_error_on_403(mock_server):
    """A 403 is transient or controller-specific; it must not trigger reauth.

    See home-assistant/core#192025: mapping this to NotAuthorizedError made
    Home Assistant start a reauthentication flow over a poll that succeeded
    again minutes later with the same credentials.
    """
    a = auth.RestAuth("__api_key__")
    mock_server.add("GET", "/api/v1/customerdetails.php", status=403, body="Forbidden")
    with pytest.raises(APIError, match="HTTP 403"):
        await a.check()


async def test_rest_auth_raises_api_error_on_connection_error(monkeypatch):
    """A transport failure surfaces as APIError, not a bare aiohttp error."""
    # Nothing is listening on port 1, so the connection is refused immediately.
    monkeypatch.setattr(auth, "REST_URL", "http://127.0.0.1:1/api/v1")
    a = auth.RestAuth("__api_key__")
    with pytest.raises(APIError) as exc_info:
        await a.check()
    assert isinstance(exc_info.value.__cause__, ClientError)


async def test_rest_auth_raises_api_error_on_timeout(mock_server, monkeypatch):
    """A timeout surfaces as APIError with a non-empty message."""
    monkeypatch.setattr(auth, "REQUEST_TIMEOUT", ClientTimeout(total=0.05))
    a = auth.RestAuth("__api_key__")
    mock_server.add("GET", "/api/v1/customerdetails.php", payload={}, delay=1)
    with pytest.raises(APIError) as exc_info:
        await a.check()
    # TimeoutError stringifies to "", so the type name stands in for it.
    assert str(exc_info.value)


@pytest.mark.parametrize("status", [401, 403, 500])
async def test_rest_auth_redacts_api_key_on_http_errors(mock_server, status):
    a = auth.RestAuth("__secret_api_key__")
    mock_server.add("GET", "/api/v1/customerdetails.php", status=status, body="boom")
    with pytest.raises(Error) as exc_info:
        await a.check()

    for text in (str(exc_info.value), str(exc_info.value.__cause__)):
        assert "__secret_api_key__" not in text
    assert "api_key=***" in str(exc_info.value.__cause__)


async def test_auth_owns_its_sessions_by_default(mock_token_fetch):
    """With no session passed in, each request gets an ephemeral one."""
    a = auth.Auth("__username__", "__password__")
    assert a.session is None
    assert await a.check() is True


async def test_auth_uses_injected_session(
    mock_token_fetch, client_session: ClientSession, session_spy
):
    """A caller-supplied session is used for the token fetch and left open."""
    calls = session_spy(client_session)
    a = auth.Auth("__username__", "__password__", session=client_session)
    assert a.session is client_session
    await a.check_token()
    assert len(calls) == 1
    assert calls[0].args == ("POST", auth.TOKEN_URL)
    assert not client_session.closed


async def test_rest_auth_uses_injected_session(
    mock_server, client_session: ClientSession, session_spy
):
    """A caller-supplied session is used for REST requests and left open."""
    calls = session_spy(client_session)
    a = auth.RestAuth("__api_key__", session=client_session)
    assert a.session is client_session
    mock_server.add(
        "GET", "/api/v1/customerdetails.php", status=200, payload={"customer_id": 123}
    )
    assert await a.check() is True
    assert len(calls) == 1
    assert calls[0].args[0] == "GET"
    assert not client_session.closed


async def test_hybrid_auth_injected_session_covers_both_apis(
    mock_server, token_payload, client_session: ClientSession, session_spy
):
    """One session passed to HybridAuth serves both the GraphQL and REST halves."""
    calls = session_spy(client_session)
    a = auth.HybridAuth(
        "__username__", "__password__", "__api_key__", session=client_session
    )
    assert a.session is client_session
    mock_server.add("POST", "/oauth/access-token", status=200, payload=token_payload)
    mock_server.add(
        "GET", "/api/v1/customerdetails.php", status=200, payload={"customer_id": 123}
    )
    assert await a.check() is True
    assert [call.args[0] for call in calls] == ["POST", "GET"]
    assert not client_session.closed


async def test_pinned_timeouts_cap_connect_separately():
    """Passing a ClientTimeout drops aiohttp's own connect ceiling, so pin it."""
    for timeout in (auth.DEFAULT_TIMEOUT, auth.REQUEST_TIMEOUT):
        assert timeout.total is not None
        assert timeout.sock_connect is not None
        assert timeout.sock_connect <= timeout.total
