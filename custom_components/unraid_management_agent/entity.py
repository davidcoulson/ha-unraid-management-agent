"""Base entity classes for Unraid Management Agent."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, Final

from homeassistant.const import CONF_HOST
from homeassistant.core import callback
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.device_registry import ChildDeviceInfo, DeviceInfo
from homeassistant.helpers.entity import EntityDescription
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import (
    CONF_ENABLE_CONTAINER_DEVICES,
    CONF_ENABLE_VM_DEVICES,
    CONF_READ_ONLY,
    DEFAULT_ENABLE_CONTAINER_DEVICES,
    DEFAULT_ENABLE_VM_DEVICES,
    DEFAULT_READ_ONLY,
    DOMAIN,
    MANUFACTURER,
)

if TYPE_CHECKING:
    from .coordinator import UnraidDataUpdateCoordinator


# Devices grouping everything about Docker and about VMs, linked to the server
# device. Container and VM devices are child devices of these, so the server
# device lists two devices instead of dozens of containers and VMs.
DOCKER_DEVICE: Final = "docker"
VMS_DEVICE: Final = "vms"
_GROUP_DEVICE_MODELS: Final = {DOCKER_DEVICE: "Docker", VMS_DEVICE: "VM Manager"}
_GROUP_DEVICE_PAGES: Final = {DOCKER_DEVICE: "Docker", VMS_DEVICE: "VMs"}


@dataclass(frozen=True, kw_only=True)
class UnraidEntityDescription(EntityDescription):
    """Base description for all Unraid entities."""

    available_fn: Callable[[UnraidDataUpdateCoordinator], bool] = lambda _: True
    supported_fn: Callable[[UnraidDataUpdateCoordinator], bool] = lambda _: True
    # DOCKER_DEVICE or VMS_DEVICE to put the entity on that device
    device_group: str | None = None


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


def vm_devices_enabled(coordinator: UnraidDataUpdateCoordinator) -> bool:
    """Return True when VMs are shown as separate devices (an option, off by default)."""
    return bool(
        coordinator.config_entry.options.get(
            CONF_ENABLE_VM_DEVICES, DEFAULT_ENABLE_VM_DEVICES
        )
    )


def group_device_identifier(entry_id: str, group: str) -> str:
    """Return the device registry identifier of the Docker or VMs device."""
    return f"{entry_id}_{group}"


@callback
def async_get_or_create_group_device(
    coordinator: UnraidDataUpdateCoordinator, group: str
) -> dr.DeviceEntry | None:
    """
    Register the Docker or VMs device of the server and return it.

    It is a regular device linked to the server device, created the first time
    an entity or child device needs it, so a server without Docker or VMs gets
    no empty device. It is named after the server ("<hostname> Docker"), which
    keeps it apart from another server's and keeps the friendly names of the
    entities moved to it from the server device. A new one starts in the
    server's area with its labels, which container and VM devices then
    inherit, so area and label targets that reached them through the server
    keep doing so, and is disabled if the server is. Returns None if the
    server device is missing.
    """
    entry = coordinator.config_entry
    registry = dr.async_get(coordinator.hass)
    # The server device is registered during setup, before the platforms load.
    server = registry.async_get_device_by_identifier(
        (DOMAIN, entry.entry_id), entry.entry_id
    )
    if server is None:
        return None
    data = coordinator.data
    system = data.system if data else None
    hostname = (system.hostname if system else None) or "Unraid"
    host = entry.data.get(CONF_HOST, "")
    identifier = (DOMAIN, group_device_identifier(entry.entry_id, group))
    is_new = registry.async_get_device_by_identifier(identifier, entry.entry_id) is None
    device = registry.async_get_or_create(
        config_entry_id=entry.entry_id,
        identifiers={identifier},
        manufacturer=MANUFACTURER,
        model=_GROUP_DEVICE_MODELS[group],
        configuration_url=f"http://{host}/{_GROUP_DEVICE_PAGES[group]}",
        translation_key=group,
        translation_placeholders={"hostname": hostname},
        via_device_id=server.id,
    )
    if not is_new:
        return device
    # A device restored from an earlier removal keeps the area and labels the
    # user gave it
    if device.area_id is None and not device.labels:
        area_id, labels = server.area_id, set(server.labels)
    else:
        area_id, labels = device.area_id, set(device.labels)
    return registry.async_update_device(
        device.id,
        area_id=area_id,
        labels=labels,
        # Container and VM devices of a disabled server are disabled with it,
        # and stay so under a disabled Docker or VMs device
        disabled_by=device.disabled_by or server.disabled_by,
    )


def build_group_device_info(
    coordinator: UnraidDataUpdateCoordinator, group: str
) -> DeviceInfo:
    """Build device info putting an entity on the Docker or VMs device."""
    entry_id = coordinator.config_entry.entry_id
    if async_get_or_create_group_device(coordinator, group) is None:
        # Keep the entity on the server device if it is somehow missing.
        return DeviceInfo(identifiers={(DOMAIN, entry_id)})
    return DeviceInfo(identifiers={(DOMAIN, group_device_identifier(entry_id, group))})


def build_vm_device_info(
    coordinator: UnraidDataUpdateCoordinator,
    vm_identifier: str,
    vm_name: str,
) -> DeviceInfo | ChildDeviceInfo:
    """
    Build device info for a virtual machine.

    VMs are child devices of the server's VMs device, so they are grouped
    there rather than listed as separate devices or under the server. The
    libvirt UUID is used as the identifier so renaming a VM keeps the device.

    The device is named after the VM. Home Assistant puts the parent device's
    name ("<hostname> VMs") in front of it in entity names, which tells VMs
    apart from containers, so the "VM · " prefix VM devices had under the
    server is no longer used. The registry updates the name each time the
    entities are set up, so existing VM devices and renamed VMs follow.
    """
    entry_id = coordinator.config_entry.entry_id
    parent = async_get_or_create_group_device(coordinator, VMS_DEVICE)
    if parent is None:
        # Keep the entity on the server device if it is somehow missing.
        return DeviceInfo(identifiers={(DOMAIN, entry_id)})
    return ChildDeviceInfo(
        identifiers={(DOMAIN, f"{entry_id}_vm_{vm_identifier}")},
        name=vm_name,
        parent_device_id=parent.id,
    )


def find_vm(
    coordinator: UnraidDataUpdateCoordinator,
    vm_identifier: str | None,
    vm_name: str | None,
) -> Any | None:
    """
    Find a VM in coordinator data by stable identifier, falling back to name.

    The identifier is matched across all VMs first, so a VM that was renamed
    is not confused with another VM that has since taken its old name.
    """
    data = coordinator.data
    if not data or not data.vms:
        return None
    if vm_identifier is not None:
        for vm in data.vms:
            current = getattr(vm, "id", None) or getattr(vm, "name", None)
            if current == vm_identifier:
                return vm
    if vm_name is not None:
        for vm in data.vms:
            if getattr(vm, "name", None) == vm_name:
                return vm
    return None


def container_devices_enabled(coordinator: UnraidDataUpdateCoordinator) -> bool:
    """Return True when containers are shown as separate devices (off by default)."""
    return bool(
        coordinator.config_entry.options.get(
            CONF_ENABLE_CONTAINER_DEVICES, DEFAULT_ENABLE_CONTAINER_DEVICES
        )
    )


def build_container_device_info(
    coordinator: UnraidDataUpdateCoordinator,
    container_name: str,
) -> DeviceInfo | ChildDeviceInfo:
    """
    Build device info for a Docker container.

    Containers are child devices of the server's Docker device: there can be
    dozens, so they are grouped there instead of being listed as separate
    devices or under the server. Keyed by name because container IDs change
    whenever a container is recreated.
    """
    entry_id = coordinator.config_entry.entry_id
    parent = async_get_or_create_group_device(coordinator, DOCKER_DEVICE)
    if parent is None:
        # Keep the entity on the server device if it is somehow missing.
        return DeviceInfo(identifiers={(DOMAIN, entry_id)})
    return ChildDeviceInfo(
        identifiers={(DOMAIN, f"{entry_id}_container_{container_name}")},
        name=container_name,
        parent_device_id=parent.id,
    )


def read_only_enabled(coordinator: UnraidDataUpdateCoordinator) -> bool:
    """Return True when the entry is in read-only mode (nothing may change the server)."""
    return bool(coordinator.config_entry.options.get(CONF_READ_ONLY, DEFAULT_READ_ONLY))


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
    "DOCKER_DEVICE",
    "VMS_DEVICE",
    "UnraidBaseEntity",
    "UnraidEntity",
    "UnraidEntityDescription",
    "async_get_or_create_group_device",
    "build_container_device_info",
    "build_group_device_info",
    "build_vm_device_info",
    "container_devices_enabled",
    "find_vm",
    "group_device_identifier",
    "read_only_enabled",
    "vm_devices_enabled",
]
