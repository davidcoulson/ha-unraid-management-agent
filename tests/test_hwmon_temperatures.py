"""Test per-channel hwmon temperature sensors."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest
from homeassistant.const import STATE_UNAVAILABLE
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.unraid_management_agent.api.models import TemperatureInfo
from custom_components.unraid_management_agent.cleanup import (
    _build_valid_dynamic_entity_keys,
    _unavailable_data_prefixes,
)
from custom_components.unraid_management_agent.const import (
    CONF_ENABLE_FAN_CONTROL,
    DOMAIN,
)
from custom_components.unraid_management_agent.coordinator import UnraidData
from custom_components.unraid_management_agent.sensor import (
    _hwmon_temperature_channels,
)

from .const import MOCK_CONFIG, MOCK_OPTIONS

ENTRY_ID = "test_entry_id"
PREFIX = f"{ENTRY_ID}_temperature_"


def _reading(name: str, value: float, source: str | None) -> TemperatureInfo:
    return TemperatureInfo(
        name=name, value_celsius=value, sensor_type="other", source=source
    )


COOLANT = _reading("octo-hid-3-3_Coolant_Temp_temp1_input", 27.8, "octo-hid-3-3")
NVME_2800 = _reading("nvme-pci-2800_Composite_temp1_input", 34.85, "nvme-pci-2800")
NVME_2700 = _reading("nvme-pci-2700_Composite_temp1_input", 29.85, "nvme-pci-2700")
# Older agents list voltages, currents and power next to temperatures
VOLTAGE = _reading("octo-hid-3-3_Fan_1_voltage_in0_input", 12.02, "octo-hid-3-3")
POWER = _reading("octo-hid-3-3_Fan_1_power_power1_input", 3.02, "octo-hid-3-3")

READINGS = [COOLANT, NVME_2800, NVME_2700, VOLTAGE, POWER]


def _system(readings: list[TemperatureInfo]) -> MagicMock:
    system = MagicMock()
    system.temperatures = readings
    return system


def _keys(readings: list[TemperatureInfo]) -> set[str]:
    return {key for key, _, _ in _hwmon_temperature_channels(_system(readings))}


def test_temperature_info_feature_and_label() -> None:
    """Channel, label and identity are parsed from the agent's reading name."""
    assert COOLANT.hwmon_feature == "temp1"
    assert COOLANT.label == "Coolant Temp"
    assert COOLANT.hwmon_key == "octo-hid-3-3_temp1"
    assert VOLTAGE.hwmon_feature is None
    assert POWER.hwmon_feature is None
    assert VOLTAGE.label is None
    assert VOLTAGE.hwmon_key is None
    unlabelled = TemperatureInfo(
        name="acpitz-acpi-0_temp1_input", source="acpitz-acpi-0"
    )
    assert unlabelled.label == "temp1"


def test_channel_keys_do_not_depend_on_other_chips() -> None:
    """A channel keeps its key when a chip sharing its short name disappears."""
    both = _keys([NVME_2800, NVME_2700])
    only_one = _keys([NVME_2800])
    assert both == {"nvme_pci_2800_temp1", "nvme_pci_2700_temp1"}
    assert only_one == {"nvme_pci_2800_temp1"}


def test_display_name_uses_short_chip_only_when_unique() -> None:
    """Names read 'octo Coolant Temp' but keep the bus address for 'nvme'."""
    names = {
        key: name for key, _, name in _hwmon_temperature_channels(_system(READINGS))
    }
    assert names == {
        "octo_hid_3_3_temp1": "octo Coolant Temp",
        "nvme_pci_2800_temp1": "nvme-pci-2800 Composite",
        "nvme_pci_2700_temp1": "nvme-pci-2700 Composite",
    }


def test_readings_without_source_stay_distinct() -> None:
    """Without a source, the reading name keeps two channels apart."""
    first = _reading("chip-a_Inlet_temp1_input", 25.0, None)
    second = _reading("chip-b_Outlet_temp1_input", 30.0, None)
    assert _keys([first, second]) == {
        "chip_a_inlet_temp1",
        "chip_b_outlet_temp1",
    }


def _entry(hass: HomeAssistant, **options: object) -> MockConfigEntry:
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="Unraid (unraid-test)",
        data=MOCK_CONFIG,
        options={**MOCK_OPTIONS, **options},
        entry_id=ENTRY_ID,
    )
    entry.add_to_hass(hass)
    return entry


def _temperature_entities(registry: er.EntityRegistry) -> dict[str, er.RegistryEntry]:
    return {
        e.unique_id: e
        for e in er.async_entries_for_config_entry(registry, ENTRY_ID)
        if e.unique_id.startswith(PREFIX)
    }


