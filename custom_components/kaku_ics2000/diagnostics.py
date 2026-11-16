"""Diagnostics download (secrets redacted)."""

from __future__ import annotations

from typing import Any

from homeassistant.components.diagnostics import async_redact_data
from homeassistant.const import CONF_EMAIL, CONF_PASSWORD
from homeassistant.core import HomeAssistant

from . import Ics2000ConfigEntry
from .const import CONF_AES_KEY, DEVICE_TYPES, UNSUPPORTED_NAMES

TO_REDACT = {CONF_EMAIL, CONF_PASSWORD, CONF_AES_KEY}


async def async_get_config_entry_diagnostics(hass: HomeAssistant, entry: Ics2000ConfigEntry) -> dict[str, Any]:
    coordinator = entry.runtime_data
    return {
        "entry": async_redact_data(dict(entry.data), TO_REDACT),
        "options": dict(entry.options),
        "modules": [
            {
                "id": m.device_id,
                "name": m.name,
                "type": m.device_type,
                "supported_as": DEVICE_TYPES[m.device_type].kind if m.device_type in DEVICE_TYPES else None,
                "type_name": (
                    DEVICE_TYPES[m.device_type].model if m.device_type in DEVICE_TYPES
                    else UNSUPPORTED_NAMES.get(m.device_type, "unknown")
                ),
                "functions": (coordinator.data or {}).get(m.device_id),
                "raw": m.raw,
            }
            for m in coordinator.modules.values()
        ],
    }
