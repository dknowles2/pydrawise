"""Structural checks that every client implements exactly the shared interface."""

import inspect

import pytest

from pydrawise.base import HydrawiseBase
from pydrawise.client import Hydrawise
from pydrawise.hybrid import HybridClient
from pydrawise.rest import RestClient

CLIENTS = (Hydrawise, HybridClient, RestClient)


def _public_methods(cls) -> set[str]:
    """Public methods defined on cls itself, ignoring anything inherited."""
    return {
        name
        for name, value in vars(cls).items()
        if not name.startswith("_") and callable(value)
    }


def _interface_methods() -> set[str]:
    return {
        name
        for name, _ in inspect.getmembers(HydrawiseBase, inspect.isfunction)
        if not name.startswith("_")
    }


@pytest.mark.parametrize("cls", CLIENTS, ids=lambda c: c.__name__)
def test_client_implements_every_interface_method(cls):
    """Each client defines every HydrawiseBase method itself.

    Inheriting the abstract method would leave the class uninstantiable, but
    this reports precisely which method is missing rather than failing later
    at construction time.
    """
    assert not _interface_methods() - _public_methods(cls)


@pytest.mark.parametrize("cls", CLIENTS, ids=lambda c: c.__name__)
def test_client_adds_no_methods_outside_the_interface(cls):
    """A client must not grow a public method the interface doesn't declare.

    update_master_valve previously existed only on Hydrawise, so callers using
    any other client had no way to reach it. Adding a method to one client
    without adding it to HydrawiseBase should fail here.
    """
    assert not _public_methods(cls) - _interface_methods()


@pytest.mark.parametrize("cls", CLIENTS, ids=lambda c: c.__name__)
def test_client_signatures_match_the_interface(cls):
    """Parameter names and order must match, so callers can swap clients."""
    for name in _interface_methods():
        want = inspect.signature(getattr(HydrawiseBase, name))
        got = inspect.signature(getattr(cls, name))
        assert list(got.parameters) == list(want.parameters), name
