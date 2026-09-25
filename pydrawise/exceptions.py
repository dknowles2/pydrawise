"""Exceptions used in pydrawise."""


class Error(Exception):
    """Base error class."""


class NotAuthenticatedError(Error):
    """Raised when a request is made to an unauthenticated object."""


class NotAuthorizedError(Error):
    """Raised when invalid credentials are used."""


class NotInitializedError(Error):
    """Raised when the legacy client is not initialized."""


class APIError(Error):
    """Raised when a request to the Hydrawise API fails.

    This covers transient failures such as network errors, timeouts, server
    errors, and GraphQL error responses. The underlying exception is available
    as ``__cause__``.
    """


class MutationError(Error):
    """Raised when there is an error performing a mutation."""


class UnknownError(Error):
    """Raised when an unknown problem occurs."""


class ThrottledError(Error):
    """Raised when a request has been throttled."""
