"""Polls the device statuses of one ICS-2000 home."""

from __future__ import annotations

import logging
import time
from datetime import timedelta

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .api import Ics2000AuthError, Ics2000Client, Ics2000Error, Module
from .const import CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL, DEFAULT_TRIES, CONF_TRIES, DOMAIN

_LOGGER = logging.getLogger(__name__)

HOLD_SECONDS = 15


class Ics2000Coordinator(DataUpdateCoordinator[dict[int, list[int]]]):
    """data = {device_id: [function values]}"""

    config_entry: ConfigEntry

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry, client: Ics2000Client, modules: list[Module]) -> None:
        super().__init__(
            hass,
            _LOGGER,
            config_entry=entry,
            name=DOMAIN,
            update_interval=timedelta(
                seconds=entry.options.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL)
            ),
        )
        self.client = client
        self.modules = {m.device_id: m for m in modules}
        # After a command the cloud status lags a few seconds behind; keep our
        # optimistic value until then so the UI doesn't flip back and forth.
        self._hold_until: dict[int, float] = {}
        self.hub_device_id: str | None = None

    @property
    def tries(self) -> int:
        return int(self.config_entry.options.get(CONF_TRIES, DEFAULT_TRIES))

    async def _async_update_data(self) -> dict[int, list[int]]:
        try:
            statuses = await self.client.get_statuses(list(self.modules))
        except Ics2000AuthError as err:
            raise ConfigEntryAuthFailed(str(err)) from err
        except Ics2000Error as err:
            raise UpdateFailed(str(err)) from err
        now = time.monotonic()
        old = self.data or {}
        for device_id, until in list(self._hold_until.items()):
            if until > now and device_id in old:
                statuses[device_id] = old[device_id]
            elif until <= now:
                del self._hold_until[device_id]
        # Keep the last known values for modules the cloud didn't return.
        return {**old, **statuses}

    async def async_set(self, device_id: int, function: int, value: int) -> None:
        """Send a command and update our local copy straight away (optimistic)."""
        await self.client.set_function(device_id, function, value, tries=self.tries)
        funcs = list((self.data or {}).get(device_id, []))
        if len(funcs) <= function:
            funcs.extend([0] * (function + 1 - len(funcs)))
        funcs[function] = value
        self._hold_until[device_id] = time.monotonic() + HOLD_SECONDS
        self.async_set_updated_data({**(self.data or {}), device_id: funcs})
