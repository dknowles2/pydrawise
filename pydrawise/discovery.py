"""Helpers for identifying Hydrawise controllers found on a local network.

Hydrawise controllers have no local API: they talk only to Hydrawise's cloud
service, and every TCP port on them is closed. There is therefore nothing to
discover *from* a controller directly. What a controller does leak is its
identity, through the DHCP request it makes when it joins a network:

* It requests a hostname of the form ``hydrawise-<last two MAC bytes>``,
  e.g. ``hydrawise-6090`` for a controller whose MAC ends in ``60:90``.
* Its MAC sits in the ``60:8A:10`` OUI, which belongs to Microchip Technology
  (the vendor of the controller's WiFi module, not of the controller).
* Its serial number -- the only hardware identifier the Hydrawise API
  exposes -- ends in the last four bytes of its MAC. One observed controller
  had MAC ``60:8a:10:b3:60:90`` and serial number ``0310b36090``; the leading
  ``03`` is presumed to be a model or product code.

That is enough for a passive DHCP watcher (such as Home Assistant's) to spot a
controller joining the network and tie it back to a controller in the user's
Hydrawise account, without probing anything. The functions here deliberately
match on the trailing bytes shared by the MAC and the serial number rather than
reconstructing one from the other, so they don't depend on the ``03`` prefix or
on the OUI staying the same across hardware revisions.
"""

import logging
import re
from collections.abc import Iterable

from .schema import Controller

_LOGGER = logging.getLogger("pydrawise")

#: Pattern matching the DHCP hostname a controller requests, in the glob syntax
#: used by Home Assistant's ``dhcp`` manifest key.
DHCP_HOSTNAME_PATTERN = "hydrawise-*"

#: Organizationally Unique Identifier of a controller's MAC address, lowercase
#: and without separators. Registered to Microchip Technology, which supplies
#: the WiFi module, so this is shared with unrelated devices and is only useful
#: alongside
#: [DHCP_HOSTNAME_PATTERN][pydrawise.discovery.DHCP_HOSTNAME_PATTERN].
MAC_OUI = "608a10"

_HOSTNAME_RE = re.compile(r"hydrawise-([0-9a-f]{4})\Z", re.IGNORECASE)
_MAC_RE = re.compile(r"\A[0-9a-f]{12}\Z")

# Number of trailing hex digits a controller's MAC address and serial number
# have in common: the last four bytes of the MAC.
_SHARED_DIGITS = 8

# Number of trailing hex digits of the MAC address that appear in the DHCP
# hostname: the last two bytes.
_HOSTNAME_DIGITS = 4


def normalize_mac(mac: str) -> str:
    """Normalizes a MAC address to lowercase hex digits with no separators.

    :param mac: A MAC address, with or without ``:``, ``-`` or ``.``
        separators.
    :raises ValueError: If ``mac`` is not a 48-bit MAC address.
    :return: The twelve hex digits of the MAC address, lowercased.
    """
    normalized = mac.replace(":", "").replace("-", "").replace(".", "").lower()
    if not _MAC_RE.match(normalized):
        raise ValueError(f"not a MAC address: {mac!r}")
    return normalized


def is_hydrawise_mac(mac: str) -> bool:
    """Whether a MAC address could belong to a Hydrawise controller.

    This only checks the OUI, which the controller shares with every other
    device using the same WiFi module, so a true result is weak evidence on its
    own. Pair it with a
    [DHCP_HOSTNAME_PATTERN][pydrawise.discovery.DHCP_HOSTNAME_PATTERN] match.

    :param mac: A MAC address, with or without separators.
    :raises ValueError: If ``mac`` is not a 48-bit MAC address.
    """
    return normalize_mac(mac).startswith(MAC_OUI)


def serial_matches_mac(serial_number: str, mac: str) -> bool:
    """Whether a controller's serial number and a MAC address identify one device.

    :param serial_number: A controller's serial number, as reported by
        [ControllerHardware.serial_number][pydrawise.schema.ControllerHardware].
    :param mac: A MAC address, with or without separators.
    :raises ValueError: If ``mac`` is not a 48-bit MAC address.
    """
    if len(serial_number) < _SHARED_DIGITS:
        return False
    return (
        serial_number.lower()[-_SHARED_DIGITS:] == normalize_mac(mac)[-_SHARED_DIGITS:]
    )


def serial_matches_hostname(serial_number: str, hostname: str) -> bool:
    """Whether a controller's serial number and a DHCP hostname identify one device.

    A hostname carries only the last two bytes of the controller's MAC address,
    so this is a weaker match than
    [serial_matches_mac][pydrawise.discovery.serial_matches_mac] and can
    collide. Prefer the MAC when a discovery mechanism reports one.

    :param serial_number: A controller's serial number, as reported by
        [ControllerHardware.serial_number][pydrawise.schema.ControllerHardware].
    :param hostname: A hostname, which need not be a Hydrawise one. A trailing
        domain, if any, is ignored.
    """
    if (match := _HOSTNAME_RE.match(hostname.split(".")[0])) is None:
        return False
    if len(serial_number) < _HOSTNAME_DIGITS:
        return False
    return serial_number.lower()[-_HOSTNAME_DIGITS:] == match.group(1).lower()


def find_controller(
    controllers: Iterable[Controller],
    *,
    mac: str | None = None,
    hostname: str | None = None,
) -> Controller | None:
    """Finds the controller a discovered device corresponds to.

    At least one of ``mac`` or ``hostname`` must be given; when both are, a
    controller has to match both.

    :param controllers: Controllers to search, e.g. the result of
        [HydrawiseBase.get_controllers][pydrawise.base.HydrawiseBase.get_controllers].
    :param mac: MAC address of the discovered device, with or without
        separators.
    :param hostname: Hostname the discovered device requested.
    :raises ValueError: If neither ``mac`` nor ``hostname`` is given, or if
        ``mac`` is not a 48-bit MAC address.
    :return: The matching controller, or ``None`` if no controller matches or
        more than one does.
    """
    if mac is None and hostname is None:
        raise ValueError("one of mac or hostname is required")

    matches = [
        controller
        for controller in controllers
        if (mac is None or serial_matches_mac(controller.hardware.serial_number, mac))
        and (
            hostname is None
            or serial_matches_hostname(controller.hardware.serial_number, hostname)
        )
    ]
    if not matches:
        return None
    if len(matches) > 1:
        _LOGGER.warning(
            "Ignoring ambiguous discovery of mac=%r hostname=%r:"
            " matched %d controllers",
            mac,
            hostname,
            len(matches),
        )
        return None
    return matches[0]
