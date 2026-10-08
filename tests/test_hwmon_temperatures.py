"""Test per-channel hwmon temperature sensors."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.unraid_management_agent.api.models import TemperatureInfo
from custom_components.unraid_management_agent.const import DOMAIN

from .const import MOCK_CONFIG, MOCK_OPTIONS

ENTRY_ID = "test_entry_id"

READINGS = [
    TemperatureInfo(
        name="octo-hid-3-3_Coolant_Temp_temp1_input",
        value_celsius=27.8,
        sensor_type="other",
        source="octo-hid-3-3",
    ),
    TemperatureInfo(
        name="nvme-pci-2800_Composite_temp1_input",
        value_celsius=34.85,
        sensor_type="other",
        source="nvme-pci-2800",
    ),
    TemperatureInfo(
        name="nvme-pci-2700_Composite_temp1_input",
        value_celsius=29.85,
        sensor_type="other",
        source="nvme-pci-2700",
    ),
    # Older agents list voltages, currents and power next to temperatures
    TemperatureInfo(
        name="octo-hid-3-3_Fan_1_voltage_in0_input",
        value_celsius=12.02,
        sensor_type="other",
        source="octo-hid-3-3",
    ),
    TemperatureInfo(
        name="octo-hid-3-3_Fan_1_power_power1_input",
        value_celsius=3.02,
        sensor_type="other",
        source="octo-hid-3-3",
    ),
]


def test_temperature_info_feature_and_label() -> None:
    """Channel and label are parsed from the agent's reading name."""
    coolant, _, _, voltage, power = READINGS
    assert coolant.hwmon_feature == "temp1"
    assert coolant.label == "Coolant Temp"
    assert voltage.hwmon_feature is None
    assert power.hwmon_feature is None
    assert voltage.label is None
    unlabelled = TemperatureInfo(
        name="acpitz-acpi-0_temp1_input", source="acpitz-acpi-0"
    )
    assert unlabelled.label == "temp1"


@pytest.mark.usefixtures("mock_unraid_websocket_client_class")
async def test_hwmon_temperature_sensors(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    mock_async_unraid_client: MagicMock,
) -> None:
    """Each temperature channel gets a disabled-by-default sensor; others are skipped."""
    mock_async_unraid_client.get_system_info.return_value.temperatures = READINGS
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="Unraid (unraid-test)",
        data=MOCK_CONFIG,
        options=MOCK_OPTIONS,
        entry_id=ENTRY_ID,
    )
    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    temps = {
        e.unique_id: e
        for e in er.async_entries_for_config_entry(entity_registry, ENTRY_ID)
        if e.unique_id.startswith(f"{ENTRY_ID}_temperature_")
    }
    # Unique short chip name, full chip name where 'nvme' is ambiguous
    assert set(temps) == {
        f"{ENTRY_ID}_temperature_octo_temp1",
        f"{ENTRY_ID}_temperature_nvme_pci_2800_temp1",
        f"{ENTRY_ID}_temperature_nvme_pci_2700_temp1",
    }
    coolant = temps[f"{ENTRY_ID}_temperature_octo_temp1"]
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
