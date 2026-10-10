import logging

import pytest

from pydrawise.discovery import (
    MAC_OUI,
    find_controller,
    is_hydrawise_mac,
    normalize_mac,
    serial_matches_hostname,
    serial_matches_mac,
)
from pydrawise.schema import Controller, ControllerHardware

# The one controller these helpers were derived from.
MAC = "60:8a:10:b3:60:90"
SERIAL = "0310b36090"
HOSTNAME = "hydrawise-6090"


def controller(serial_number: str, id: int = 1) -> Controller:
    return Controller(
        id=id,
        name=f"Controller {id}",
        hardware=ControllerHardware(serial_number=serial_number),
    )


@pytest.mark.parametrize(
    "mac",
    [
        "608a10b36090",
        "60:8a:10:b3:60:90",
        "60-8A-10-B3-60-90",
        "608a.10b3.6090",
        "60:8A:10:B3:60:90",
    ],
)
def test_normalize_mac(mac):
    assert normalize_mac(mac) == "608a10b36090"


@pytest.mark.parametrize(
    "mac",
    [
        "",
        "608a10b360",  # too short
        "608a10b3609012",  # too long
        "608a10b3609z",  # not hex
        "60:8a:10:b3:60",
        "hydrawise-6090",
    ],
)
def test_normalize_mac_invalid(mac):
    with pytest.raises(ValueError, match="not a MAC address"):
        normalize_mac(mac)


def test_is_hydrawise_mac():
    assert is_hydrawise_mac(MAC)
    assert is_hydrawise_mac(MAC_OUI + "000000")
    assert not is_hydrawise_mac("aa:bb:cc:b3:60:90")


def test_serial_matches_mac():
    assert serial_matches_mac(SERIAL, MAC)
    assert serial_matches_mac(SERIAL.upper(), "608a10b36090")
    # Only the trailing four bytes matter: a different leading product code or
    # OUI still identifies the same device.
    assert serial_matches_mac("9910b36090", MAC)
    assert serial_matches_mac(SERIAL, "aa:bb:10:b3:60:90")


def test_serial_matches_mac_mismatch():
    assert not serial_matches_mac("0310b36091", MAC)
    assert not serial_matches_mac("03b36090", MAC)  # right tail, wrong byte
    assert not serial_matches_mac("", MAC)
    assert not serial_matches_mac("6090", MAC)  # too short to compare


def test_serial_matches_mac_invalid_mac():
    with pytest.raises(ValueError, match="not a MAC address"):
        serial_matches_mac(SERIAL, "not-a-mac")


def test_serial_matches_hostname():
    assert serial_matches_hostname(SERIAL, HOSTNAME)
    assert serial_matches_hostname(SERIAL.upper(), "HYDRAWISE-6090")
    assert serial_matches_hostname(SERIAL, "hydrawise-6090.lan")


def test_serial_matches_hostname_mismatch():
    assert not serial_matches_hostname("0310b36091", HOSTNAME)
    assert not serial_matches_hostname("", HOSTNAME)
    assert not serial_matches_hostname("090", HOSTNAME)  # too short to compare


@pytest.mark.parametrize(
    "hostname",
    [
        "",
        "hydrawise",
        "hydrawise-",
        "hydrawise-609",  # too few digits
        "hydrawise-60900",  # too many digits
        "hydrawise-609z",  # not hex
        "my-hydrawise-6090",
        "0310b36090",
    ],
)
def test_serial_matches_hostname_not_hydrawise(hostname):
    assert not serial_matches_hostname(SERIAL, hostname)


def test_find_controller_by_mac():
    want = controller(SERIAL)
    controllers = [controller("0310aabbccdd", id=2), want]
    assert find_controller(controllers, mac=MAC) is want


def test_find_controller_by_hostname():
    want = controller(SERIAL)
    controllers = [controller("0310aabbccdd", id=2), want]
    assert find_controller(controllers, hostname=HOSTNAME) is want


def test_find_controller_by_mac_and_hostname():
    want = controller(SERIAL)
    assert find_controller([want], mac=MAC, hostname=HOSTNAME) is want
    # Both have to match.
    assert find_controller([want], mac=MAC, hostname="hydrawise-1234") is None
    assert find_controller([want], mac="aa:bb:cc:dd:60:90", hostname=HOSTNAME) is None


def test_find_controller_no_match():
    assert find_controller([], mac=MAC) is None
    assert find_controller([controller("0310aabbccdd")], mac=MAC) is None


def test_find_controller_ambiguous(caplog):
    # Two controllers whose serial numbers share a hostname suffix.
    controllers = [controller("0310aabb6090", id=1), controller(SERIAL, id=2)]
    with caplog.at_level(logging.WARNING, logger="pydrawise"):
        assert find_controller(controllers, hostname=HOSTNAME) is None
    assert "ambiguous" in caplog.text
    # The MAC disambiguates them.
    found = find_controller(controllers, mac=MAC)
    assert found is not None
    assert found.id == 2


def test_find_controller_requires_an_identifier():
    with pytest.raises(ValueError, match="one of mac or hostname is required"):
        find_controller([controller(SERIAL)])
