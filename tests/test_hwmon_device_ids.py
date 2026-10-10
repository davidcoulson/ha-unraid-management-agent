"""Test device-based keys for USB HID hwmon chips (temperatures and fans)."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.unraid_management_agent.api.models import (
    FanInfo,
    TemperatureInfo,
    fan_sensor_keys,
)
from custom_components.unraid_management_agent.cleanup import (
    _build_valid_dynamic_entity_keys,
)
from custom_components.unraid_management_agent.const import (
    CONF_ENABLE_FAN_CONTROL,
    DOMAIN,
)
from custom_components.unraid_management_agent.coordinator import UnraidData
from custom_components.unraid_management_agent.hwmon import fan_legacy_unique_ids
from custom_components.unraid_management_agent.sensor import (
    _hwmon_temperature_channels,
)

from .const import MOCK_CONFIG, MOCK_OPTIONS

ENTRY_ID = "test_entry_id"
TEMP = f"{ENTRY_ID}_temperature_"
FAN = f"{ENTRY_ID}_fan_"
SERIAL_A = "07274-50017"
SERIAL_B = "07274-61234"


def _temp(source: str, value: float, device_id: str | None) -> TemperatureInfo:
    return TemperatureInfo(
        name=f"{source}_Coolant_Temp_temp1_input",
        value_celsius=value,
        sensor_type="other",
        source=source,
        device_id=device_id,
    )


def _fan(name: str, rpm: int, source: str, device_id: str | None) -> FanInfo:
    return FanInfo(name=name, rpm=rpm, source=source, device_id=device_id)


def _system(temps: list[TemperatureInfo], fans: list[FanInfo]) -> MagicMock:
    system = MagicMock()
    system.temperatures = temps
    system.fans = fans
    return system


OCTO_A = _temp("octo-hid-3-3", 27.8, SERIAL_A)
OCTO_A_RECONNECTED = _temp("octo-hid-3-13", 28.4, SERIAL_A)
OCTO_B = _temp("octo-hid-3-14", 31.0, SERIAL_B)
# What the agent reports with one Octo, and after a second one is added
FAN_A = _fan("octo_fan8", 750, "octo-hid-3-13", SERIAL_A)
FAN_A_RENAMED = _fan(f"octo-{SERIAL_A}_fan8", 751, "octo-hid-3-13", SERIAL_A)
FAN_B = _fan(f"octo-{SERIAL_B}_fan8", 900, "octo-hid-3-14", SERIAL_B)


def _keys(temps: list[TemperatureInfo]) -> set[str]:
    return {key for key, _, _ in _hwmon_temperature_channels(_system(temps, []))}


def test_temperature_key_uses_device_id() -> None:
    """With a device_id the key names the device; a reconnect keeps it."""
    assert OCTO_A.hwmon_key == f"octo-hid-{SERIAL_A}_temp1"
    assert OCTO_A.hwmon_hid_chip == "octo-hid"
    assert (
        _keys([OCTO_A]) == _keys([OCTO_A_RECONNECTED]) == {"octo_hid_07274_50017_temp1"}
    )


def test_two_octos_with_device_ids() -> None:
    """Two identical controllers get separate, address-free keys and names."""
    channels = _hwmon_temperature_channels(_system([OCTO_A, OCTO_B], []))
    assert {key: name for key, _, name in channels} == {
        "octo_hid_07274_50017_temp1": f"octo {SERIAL_A} Coolant Temp",
        "octo_hid_07274_61234_temp1": f"octo {SERIAL_B} Coolant Temp",
    }


def test_fan_keys() -> None:
    """Fans with a device_id are keyed by device, so a rename keeps the key."""
    assert FAN_A.device_key == FAN_A_RENAMED.device_key == "octo_07274_50017_fan8"
    assert FAN_A.chip_short == "octo"
    keys = [key for key, _, _ in fan_sensor_keys([FAN_A_RENAMED, FAN_B])]
    assert keys == ["octo_07274_50017_fan8", "octo_07274_61234_fan8"]
    plain = FanInfo(name="nct6798_fan1", rpm=900)
    assert plain.device_key is None
    assert plain.chip_short is None
    assert FanInfo(name="octo_pump", rpm=1, device_id=SERIAL_A).device_key is None
    data = UnraidData(system=_system([], [FAN_A_RENAMED, FAN_B]))
    assert {"fan_octo_07274_50017_fan8", "fan_octo_07274_61234_fan8"} <= (
        _build_valid_dynamic_entity_keys(data)
    )


def test_fan_legacy_ids_only_for_a_single_controller() -> None:
    """The name-based ID is only adopted when it cannot be another controller."""
    assert fan_legacy_unique_ids(ENTRY_ID, FAN_A, [FAN_A]) == [f"{FAN}octo_fan8"]
    assert fan_legacy_unique_ids(ENTRY_ID, FAN_A_RENAMED, [FAN_A_RENAMED, FAN_B]) == []
    assert fan_legacy_unique_ids(ENTRY_ID, FanInfo(name="cpu", rpm=1), []) == []
    assert fan_legacy_unique_ids(ENTRY_ID, {"name": "x"}, []) == []


def _entry(hass: HomeAssistant) -> MockConfigEntry:
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="Unraid (unraid-test)",
        data=MOCK_CONFIG,
        options={**MOCK_OPTIONS, CONF_ENABLE_FAN_CONTROL: True},
        entry_id=ENTRY_ID,
    )
    entry.add_to_hass(hass)
    return entry


def _register(
    registry: er.EntityRegistry,
    entry: MockConfigEntry,
    unique_id: str,
    entity_id: str,
    *,
    disabled: bool = False,
) -> None:
    registry.async_get_or_create(
        "sensor",
        DOMAIN,
        unique_id,
        config_entry=entry,
        suggested_object_id=entity_id.removeprefix("sensor."),
        disabled_by=er.RegistryEntryDisabler.INTEGRATION if disabled else None,
    )


def _value(hass: HomeAssistant, entity_id: str) -> float:
    state = hass.states.get(entity_id)
    assert state is not None
    return float(state.state)


@pytest.mark.usefixtures("mock_unraid_websocket_client_class")
async def test_existing_entities_move_to_device_keys(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    mock_async_unraid_client: MagicMock,
) -> None:
    """Model-keyed temperature and name-keyed fan entities keep their IDs."""
    system = mock_async_unraid_client.get_system_info.return_value
    system.temperatures = [OCTO_A_RECONNECTED]
    system.fans = [FAN_A]
    entry = _entry(hass)
    _register(entity_registry, entry, f"{TEMP}octo_hid_temp1", "sensor.coolant")
    _register(entity_registry, entry, f"{FAN}octo_fan8", "sensor.flow")
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    coolant = entity_registry.async_get("sensor.coolant")
    flow = entity_registry.async_get("sensor.flow")
    assert coolant is not None
    assert flow is not None
    assert coolant.unique_id == f"{TEMP}octo_hid_07274_50017_temp1"
    assert flow.unique_id == f"{FAN}octo_07274_50017_fan8"
    assert _value(hass, "sensor.coolant") == 28.4
    assert _value(hass, "sensor.flow") == 750


@pytest.mark.usefixtures("mock_unraid_websocket_client_class")
async def test_second_controller_added_later(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    mock_async_unraid_client: MagicMock,
) -> None:
    """Adding a second Octo leaves the first one's sensors where they are."""
    system = mock_async_unraid_client.get_system_info.return_value
    system.temperatures = [OCTO_A]
    system.fans = [FAN_A]
    entry = _entry(hass)
    _register(entity_registry, entry, f"{TEMP}octo_hid_3_3_temp1", "sensor.coolant")
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    flow = entity_registry.async_get_entity_id(
        "sensor", DOMAIN, f"{FAN}octo_07274_50017_fan8"
    )
    assert flow is not None

    # The agent now names the first Octo's fans by device, and the first Octo
    # reconnects with a new address at the same time.
    system.temperatures = [OCTO_A_RECONNECTED, OCTO_B]
    system.fans = [FAN_A_RENAMED, FAN_B]
    await entry.runtime_data.coordinator.async_refresh()
    await hass.async_block_till_done()

    assert _value(hass, "sensor.coolant") == 28.4
    assert _value(hass, flow) == 751
    temps = {
        e.unique_id
        for e in er.async_entries_for_config_entry(entity_registry, ENTRY_ID)
        if e.unique_id.startswith(TEMP)
    }
    assert temps == {
        f"{TEMP}octo_hid_07274_50017_temp1",
        f"{TEMP}octo_hid_07274_61234_temp1",
    }


