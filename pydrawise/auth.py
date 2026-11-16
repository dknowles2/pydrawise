"""Authentication support for the Hydrawise v2 GraphQL API."""

from asyncio import Lock
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any

import aiohttp

from .base import BaseAuth
from .const import CLIENT_ID, CLIENT_SECRET, REQUEST_TIMEOUT, REST_URL, TOKEN_URL
from .exceptions import APIError, Error, NotAuthorizedError

DEFAULT_TIMEOUT = aiohttp.ClientTimeout(total=60, sock_connect=30)
_INVALID_API_KEY = "API key not valid"


def _redact_api_key(e: aiohttp.ClientResponseError) -> None:
    """Replaces the api_key query parameter in an error's URLs with a placeholder.

    Mutates the error in place. ``aiohttp`` builds its message from
    ``request_info``, so this has to happen before the error is stringified,
    logged, or attached to another exception as ``__cause__``.
    """
    if e.request_info and e.request_info.url:
        e.request_info = e.request_info._replace(
            url=e.request_info.url.with_query({"api_key": "***"}),
            real_url=e.request_info.real_url.with_query({"api_key": "***"}),
        )


@dataclass
class Token:
    """Authentication token."""

    token: str
    refresh: str
    type: str
    expires: datetime

    def __str__(self) -> str:
        return f"{self.type} {self.token}"


class Auth(BaseAuth):
    """Authentication support for the Hydrawise GraphQL API."""

    def __init__(
        self,
        username: str,
        password: str,
        session: aiohttp.ClientSession | None = None,
    ) -> None:
        """Initializer.

        :param username: The username to use for authenticating with the Hydrawise service.
        :param password: The password to use for authenticating with the Hydrawise service.
        :param session: Optional aiohttp ClientSession to use for requests. If not
            provided, a new session is created for each request. It is the
            caller's responsibility to close any session that is passed in.
        """
        self.__username = username
        self.__password = password
        self._lock = Lock()
        self._token: Token | None = None
        self._session = session

    async def _fetch_token_locked(self, refresh: bool = False) -> None:
        data = {
            "client_id": CLIENT_ID,
            "client_secret": CLIENT_SECRET,
        }
        if refresh:
            assert self._token is not None
            data["grant_type"] = "refresh_token"
            data["refresh_token"] = self._token.refresh
        else:
            data["grant_type"] = "password"
            data["scope"] = "all"
            data["username"] = self.__username
            data["password"] = self.__password
        async with (
            self._client_session() as session,
            session.post(
                TOKEN_URL,
                headers={"Content-Type": "application/x-www-form-urlencoded"},
                data=data,
                timeout=DEFAULT_TIMEOUT,
            ) as resp,
        ):
            resp_json = await resp.json()
            if "error" in resp_json:
                self._token = None
                # The service usually includes a human-readable "message", but
                # falls back to the bare "error" code when it doesn't.
                raise NotAuthorizedError(resp_json.get("message", resp_json["error"]))
            self._token = Token(
                token=resp_json["access_token"],
                refresh=resp_json["refresh_token"],
                type=resp_json["token_type"],
                expires=datetime.now() + timedelta(seconds=resp_json["expires_in"]),
            )

    async def check(self) -> bool:
        """Validates that the credentials are valid."""
        await self.check_token()
        return True

    async def check_token(self) -> None:
        """Checks a token and refreshes if necessary."""
        async with self._lock:
            if self._token is None:
                await self._fetch_token_locked(refresh=False)
            elif self._token.expires - datetime.now() < timedelta(minutes=5):
                await self._fetch_token_locked(refresh=True)

    async def token(self) -> str:
        """Retrieves an authentication token for the current user.

        :rtype: string
        """
        await self.check_token()
        async with self._lock:
            return str(self._token)


class RestAuth(BaseAuth):
    """Authentication support for the Hydrawise REST API."""

    def __init__(
        self,
        api_key: str,
        session: aiohttp.ClientSession | None = None,
    ) -> None:
        """Initializer.

        :param api_key: The API key to use for authenticating with the Hydrawise REST service.
        :param session: Optional aiohttp ClientSession to use for requests. If not
            provided, a new session is created for each request. It is the
            caller's responsibility to close any session that is passed in.
        """
        self._api_key = api_key
        self._session = session

    async def get(self, path: str, **kwargs: Any) -> dict:
        """Perform an authenticated GET request and return the JSON response.

        :raises NotAuthorizedError: if the API key was rejected.
        :raises APIError: if the request failed for any other reason.
        """
        url = f"{REST_URL}/{path}"
        params = {"api_key": self._api_key}
        params.update(kwargs)
        try:
            async with (
                self._client_session() as session,
                session.get(url, params=params, timeout=REQUEST_TIMEOUT) as resp,
            ):
                if resp.status == 404 and await resp.text() == _INVALID_API_KEY:
                    raise NotAuthorizedError(_INVALID_API_KEY)
                resp.raise_for_status()
                return await resp.json()
        except Error:
            # Already one of ours; don't re-wrap it below.
            raise
        except aiohttp.ClientResponseError as e:
            # Redact the API key so it can't leak via this message or `__cause__`.
            _redact_api_key(e)
            if e.status == 401:
                # 401 is the only status that unambiguously means the API key was
                # rejected. An invalid key is also reported as a 404 carrying the
                # _INVALID_API_KEY body, which is handled above.
                raise NotAuthorizedError(f"HTTP {e.status}") from e
            # Anything else is a request failure, not a credential problem. In
            # particular the v1 API answers 403 both for transient refusals and
            # for per-controller conditions such as a controller with no serial
            # number attached; neither means the API key is bad. Reporting those
            # as NotAuthorizedError made callers (notably Home Assistant) prompt
            # for reauthentication over a poll that succeeds on the next try.
            raise APIError(f"HTTP {e.status}") from e
        except (aiohttp.ClientError, TimeoutError) as e:
            raise APIError(str(e) or type(e).__name__) from e

    async def check(self) -> bool:
        """Validates that the credentials are valid."""
        await self.get("customerdetails.php")
        return True


class HybridAuth(Auth, RestAuth):
    """Authentication support for the Hydrawise GraphQL & REST APIs."""

    def __init__(
        self,
        username: str,
        password: str,
        api_key: str,
        session: aiohttp.ClientSession | None = None,
    ) -> None:
        """Initializer.

        :param username: The username to use for authenticating with the Hydrawise GraphQL service.
        :param password: The password to use for authenticating with the Hydrawise GraphQL service.
        :param api_key: The API key to use for authenticating with the Hydrawise REST service.
        :param session: Optional aiohttp ClientSession to use for requests. If not
            provided, a new session is created for each request. It is the
            caller's responsibility to close any session that is passed in.
        """
        Auth.__init__(self, username, password, session=session)
        RestAuth.__init__(self, api_key, session=session)

    async def _check_api_token(self) -> None:
        await self.get("customerdetails.php")

    async def check(self) -> bool:
        """Validates that both the GraphQL credentials and the REST API key are valid."""
        await super().check()
        await self._check_api_token()
        return True
