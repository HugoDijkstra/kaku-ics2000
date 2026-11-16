"""Somfy actuators as covers (no position feedback)."""

from __future__ import annotations

from typing import Any

from homeassistant.components.cover import CoverEntity, CoverEntityFeature
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import Ics2000ConfigEntry
from .entity import Ics2000Entity, modules_of_kind


async def async_setup_entry(
    hass: HomeAssistant, entry: Ics2000ConfigEntry, async_add_entities: AddConfigEntryEntitiesCallback
) -> None:
    coordinator = entry.runtime_data
    async_add_entities(Ics2000Cover(coordinator, m) for m in modules_of_kind(coordinator, "cover"))


class Ics2000Cover(Ics2000Entity, CoverEntity):
    _attr_assumed_state = True
    _attr_is_closed = None
    _attr_supported_features = (
        CoverEntityFeature.OPEN | CoverEntityFeature.CLOSE | CoverEntityFeature.STOP
    )

    async def async_open_cover(self, **kwargs: Any) -> None:
        await self._set(self.dtype.cover_open, 0)

    async def async_close_cover(self, **kwargs: Any) -> None:
        await self._set(self.dtype.cover_close, 0)

    async def async_stop_cover(self, **kwargs: Any) -> None:
        await self._set(self.dtype.cover_stop, 0)