@pytest.mark.usefixtures("mock_unraid_websocket_client_class")
async def test_controller_absent_at_startup(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    mock_async_unraid_client: MagicMock,
) -> None:
    """A controller that is unplugged when HA starts keeps its entity later."""
    system = mock_async_unraid_client.get_system_info.return_value
    system.temperatures = []
    system.fans = []
    entry = _entry(hass)
    _register(
        entity_registry, entry, f"{TEMP}octo_hid_3_2_temp1", "sensor.old", disabled=True
    )
    _register(entity_registry, entry, f"{TEMP}octo_hid_3_3_temp1", "sensor.coolant")
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    system.temperatures = [OCTO_A_RECONNECTED]
    await entry.runtime_data.coordinator.async_refresh()
    await hass.async_block_till_done()

    coolant = entity_registry.async_get("sensor.coolant")
    assert coolant is not None
    assert coolant.unique_id == f"{TEMP}octo_hid_07274_50017_temp1"
    assert _value(hass, "sensor.coolant") == 28.4


@pytest.mark.usefixtures("mock_unraid_websocket_client_class")
async def test_ambiguous_entities_are_not_adopted(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    mock_async_unraid_client: MagicMock,
) -> None:
    """With two Octos present, a model-keyed entity is not given to either."""
    system = mock_async_unraid_client.get_system_info.return_value
    system.temperatures = [OCTO_A, OCTO_B]
    system.fans = [FAN_A_RENAMED, FAN_B]
    entry = _entry(hass)
    _register(entity_registry, entry, f"{TEMP}octo_hid_temp1", "sensor.coolant")
    _register(entity_registry, entry, f"{FAN}octo_fan8", "sensor.flow")
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    coolant = entity_registry.async_get("sensor.coolant")
    flow = entity_registry.async_get("sensor.flow")
    assert coolant is not None
    assert flow is not None
    assert coolant.unique_id == f"{TEMP}octo_hid_temp1"
    assert flow.unique_id == f"{FAN}octo_fan8"
