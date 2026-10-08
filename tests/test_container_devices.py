"""Test Docker containers as child devices of the Unraid server."""

from __future__ import annotations

import pytest
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers import entity_registry as er

from custom_components.unraid_management_agent.const import DOMAIN

ENTRY_ID = "test_entry_id"


@pytest.mark.usefixtures(
    "mock_unraid_client_class", "mock_unraid_websocket_client_class"
)
async def test_containers_are_child_devices_of_the_server(
    hass: HomeAssistant, mock_config_entry
) -> None:
    """Each container's switches, button and sensors share a child device."""
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    devices = dr.async_get(hass)
    server = devices.async_get_device_by_identifier((DOMAIN, ENTRY_ID), ENTRY_ID)
    plex = devices.async_get_child_device_by_identifier(
        (DOMAIN, f"{ENTRY_ID}_container_plex"), ENTRY_ID
    )
    assert server is not None
    assert plex is not None
    assert plex.name == "plex"
    assert plex.parent_device_id == server.id

    entities = er.async_get(hass)
    on_plex = {
        e.entity_id
        for e in entities.entities.values()
        if e.config_entry_id == ENTRY_ID and e.device_id == plex.id
    }
    assert "switch.unraid_test_plex_running" in on_plex
    assert "switch.unraid_test_plex_autostart" in on_plex
    assert "button.unraid_test_plex_restart" in on_plex
    assert "sensor.unraid_test_plex_cpu" in on_plex

    # Containers do not show up as separate main devices
    main_devices = dr.async_entries_for_config_entry(devices, ENTRY_ID)
    assert all("_container_" not in next(iter(d.identifiers))[1] for d in main_devices)
