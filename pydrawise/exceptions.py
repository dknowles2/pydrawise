"""Exceptions used in pydrawise."""


class Error(Exception):
    """Base error class."""


class NotAuthenticatedError(Error):
    """Raised when a request is made to an unauthenticated object."""


class NotAuthorizedError(Error):
    """Raised when invalid credentials are used.

    This is deliberately narrow, because callers tend to react to it by
    re-prompting the user for credentials. The REST v1 API in particular
    answers HTTP 403 for transient refusals and for per-controller conditions
    that have nothing to do with the API key, so those raise `APIError`.
    """


class NotInitializedError(Error):
    """Raised when the legacy client is not initialized."""


class APIError(Error):
    """Raised when a request to the Hydrawise API fails.

    This covers usually-transient failures such as network errors, timeouts,
    server errors, GraphQL error responses, and HTTP errors from the REST v1
    API that don't mean the API key was rejected. Callers should retry rather
    than treat it as a credential problem. The underlying exception is
    available as ``__cause__``.
    """


class MutationError(Error):
    """Raised when there is an error performing a mutation."""


class UnknownError(Error):
    """Raised when an unknown problem occurs."""


class ThrottledError(Error):
    """Raised when a request has been throttled."""
