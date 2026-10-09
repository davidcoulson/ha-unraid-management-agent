"""Test the system service running binary sensors (agent /services endpoint)."""

from __future__ import annotations

import logging
from typing import Any
from unittest.mock import MagicMock

import pytest
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import STATE_OFF, STATE_ON, STATE_UNAVAILABLE, EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers import entity_registry as er
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.unraid_management_agent import (
    binary_sensor,
    button,
    number,
    sensor,
    switch,
)
from custom_components.unraid_management_agent.api.exceptions import (
    UnraidNotFoundError,
)
from custom_components.unraid_management_agent.api.models import (
    DockerSettings,
    SystemService,
    SystemServiceList,
    VMSettings,
)
from custom_components.unraid_management_agent.cleanup import (
    _build_valid_dynamic_entity_keys,
    _unavailable_data_prefixes,
)
from custom_components.unraid_management_agent.const import DOMAIN
from custom_components.unraid_management_agent.coordinator import UnraidData

from .const import MOCK_CONFIG, MOCK_OPTIONS

ENTRY_ID = "test_entry_id"
PREFIX = f"{ENTRY_ID}_system_service_"

# GET /api/v1/services from a live agent (v2026.09.01, Unraid 7.4.0-beta.3)
LIVE_RESPONSE: dict[str, Any] = {
    "count": 11,
    "services": [
        {"name": "docker", "running": True},
        {"name": "libvirt", "running": True},
        {"name": "smb", "running": True},
        {"name": "nfs", "running": True},
        {"name": "ftp", "running": False},
        {"name": "sshd", "running": True},
        {"name": "nginx", "running": True},
        {"name": "syslog", "running": True},
        {"name": "ntpd", "running": True},
        {"name": "avahi", "running": True},
        {"name": "wireguard", "running": False},
    ],
    "timestamp": "2026-10-08T23:01:57.035302399-04:00",
}


def _services(*services: tuple[str | None, bool]) -> SystemServiceList:
    return SystemServiceList(
        count=len(services),
        services=[
            SystemService(name=name, running=running) for name, running in services
        ],
    )


def _entry(hass: HomeAssistant) -> MockConfigEntry:
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="Unraid (unraid-test)",
        data=MOCK_CONFIG,
        options=MOCK_OPTIONS,
        entry_id=ENTRY_ID,
    )
    entry.add_to_hass(hass)
    return entry


def _service_entities(registry: er.EntityRegistry) -> dict[str, er.RegistryEntry]:
    return {
        e.unique_id[len(PREFIX) :]: e
        for e in er.async_entries_for_config_entry(registry, ENTRY_ID)
        if e.unique_id.startswith(PREFIX)
    }


