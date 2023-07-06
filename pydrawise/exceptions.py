"""Exceptions used in pydrawise."""


class Error(Exception):
    """Base error class."""


class NotAuthenticatedError(Error):
    """Raised when a request is made to an unathenticated object."""


class NotAuthorizedError(Error):
    """Raised when invalid credentials are used."""


class NotInitializedError(Error):
    """Raised when the legacy client is not initialized."""


class MutationError(Error):
    """Raised when there is an error performing a mutation."""


class UnknownError(Error):
    """Raised when an unknown problem occurs."""
