"""Authentication support for the Hydrawise v2 GraphQL API."""

import aiohttp
from datetime import datetime, timedelta
import logging
from threading import Lock

from gql import Client
from gql.dsl import DSLField, DSLMutation, DSLQuery, DSLSelectable, dsl_gql
from gql.transport.aiohttp import AIOHTTPTransport, log as gql_log

from .exceptions import MutationError, NotAuthorizedError

# GQL is quite chatty in logs by default.
gql_log.setLevel(logging.ERROR)

CLIENT_ID = "hydrawise_app"
CLIENT_SECRET = "zn3CrjglwNV1"
TOKEN_URL = "https://app.hydrawise.com/api/v2/oauth/access-token"
API_URL = "https://app.hydrawise.com/api/v2/graph"
DEFAULT_TIMEOUT = 60


class Auth:
    def __init__(self, username: str, password: str) -> None:
        self.__username = username
        self.__password = password
        self._lock = Lock()
        self._token: str | None = None
        self._token_type: str | None = None
        self._token_expires: datetime | None = None
        self._refresh_token: str | None = None

    async def _fetch_token_locked(self, refresh=False):
        data = {
            "client_id": CLIENT_ID,
            "client_secret": CLIENT_SECRET,
        }
        if refresh:
            assert self._token is not None
            data["grant_type"] = "refresh_token"
            data["refresh_token"] = self._refresh_token
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
                    self._token_type = None
                    self._token = None
                    self._token_expires = None
                    raise NotAuthorizedError(resp_json["message"])
                self._token = resp_json["access_token"]
                self._refresh_token = self._token["refresh_token"]
                self._token_type = resp_json["token_type"]
                self._token_expires = datetime.now() + timedelta(
                    seconds=resp_json["expires_in"]
                )

    async def check_token(self):
        with self._lock:
            if self._token is None:
                await self._fetch_token_locked(refresh=False)
            elif self._token_expires - datetime.now() < timedelta(minutes=5):
                await self._fetch_token_locked(refresh=True)

    async def token(self) -> str:
        await self.check_token()
        with self._lock:
            return f"{self._token_type} {self._token}"

    async def client(self) -> Client:
        headers = {"Authorization": await self.token()}
        transport = AIOHTTPTransport(url=API_URL, headers=headers)
        return Client(transport=transport, parse_results=True)

    async def query(self, selector: DSLSelectable) -> dict:
        async with await self.client() as session:
            return await session.execute(dsl_gql(DSLQuery(selector)))

    async def mutation(self, selector: DSLField) -> None:
        async with await self.client() as session:
            result = await session.execute(dsl_gql(DSLMutation(selector)))
            resp = result[selector.name]
            if resp["status"] != "OK":
                raise MutationError(resp["summary"])
