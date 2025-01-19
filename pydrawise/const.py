"""Constants."""

from aiohttp import ClientTimeout

GRAPHQL_URL = "https://app.hydrawise.com/api/v2/graph"
TOKEN_URL = "https://app.hydrawise.com/api/v2/oauth/access-token"
REST_URL = "https://api.hydrawise.com/api/v1"

CLIENT_ID = "hydrawise_app"
CLIENT_SECRET = "zn3CrjglwNV1"

DEFAULT_APP_ID = "pydrawise"

REQUEST_TIMEOUT = ClientTimeout(total=30)
