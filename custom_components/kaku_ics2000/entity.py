"""Base entity for ICS-2000 modules."""

from __future__ import annotations

from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .api import Module
from .const import DEVICE_TYPES, DOMAIN, DeviceType
from .coordinator import Ics2000Coordinator


class Ics2000Entity(CoordinatorEntity[Ics2000Coordinator]):
    _attr_has_entity_name = True
    _attr_name = None  # the entity is the device

    def __init__(self, coordinator: Ics2000Coordinator, module: Module) -> None:
        super().__init__(coordinator)
        self.module = module
        self.dtype: DeviceType = DEVICE_TYPES[module.device_type]
        mac = coordinator.client.mac
        self._attr_unique_id = f"{mac}_{module.device_id}"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, f"{mac}_{module.device_id}")},
            name=module.name,
            manufacturer="KlikAanKlikUit",
            model=self.dtype.model,
            via_device_id=coordinator.hub_device_id,
        )

    def _func(self, index: int | None) -> int | None:
        if index is None:
            return None
        funcs = (self.coordinator.data or {}).get(self.module.device_id)
        if not funcs or len(funcs) <= index:
            return None
        return funcs[index]

    async def _set(self, function: int, value: int) -> None:
        await self.coordinator.async_set(self.module.device_id, function, value)


def modules_of_kind(coordinator: Ics2000Coordinator, kind: str) -> list[Module]:
    return [
        m for m in coordinator.modules.values()
        if m.device_type in DEVICE_TYPES and DEVICE_TYPES[m.device_type].kind == kind
    ]
