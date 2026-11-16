"""Dimmers and dimmable bulbs as lights."""

from __future__ import annotations

from typing import Any

from homeassistant.components.light import ATTR_BRIGHTNESS, ColorMode, LightEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import Ics2000ConfigEntry
from .entity import Ics2000Entity, modules_of_kind


async def async_setup_entry(
    hass: HomeAssistant, entry: Ics2000ConfigEntry, async_add_entities: AddConfigEntryEntitiesCallback
) -> None:
    coordinator = entry.runtime_data
    async_add_entities(Ics2000Light(coordinator, m) for m in modules_of_kind(coordinator, "light"))


class Ics2000Light(Ics2000Entity, LightEntity):
    _attr_color_mode = ColorMode.BRIGHTNESS
    _attr_supported_color_modes = {ColorMode.BRIGHTNESS}

    @property
    def is_on(self) -> bool | None:
        value = self._func(self.dtype.on_off)
        return None if value is None else value > 0

    @property
    def brightness(self) -> int | None:
        level = self._func(self.dtype.dim)
        if level is None:
            return None
        return max(1, min(255, round(level * 255 / self.dtype.max_brightness)))

    async def async_turn_on(self, **kwargs: Any) -> None:
        if ATTR_BRIGHTNESS in kwargs and self.dtype.dim is not None:
            level = max(1, round(kwargs[ATTR_BRIGHTNESS] * self.dtype.max_brightness / 255))
            if not self.is_on:
                await self._set(self.dtype.on_off, 1)
            await self._set(self.dtype.dim, level)
        else:
            await self._set(self.dtype.on_off, 1)

    async def async_turn_off(self, **kwargs: Any) -> None:
        await self._set(self.dtype.on_off, 0)
