"""Find the hub on the networks Home Assistant is connected to."""

from __future__ import annotations

from homeassistant.components import network
from homeassistant.core import HomeAssistant

from .api import discover_hubs, subnet_hosts


async def async_discover(hass: HomeAssistant, timeout: float = 3.0) -> dict[str, str]:
    nets: list[str] = []
    for adapter in await network.async_get_adapters(hass):
        if not adapter["enabled"]:
            continue
        for ip in adapter["ipv4"]:
            nets.append(f"{ip['address']}/{ip['network_prefix']}")
    try:
        return await discover_hubs(timeout=timeout, extra_targets=subnet_hosts(nets))
    except OSError:
        return {}
