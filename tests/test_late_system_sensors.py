"""Test system and ZFS ARC sensors the agent reports only after setup."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.unraid_management_agent.api.models import ZFSArcStats
from custom_components.unraid_management_agent.const import DOMAIN

from .const import MOCK_CONFIG, MOCK_OPTIONS

ENTRY_ID = "test_entry_id"
CPU_POWER = f"{ENTRY_ID}_cpu_power"
ARC_HIT_RATIO = f"{ENTRY_ID}_zfs_arc_hit_ratio"


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


def _unique_ids(registry: er.EntityRegistry) -> set[str]:
    return {e.unique_id for e in er.async_entries_for_config_entry(registry, ENTRY_ID)}


@pytest.mark.usefixtures("mock_unraid_websocket_client_class")
async def test_cpu_power_added_when_first_reported(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    mock_async_unraid_client: MagicMock,
) -> None:
    """CPU power needs two RAPL samples, so it is absent in the first update."""
    system = mock_async_unraid_client.get_system_info.return_value
    system.cpu_power_watts = None
    entry = _entry(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    assert CPU_POWER not in _unique_ids(entity_registry)

    system.cpu_power_watts = 108.7
    await entry.runtime_data.coordinator.async_refresh()
    await hass.async_block_till_done()

    assert CPU_POWER in _unique_ids(entity_registry)
    entity_id = entity_registry.async_get_entity_id("sensor", DOMAIN, CPU_POWER)
    assert entity_id is not None
    state = hass.states.get(entity_id)
    assert state is not None
    assert float(state.state) == 108.7

    # Later updates must not try to add it again
    await entry.runtime_data.coordinator.async_refresh()
    await hass.async_block_till_done()
    assert CPU_POWER in _unique_ids(entity_registry)


@pytest.mark.usefixtures("mock_unraid_websocket_client_class")
async def test_arc_sensors_added_when_first_reported(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    mock_async_unraid_client: MagicMock,
) -> None:
    """The ARC hit ratio appears once the agent returns ARC statistics."""
    mock_async_unraid_client.get_zfs_arc_stats.return_value = None
    entry = _entry(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    assert ARC_HIT_RATIO not in _unique_ids(entity_registry)

    mock_async_unraid_client.get_zfs_arc_stats.return_value = ZFSArcStats(
        hit_ratio_percent=99.9,
        size_bytes=1024,
        configured_max_bytes=2048,
    )
    await entry.runtime_data.coordinator.async_refresh()
    await hass.async_block_till_done()

    unique_ids = _unique_ids(entity_registry)
    assert ARC_HIT_RATIO in unique_ids
    assert f"{ENTRY_ID}_zfs_arc_configured_max" in unique_ids or any(
        "arc" in unique_id and "configured" in unique_id for unique_id in unique_ids
    )
