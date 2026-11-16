"""Constants for the KlikAanKlikUit ICS-2000 integration."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Final

DOMAIN: Final = "kaku_ics2000"

CONF_HOME_ID: Final = "home_id"
CONF_MAC: Final = "mac"
CONF_AES_KEY: Final = "aes_key"
CONF_TRIES: Final = "tries"
CONF_SCAN_INTERVAL: Final = "scan_interval"

DEFAULT_TRIES: Final = 2
DEFAULT_SCAN_INTERVAL: Final = 30  # seconds
MIN_SCAN_INTERVAL: Final = 10

API_URL: Final = "https://trustsmartcloud2.com/ics2000_api"
HUB_PORT: Final = 2012


@dataclass(frozen=True, slots=True)
class DeviceType:
    """What a KAKU device type can do, and at which function index."""

    model: str
    kind: str  # "switch" | "light" | "cover" | "unsupported"
    on_off: int | None = None
    dim: int | None = None
    max_brightness: int = 255
    cover_open: int | None = None
    cover_stop: int | None = None
    cover_close: int | None = None


# Based on the device table of ics-2000-python (zefanjajobse/ics_2000_python).
DEVICE_TYPES: Final[dict[int, DeviceType]] = {
    1: DeviceType("APC3-2300R smart plug", "switch", on_off=0),
    2: DeviceType("Dimmer", "light", on_off=0, dim=1, max_brightness=15),
    23: DeviceType("Somfy actuator", "cover", cover_open=0, cover_stop=1, cover_close=2),
    24: DeviceType("Dimmable lightbulb", "light", on_off=0, dim=1, max_brightness=15),
    33: DeviceType("Zigbee smart plug", "switch", on_off=3),
    34: DeviceType("Zigbee dimmer", "light", on_off=3, dim=4),
    36: DeviceType("Zigbee dimmable light (CT)", "light", on_off=3, dim=4),
    40: DeviceType("Zigbee dimmable lightbulb", "light", on_off=3, dim=4),
    41: DeviceType("Zigbee smart plug", "switch", on_off=3),
    48: DeviceType("Group with dimmable lightbulb", "light", on_off=3, dim=4),
}

# Sensors, remotes and system modules: listed so we can name them in logs,
# but no entities are created for them.
UNSUPPORTED_NAMES: Final[dict[int, str]] = {
    3: "Actuator", 4: "Outdoor motion detector", 5: "Contact sensor",
    6: "Doorbell", 7: "1-channel wall control", 8: "2-channel wall control",
    9: "1-channel remote", 10: "2-channel remote", 11: "3-channel remote",
    12: "16-channel remote", 13: "Wall remote", 14: "Light sensor",
    15: "Dusk sensor", 16: "ARC remote", 17: "ARC contact sensor",
    18: "ARC motion sensor", 19: "ARC smoke sensor", 20: "ARC siren",
    21: "Doorbell", 22: "Built-in wall switch", 25: "1-button wall switch",
    26: "2-button wall switch", 27: "BREL actuator", 28: "Contact sensor",
    29: "Keychain remote", 30: "Action button", 31: "Rotary dimmer",
    32: "Zigbee device", 35: "Zigbee RGB light", 37: "Zigbee multi dimmer",
    38: "Zigbee lock", 39: "Zigbee remote", 42: "Leak sensor",
    43: "Smoke detector", 44: "CO sensor", 45: "Temp/humidity sensor",
    46: "Zigbee light group", 47: "Fire sensor", 238: "P1 module",
    240: "Alarm module", 241: "IP camera module", 242: "Geofencing module",
    243: "System module",
}