async def _setup(
    hass: HomeAssistant, *, enable: tuple[str, ...] = ()
) -> MockConfigEntry:
    """Set up the entry, enabling the given system service sensors."""
    entry = _entry(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    if enable:
        registry = er.async_get(hass)
        entities = _service_entities(registry)
        for name in enable:
            registry.async_update_entity(entities[name].entity_id, disabled_by=None)
        await hass.config_entries.async_reload(entry.entry_id)
        await hass.async_block_till_done()
    return entry


@pytest.mark.usefixtures("mock_unraid_websocket_client_class")
async def test_sensors_only_for_services_without_network_service_sensor(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    device_registry: dr.DeviceRegistry,
    mock_async_unraid_client: MagicMock,
) -> None:
    """Docker, libvirt and nginx get sensors; network services are not duplicated."""
    mock_async_unraid_client.list_services.return_value = (
        SystemServiceList.model_validate(LIVE_RESPONSE)
    )
    await _setup(hass)

    entities = _service_entities(entity_registry)
    assert set(entities) == {"docker", "libvirt", "nginx"}
    server = device_registry.async_get_device_by_identifier(
        (DOMAIN, ENTRY_ID), ENTRY_ID
    )
    assert server is not None
    for entity in entities.values():
        assert entity.disabled_by is er.RegistryEntryDisabler.INTEGRATION
        assert entity.entity_category is EntityCategory.DIAGNOSTIC
        assert entity.translation_key == "system_service"
        assert entity.device_id == server.id
    assert entities["docker"].entity_id == "binary_sensor.unraid_test_docker_service"


@pytest.mark.usefixtures("mock_unraid_websocket_client_class")
async def test_state_and_attributes(
    hass: HomeAssistant,
    mock_async_unraid_client: MagicMock,
) -> None:
    """The sensors report the running state and the Unraid enabled setting."""
    mock_async_unraid_client.list_services.return_value = _services(
        ("docker", True), ("libvirt", True), ("nginx", False)
    )
    mock_async_unraid_client.get_docker_settings.return_value = DockerSettings(
        enabled=True
    )
    mock_async_unraid_client.get_vm_settings.return_value = VMSettings(enabled=False)
    await _setup(hass, enable=("docker", "libvirt", "nginx"))

    docker = hass.states.get("binary_sensor.unraid_test_docker_service")
    assert docker is not None
    assert docker.state == STATE_ON
    assert docker.attributes["device_class"] == "running"
    assert docker.attributes["friendly_name"] == "unraid-test Docker Service"
    assert docker.attributes["enabled"] is True

    libvirt = hass.states.get("binary_sensor.unraid_test_libvirt_service")
    assert libvirt is not None
    assert libvirt.state == STATE_ON
    assert libvirt.attributes["enabled"] is False

    nginx = hass.states.get("binary_sensor.unraid_test_nginx_service")
    assert nginx is not None
    assert nginx.state == STATE_OFF
    assert "enabled" not in nginx.attributes


@pytest.mark.usefixtures("mock_unraid_websocket_client_class")
async def test_no_enabled_attribute_without_settings(
    hass: HomeAssistant,
    mock_async_unraid_client: MagicMock,
) -> None:
    """Without Docker settings data, the enabled attribute is left out."""
    mock_async_unraid_client.list_services.return_value = _services(("docker", False))
    await _setup(hass, enable=("docker",))

    docker = hass.states.get("binary_sensor.unraid_test_docker_service")
    assert docker is not None
    assert docker.state == STATE_OFF
    assert "enabled" not in docker.attributes


@pytest.mark.usefixtures("mock_unraid_websocket_client_class")
async def test_older_agent_without_endpoint(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    mock_async_unraid_client: MagicMock,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """An agent without /services (404) gets no sensors and logs no warnings."""
    mock_async_unraid_client.list_services.side_effect = UnraidNotFoundError(
        "404 page not found", status_code=404
    )
    caplog.set_level(logging.DEBUG)
    entry = await _setup(hass)

    assert entry.state is ConfigEntryState.LOADED
    assert entry.runtime_data.coordinator.data.system_services is None
    assert _service_entities(entity_registry) == {}
    assert not [
        r
        for r in caplog.records
        if "system services" in r.getMessage() and r.levelno > logging.DEBUG
    ]


@pytest.mark.usefixtures("mock_unraid_websocket_client_class")
async def test_null_service_list(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    mock_async_unraid_client: MagicMock,
) -> None:
    """A null service list is treated as unavailable data, not an empty list."""
    mock_async_unraid_client.list_services.return_value = (
        SystemServiceList.model_validate({"count": 0, "services": None})
    )
    entry = await _setup(hass)

    assert entry.runtime_data.coordinator.data.system_services is None
    assert _service_entities(entity_registry) == {}


@pytest.mark.usefixtures("mock_unraid_websocket_client_class")
async def test_service_added_after_setup(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    mock_async_unraid_client: MagicMock,
) -> None:
    """A service that appears in a later update gets its sensor without a reload."""
    mock_async_unraid_client.list_services.return_value = _services(
        ("docker", True), (None, True), ("docker", True)
    )
    entry = await _setup(hass)
    assert set(_service_entities(entity_registry)) == {"docker"}

    mock_async_unraid_client.list_services.return_value = _services(
        ("docker", True), ("nginx", True), ("smb", True)
    )
    await entry.runtime_data.coordinator.async_refresh()
    await hass.async_block_till_done()

    assert set(_service_entities(entity_registry)) == {"docker", "nginx"}


@pytest.mark.usefixtures("mock_unraid_websocket_client_class")
async def test_unavailable_when_service_disappears(
    hass: HomeAssistant,
    mock_async_unraid_client: MagicMock,
) -> None:
    """A service missing from the latest list makes its sensor unavailable."""
    mock_async_unraid_client.list_services.return_value = _services(("docker", True))
    entry = await _setup(hass, enable=("docker",))
    coordinator = entry.runtime_data.coordinator
    entity_id = "binary_sensor.unraid_test_docker_service"

    mock_async_unraid_client.list_services.return_value = _services(("nginx", True))
    await coordinator.async_refresh()
    await hass.async_block_till_done()
    state = hass.states.get(entity_id)
    assert state is not None
    assert state.state == STATE_UNAVAILABLE

    mock_async_unraid_client.list_services.return_value = _services(("docker", True))
    await coordinator.async_refresh()
    await hass.async_block_till_done()
    state = hass.states.get(entity_id)
    assert state is not None
    assert state.state == STATE_ON


@pytest.mark.usefixtures("mock_unraid_websocket_client_class")
async def test_recreated_after_registry_removal(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    mock_async_unraid_client: MagicMock,
) -> None:
    """A sensor removed from the registry comes back while the service exists."""
    mock_async_unraid_client.list_services.return_value = _services(("docker", True))
    entry = await _setup(hass)
    entity_registry.async_remove(_service_entities(entity_registry)["docker"].entity_id)
    assert _service_entities(entity_registry) == {}

    await entry.runtime_data.coordinator.async_refresh()
    await hass.async_block_till_done()

    assert set(_service_entities(entity_registry)) == {"docker"}


def test_cleanup_keys() -> None:
    """Stale cleanup keeps listed services and protects them when data is missing."""
    data = UnraidData(
        system_services=list(_services(("docker", True), (None, True)).services or [])
    )
    keys = _build_valid_dynamic_entity_keys(data)
    assert "system_service_docker" in keys
    assert not any(
        k.startswith("system_service_") and k != "system_service_docker" for k in keys
    )
    assert "system_service_" in _unavailable_data_prefixes(UnraidData())
    assert "system_service_" not in _unavailable_data_prefixes(
        UnraidData(system_services=[])
    )


def test_no_static_key_uses_system_service_prefix() -> None:
    """No static entity key may start with the dynamic system_service_ prefix."""
    for module in (binary_sensor, button, number, sensor, switch):
        for name, value in vars(module).items():
            if name.endswith("_DESCRIPTIONS"):
                for description in value:
                    assert not description.key.startswith("system_service_")
