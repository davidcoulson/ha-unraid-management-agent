"""Base entity classes for Unraid Management Agent."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

from homeassistant.const import CONF_HOST
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity import EntityDescription
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN, MANUFACTURER

if TYPE_CHECKING:
    from .coordinator import UnraidDataUpdateCoordinator


@dataclass(frozen=True, kw_only=True)
class UnraidEntityDescription(EntityDescription):
    """Base description for all Unraid entities."""

    available_fn: Callable[[UnraidDataUpdateCoordinator], bool] = lambda _: True
    supported_fn: Callable[[UnraidDataUpdateCoordinator], bool] = lambda _: True


class UnraidBaseEntity(CoordinatorEntity["UnraidDataUpdateCoordinator"]):
    """Base entity for Unraid Management Agent."""

    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: UnraidDataUpdateCoordinator,
        key: str,
    ) -> None:
        """Initialize the entity."""
        super().__init__(coordinator)
        self._attr_unique_id = f"{coordinator.config_entry.entry_id}_{key}"
        self._attr_device_info = self._build_device_info()

    def _build_device_info(self) -> DeviceInfo:
        """Build device info for this entity."""
        data = self.coordinator.data
        system = data.system if data else None

        hostname = "Unraid"
        version = "Unknown"
        agent_version = None
        host = self.coordinator.config_entry.data.get(CONF_HOST, "")

        if system:
            hostname = system.hostname or "Unraid"
            version = system.version or "Unknown"
            agent_version = getattr(system, "agent_version", None)

        device_info = DeviceInfo(
            identifiers={(DOMAIN, self.coordinator.config_entry.entry_id)},
            name=hostname,
            manufacturer=MANUFACTURER,
            model=f"Unraid {version}",
            sw_version=version,
            configuration_url=f"http://{host}",
        )

        if agent_version:
            device_info["hw_version"] = agent_version

        return device_info

    @property
    def available(self) -> bool:
        """Return if entity is available."""
        return (
            self.coordinator.last_update_success and self.coordinator.data is not None
        )


def build_vm_device_info(
    coordinator: UnraidDataUpdateCoordinator,
    vm_identifier: str,
    vm_name: str,
) -> DeviceInfo:
    """
    Build device info for a virtual machine.

    Each VM gets its own device, linked to the Unraid server device, so its
    controls and metrics are grouped together. The libvirt UUID is used as the
    identifier so renaming a VM keeps the same device.
    """
    entry_id = coordinator.config_entry.entry_id
    device_info = DeviceInfo(
        identifiers={(DOMAIN, f"{entry_id}_vm_{vm_identifier}")},
        name=vm_name,
        manufacturer="QEMU/KVM",
        model="Virtual Machine",
    )
    # The server device is registered during setup, before the platforms load.
    server = dr.async_get(coordinator.hass).async_get_device_by_identifier(
        (DOMAIN, entry_id), entry_id
    )
    if server is not None:
        device_info["via_device_id"] = server.id
    return device_info


def find_vm(
    coordinator: UnraidDataUpdateCoordinator,
    vm_identifier: str | None,
    vm_name: str | None,
) -> Any | None:
    """Find a VM in coordinator data by stable identifier, falling back to name."""
    data = coordinator.data
    if not data or not data.vms:
        return None
    for vm in data.vms:
        current_identifier = getattr(vm, "id", None) or getattr(vm, "name", None)
        if vm_identifier is not None and current_identifier == vm_identifier:
            return vm
        if vm_name is not None and getattr(vm, "name", None) == vm_name:
            return vm
    return None


class UnraidEntity(UnraidBaseEntity):
    """Entity with description support for Unraid Management Agent."""

    entity_description: UnraidEntityDescription

    def __init__(
        self,
        coordinator: UnraidDataUpdateCoordinator,
        entity_description: UnraidEntityDescription,
    ) -> None:
        """Initialize the entity."""
        super().__init__(coordinator, entity_description.key)
        self.entity_description = entity_description

    @property
    def available(self) -> bool:
        """Return if entity is available."""
        if super().available:
            return self.entity_description.available_fn(self.coordinator)
        return False


# Export these for external use
__all__ = [
    "UnraidBaseEntity",
    "UnraidEntity",
    "UnraidEntityDescription",
    "build_vm_device_info",
    "find_vm",
]
