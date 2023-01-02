"""API for interacting with Hydrawise sprinkler controllers."""

from .auth import Auth
from .client import Hydrawise
from .exceptions import (
    Error,
    NotAuthenticatedError,
    NotAuthorizedError,
    MutationError,
    UnknownError,
)
from .schema import Controller, Sensor, User, Zone

__all__ = (
    "Auth",
    "Controller",
    "Error",
    "Hydrawise",
    "MutationError",
    "NotAuthenticatedError",
    "NotAuthorizedError",
    "Sensor",
    "UnknownError",
    "User",
    "Zone",
)
