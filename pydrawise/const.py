"""Constants."""

from aiohttp import ClientTimeout

GRAPHQL_URL = "https://app.hydrawise.com/api/v2/graph"
TOKEN_URL = "https://app.hydrawise.com/api/v2/oauth/access-token"
REST_URL = "https://api.hydrawise.com/api/v1"

CLIENT_ID = "hydrawise_app"
CLIENT_SECRET = "zn3CrjglwNV1"

DEFAULT_APP_ID = "pydrawise"

# Per-request timeouts. These are passed explicitly on every request rather
# than left to whatever the session defaults to, so that a caller-supplied
# session's configuration can't change how long pydrawise is willing to wait.
# sock_connect is pinned alongside total because passing a ClientTimeout
# replaces aiohttp's default object wholesale, which would otherwise drop its
# 30 second connect ceiling and leave a dead peer to consume the total budget.
REQUEST_TIMEOUT = ClientTimeout(total=30, sock_connect=30)

# GraphQL gets a longer budget than REST: the heaviest calls in the library are
# the watering report queries, over a caller-supplied date range.
GRAPHQL_TIMEOUT = ClientTimeout(total=60, sock_connect=30)
