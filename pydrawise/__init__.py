"""API for interacting with Hydrawise sprinkler controllers."""

from .auth import Auth
from .base import HydrawiseBase
from .client import Hydrawise
from .diagnostics import REDACTED, redacted_dump
from .exceptions import (
    APIError,
    Error,
    MutationError,
    NotAuthenticatedError,
    NotAuthorizedError,
    NotInitializedError,
    ThrottledError,
    UnknownError,
)
from .schema import Controller, Sensor, User, Zone

__all__ = (
    "REDACTED",
    "APIError",
    "Auth",
    "Controller",
    "Error",
    "Hydrawise",
    "HydrawiseBase",
    "MutationError",
    "NotAuthenticatedError",
    "NotAuthorizedError",
    "NotInitializedError",
    "Sensor",
    "ThrottledError",
    "UnknownError",
    "User",
    "Zone",
    "redacted_dump",
)
