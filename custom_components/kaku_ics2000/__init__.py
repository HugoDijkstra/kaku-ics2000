"""KlikAanKlikUit ICS-2000 integration."""

from __future__ import annotations

import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_EMAIL, CONF_HOST, CONF_PASSWORD, Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed, ConfigEntryNotReady
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .api import Ics2000AuthError, Ics2000Client, Ics2000Error
from .discovery import async_discover
from .const import CONF_AES_KEY, CONF_HOME_ID, CONF_MAC, DEVICE_TYPES, DOMAIN, UNSUPPORTED_NAMES
from .coordinator import Ics2000Coordinator

_LOGGER = logging.getLogger(__name__)

PLATFORMS = [Platform.COVER, Platform.LIGHT, Platform.SWITCH]

type Ics2000ConfigEntry = ConfigEntry[Ics2000Coordinator]


async def async_setup_entry(hass: HomeAssistant, entry: Ics2000ConfigEntry) -> bool:
    data = entry.data
    client = Ics2000Client(
        async_get_clientsession(hass),
        data[CONF_EMAIL],
        data[CONF_PASSWORD],
        home_id=data[CONF_HOME_ID],
        mac=data[CONF_MAC],
        aes_key=data[CONF_AES_KEY],
        host=data.get(CONF_HOST),
    )

    try:
        modules = await client.get_modules()
    except Ics2000AuthError as err:
        raise ConfigEntryAuthFailed(str(err)) from err
    except Ics2000Error as err:
        raise ConfigEntryNotReady(str(err)) from err

    # The hub may have a new IP address since setup: look for it again.
    found = await async_discover(hass, timeout=2)
    if client.mac in found and found[client.mac] != client.host:
        _LOGGER.info("ICS-2000 found at %s", found[client.mac])
        client.host = found[client.mac]
        hass.config_entries.async_update_entry(entry, data={**data, CONF_HOST: client.host})

    for m in modules:
        if m.device_type not in DEVICE_TYPES:
            _LOGGER.debug(
                "Skipping '%s' (type %s: %s)",
                m.name, m.device_type, UNSUPPORTED_NAMES.get(m.device_type, "unknown"),
            )

    coordinator = Ics2000Coordinator(hass, entry, client, modules)
    await coordinator.async_config_entry_first_refresh()
    entry.runtime_data = coordinator

    hub = dr.async_get(hass).async_get_or_create(
        config_entry_id=entry.entry_id,
        identifiers={(DOMAIN, client.mac)},
        connections={(dr.CONNECTION_NETWORK_MAC, ":".join(client.mac[i:i + 2] for i in range(0, 12, 2)))},
        manufacturer="KlikAanKlikUit",
        model="ICS-2000",
        name=entry.title,
    )
    coordinator.hub_device_id = hub.id

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    entry.async_on_unload(entry.add_update_listener(_async_reload))
    return True


async def _async_reload(hass: HomeAssistant, entry: Ics2000ConfigEntry) -> None:
    await hass.config_entries.async_reload(entry.entry_id)


async def async_unload_entry(hass: HomeAssistant, entry: Ics2000ConfigEntry) -> bool:
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
