# KlikAanKlikUit ICS-2000 for Home Assistant

Custom integration for the KAKU ICS-2000 hub.

- UI setup: log in with your KlikAanKlikUit account; the hub is found on the LAN automatically.
- Real device state, polled from the Trust cloud (default every 30 s), with optimistic updates after a command.
- Commands go straight to the hub over UDP on the LAN, with the cloud as fallback.
- Plugs -> `switch`, dimmers/dimmable bulbs -> `light` with brightness, Somfy actuators -> `cover`.
- Options: refresh interval, send attempts. Re-authentication and diagnostics download.

Protocol based on [ics-2000-python](https://github.com/zefanjajobse/ics_2000_python).

Tests: `uv run --no-project --with ics-2000-python --with cryptography --with aiohttp --with pytest pytest tests -q`

## Installation

**Marketplace (Home Assistant 2026.11+):** Settings → Marketplace → *Add from link* → `HugoDijkstra/kaku-ics2000` → Install, restart, then add **KlikAanKlikUit ICS-2000** under Settings → Devices & services.

**Manual:** copy `custom_components/kaku_ics2000` into your `/config/custom_components/` and restart.

## Supported devices

| KAKU type | Home Assistant |
|---|---|
| Plugs (APC3-2300R, Zigbee plugs) | `switch` |
| Dimmers, dimmable (Zigbee) bulbs | `light` with brightness |
| Somfy actuators | `cover` (open/close/stop) |

Sensors, remotes and the P1 module are not supported yet.

## License

Apache-2.0. Protocol and device table derived from [ics-2000-python](https://github.com/zefanjajobse/ics_2000_python) (Apache-2.0).
