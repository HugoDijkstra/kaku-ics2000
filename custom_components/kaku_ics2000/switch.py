"""On/off modules (plugs) as switches."""

from __future__ import annotations

from typing import Any

from homeassistant.components.switch import SwitchDeviceClass, SwitchEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import Ics2000ConfigEntry
from .entity import Ics2000Entity, modules_of_kind


async def async_setup_entry(
    hass: HomeAssistant, entry: Ics2000ConfigEntry, async_add_entities: AddConfigEntryEntitiesCallback
) -> None:
    coordinator = entry.runtime_data
    async_add_entities(Ics2000Switch(coordinator, m) for m in modules_of_kind(coordinator, "switch"))


class Ics2000Switch(Ics2000Entity, SwitchEntity):
    _attr_device_class = SwitchDeviceClass.OUTLET

    @property
    def is_on(self) -> bool | None:
        value = self._func(self.dtype.on_off)
        return None if value is None else value > 0

    async def async_turn_on(self, **kwargs: Any) -> None:
        await self._set(self.dtype.on_off, 1)

    async def async_turn_off(self, **kwargs: Any) -> None:
        await self._set(self.dtype.on_off, 0)