@pytest.mark.usefixtures("mock_unraid_websocket_client_class")
async def test_hwmon_temperature_sensors(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    mock_async_unraid_client: MagicMock,
) -> None:
    """Each temperature channel gets a disabled-by-default sensor; others are skipped."""
    mock_async_unraid_client.get_system_info.return_value.temperatures = READINGS
    entry = _entry(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    temps = _temperature_entities(entity_registry)
    assert set(temps) == {
        f"{PREFIX}octo_hid_3_3_temp1",
        f"{PREFIX}nvme_pci_2800_temp1",
        f"{PREFIX}nvme_pci_2700_temp1",
    }
    coolant = temps[f"{PREFIX}octo_hid_3_3_temp1"]
    assert coolant.entity_id == "sensor.unraid_test_temperature_octo_coolant_temp"
    assert coolant.disabled_by is er.RegistryEntryDisabler.INTEGRATION

    # Enable it and check the reported value
    entity_registry.async_update_entity(coolant.entity_id, disabled_by=None)
    await hass.config_entries.async_reload(entry.entry_id)
    await hass.async_block_till_done()
    state = hass.states.get(coolant.entity_id)
    assert state is not None
    assert float(state.state) == 27.8
    assert state.attributes["unit_of_measurement"] == "°C"
    assert state.attributes["device_class"] == "temperature"
    assert state.attributes["sensor"] == "octo-hid-3-3_Coolant_Temp_temp1_input"


@pytest.mark.usefixtures("mock_unraid_websocket_client_class")
async def test_created_without_fan_control(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    mock_async_unraid_client: MagicMock,
) -> None:
    """Temperature sensors do not depend on the fan control option."""
    mock_async_unraid_client.get_system_info.return_value.temperatures = [COOLANT]
    entry = _entry(hass, **{CONF_ENABLE_FAN_CONTROL: False})
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    assert set(_temperature_entities(entity_registry)) == {
        f"{PREFIX}octo_hid_3_3_temp1"
    }


@pytest.mark.usefixtures("mock_unraid_websocket_client_class")
async def test_channel_added_after_setup(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    mock_async_unraid_client: MagicMock,
) -> None:
    """A channel that appears in a later update gets its sensor without a reload."""
    system = mock_async_unraid_client.get_system_info.return_value
    system.temperatures = [NVME_2800]
    entry = _entry(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    assert set(_temperature_entities(entity_registry)) == {
        f"{PREFIX}nvme_pci_2800_temp1"
    }

    system.temperatures = [NVME_2800, COOLANT]
    coordinator = entry.runtime_data.coordinator
    await coordinator.async_refresh()
    await hass.async_block_till_done()

    assert set(_temperature_entities(entity_registry)) == {
        f"{PREFIX}nvme_pci_2800_temp1",
        f"{PREFIX}octo_hid_3_3_temp1",
    }


def test_cleanup_knows_temperature_keys() -> None:
    """Stale cleanup keeps current channels and protects them when data is missing."""
    data = UnraidData(system=_system(READINGS))
    keys = _build_valid_dynamic_entity_keys(data)
    assert {
        "temperature_octo_hid_3_3_temp1",
        "temperature_nvme_pci_2800_temp1",
        "temperature_nvme_pci_2700_temp1",
    } <= keys
    assert not any(k.startswith("temperature_octo_hid_3_3_in") for k in keys)
    assert "temperature_" in _unavailable_data_prefixes(UnraidData())
    assert "temperature_" not in _unavailable_data_prefixes(data)


async def _setup_enabled_coolant(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
) -> tuple[MockConfigEntry, str]:
    """Set up the entry with the coolant sensor enabled; return its entity ID."""
    entry = _entry(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    entity_id = _temperature_entities(entity_registry)[
        f"{PREFIX}octo_hid_3_3_temp1"
    ].entity_id
    entity_registry.async_update_entity(entity_id, disabled_by=None)
    await hass.config_entries.async_reload(entry.entry_id)
    await hass.async_block_till_done()
    return entry, entity_id


@pytest.mark.usefixtures("mock_unraid_websocket_client_class")
async def test_unavailable_when_channel_disappears(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    mock_async_unraid_client: MagicMock,
) -> None:
    """A channel missing from the latest data makes its sensor unavailable."""
    system = mock_async_unraid_client.get_system_info.return_value
    system.temperatures = [COOLANT, NVME_2800]
    entry, entity_id = await _setup_enabled_coolant(hass, entity_registry)
    coordinator = entry.runtime_data.coordinator
    state = hass.states.get(entity_id)
    assert state is not None
    assert float(state.state) == 27.8

    system.temperatures = [NVME_2800]
    await coordinator.async_refresh()
    await hass.async_block_till_done()
    state = hass.states.get(entity_id)
    assert state is not None
    assert state.state == STATE_UNAVAILABLE

    system.temperatures = [COOLANT, NVME_2800]
    await coordinator.async_refresh()
    await hass.async_block_till_done()
    state = hass.states.get(entity_id)
    assert state is not None
    assert float(state.state) == 27.8


@pytest.mark.usefixtures("mock_unraid_websocket_client_class")
async def test_reading_matched_by_channel_not_label(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    mock_async_unraid_client: MagicMock,
) -> None:
    """A relabelled channel (sensors.conf change) keeps feeding the same sensor."""
    system = mock_async_unraid_client.get_system_info.return_value
    system.temperatures = [COOLANT]
    entry, entity_id = await _setup_enabled_coolant(hass, entity_registry)

    relabelled = _reading("octo-hid-3-3_Loop_Inlet_temp1_input", 31.5, "octo-hid-3-3")
    system.temperatures = [relabelled]
    await entry.runtime_data.coordinator.async_refresh()
    await hass.async_block_till_done()

    state = hass.states.get(entity_id)
    assert state is not None
    assert float(state.state) == 31.5
    assert state.attributes["sensor"] == "octo-hid-3-3_Loop_Inlet_temp1_input"
    assert set(_temperature_entities(entity_registry)) == {
        f"{PREFIX}octo_hid_3_3_temp1"
    }
