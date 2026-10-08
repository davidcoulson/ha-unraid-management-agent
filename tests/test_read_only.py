"""Test the read-only option (sensors only, no controls)."""

from __future__ import annotations

import pytest
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import entity_registry as er
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.unraid_management_agent.const import CONF_READ_ONLY, DOMAIN

from .const import MOCK_CONFIG, MOCK_OPTIONS


def _entry(hass: HomeAssistant, *, read_only: bool) -> MockConfigEntry:
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="Unraid (unraid-test)",
        data=MOCK_CONFIG,
        options={**MOCK_OPTIONS, CONF_READ_ONLY: read_only},
        entry_id="test_entry_id",
    )
    entry.add_to_hass(hass)
    return entry


def _domains(hass: HomeAssistant, entry_id: str) -> set[str]:
    registry = er.async_get(hass)
    return {e.domain for e in er.async_entries_for_config_entry(registry, entry_id)}


@pytest.mark.usefixtures(
    "mock_async_unraid_client", "mock_unraid_websocket_client_class"
)
async def test_read_only_creates_only_sensors(hass: HomeAssistant) -> None:
    """Read-only mode sets up sensors but no switches, buttons or numbers."""
    entry = _entry(hass, read_only=True)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    domains = _domains(hass, entry.entry_id)
    assert "sensor" in domains
    assert not domains & {"switch", "button", "number"}

    # Unloading only unloads what was set up
    assert await hass.config_entries.async_unload(entry.entry_id)
    assert entry.state is ConfigEntryState.NOT_LOADED


@pytest.mark.usefixtures(
    "mock_async_unraid_client", "mock_unraid_websocket_client_class"
)
async def test_enabling_read_only_removes_existing_controls(
    hass: HomeAssistant,
) -> None:
    """Switching to read-only removes the control entities created before."""
    entry = _entry(hass, read_only=False)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    assert {"switch", "button"} <= _domains(hass, entry.entry_id)

    hass.config_entries.async_update_entry(
        entry, options={**MOCK_OPTIONS, CONF_READ_ONLY: True}
    )
    assert await hass.config_entries.async_reload(entry.entry_id)
    await hass.async_block_till_done()

    domains = _domains(hass, entry.entry_id)
    assert "sensor" in domains
    assert not domains & {"switch", "button", "number"}


@pytest.mark.usefixtures("mock_unraid_websocket_client_class")
async def test_read_only_blocks_services(
    hass: HomeAssistant, mock_async_unraid_client
) -> None:
    """Integration actions refuse to change the server in read-only mode."""
    entry = _entry(hass, read_only=True)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    with pytest.raises(HomeAssistantError) as err:
        await hass.services.async_call(
            DOMAIN, "vm_stop", {"vm_id": "Windows 10"}, blocking=True
        )
    assert err.value.translation_key == "read_only_mode"
    mock_async_unraid_client.stop_vm.assert_not_called()
