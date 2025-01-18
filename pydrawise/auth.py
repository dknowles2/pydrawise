"""Authentication support for the Hydrawise v2 GraphQL API."""

from asyncio import Lock
from dataclasses import dataclass
from datetime import datetime, timedelta

import aiohttp

from .base import BaseAuth
from .const import CLIENT_ID, CLIENT_SECRET, TOKEN_URL
from .exceptions import NotAuthorizedError

DEFAULT_TIMEOUT = aiohttp.ClientTimeout(total=60)


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

    def __init__(self, username: str, password: str) -> None:
        """Initializer.

        :param username: The username to use for authenticating with the Hydrawise service.
        :param password: The password to use for authenticating with the Hydrawise service.
        """
        self.__username = username
        self.__password = password
        self._lock = Lock()
        self._token: Token | None = None

    async def _fetch_token_locked(self, refresh=False):
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
        async with aiohttp.ClientSession() as session:
            async with session.post(
                TOKEN_URL,
                headers={"Content-Type": "application/x-www-form-urlencoded"},
                data=data,
                timeout=DEFAULT_TIMEOUT,
            ) as resp:
                resp_json = await resp.json()
                if "error" in resp_json:
                    self._token = None
                    raise NotAuthorizedError(resp_json["message"])
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

    async def check_token(self):
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
