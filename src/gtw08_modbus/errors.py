"""The errors the library raises itself."""

from __future__ import annotations


class Gtw08Error(Exception):
    """Base class of every error this library raises itself."""


class NoApplianceError(Gtw08Error):
    """The gateway answered, but reports no appliance behind it."""


class GatewayNotReadyError(Gtw08Error):
    """The gateway has not read the appliance's board count yet."""
