"""Tests for the Unraid Management Agent number platform (fan speed control)."""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError

from custom_components.unraid_management_agent.api.models import (
    FanControlStatus,
    FanDevice,
)
from custom_components.unraid_management_agent.const import (
    CONF_ENABLE_FAN_CONTROL,
)
from custom_components.unraid_management_agent.coordinator import (
    UnraidData,
    UnraidRuntimeData,
)
from custom_components.unraid_management_agent.number import (
    UnraidFanSpeedNumber,
    async_setup_entry,
)


async def test_number_setup_disabled_by_default(
    hass: HomeAssistant,
    mock_config_entry,
) -> None:
    """Test number setup returns early when fan control is disabled."""
    hass.config_entries.async_update_entry(
        mock_config_entry, options={CONF_ENABLE_FAN_CONTROL: False}
    )
    add_entities = MagicMock()

    await async_setup_entry(hass, mock_config_entry, add_entities)
    add_entities.assert_not_called()


async def test_number_setup_enabled_with_fans(
    hass: HomeAssistant,
    mock_config_entry,
) -> None:
    """Test number setup creates entities for controllable fans."""
    hass.config_entries.async_update_entry(
        mock_config_entry, options={CONF_ENABLE_FAN_CONTROL: True}
    )

    fan1 = FanDevice(
        id="fan1",
        name="CPU Fan",
        controllable=True,
        pwm_percent=55,
        rpm=1200,
        mode="manual",
        pwm_value=140,
    )
    fan2 = FanDevice(
        id="fan2",
        name="Case Fan",
        controllable=False,
        pwm_percent=100,
        rpm=800,
    )

    coordinator = MagicMock()
    coordinator.config_entry = mock_config_entry
    coordinator.data = UnraidData(fan_control=FanControlStatus(fans=[fan1, fan2]))
    mock_config_entry.runtime_data = MagicMock(coordinator=coordinator)

    added = []

    def _add_entities(entities: list[Any]) -> None:
        added.extend(entities)

    await async_setup_entry(hass, mock_config_entry, _add_entities)
    assert len(added) == 1
    assert added[0]._fan_id == "fan1"
    assert added[0].native_value == 55.0
    assert added[0].extra_state_attributes == {
        "fan_id": "fan1",
        "rpm": 1200,
        "mode": "manual",
        "pwm_value": 140,
    }
    assert added[0].available is True


async def test_number_fan_properties_and_actions(
    hass: HomeAssistant,
    mock_config_entry,
) -> None:
    """Test fan speed entity values, availability, and set value action."""
    fan = FanDevice(
        id="fan1",
        name="CPU Fan",
        controllable=True,
        pwm_percent=50,
        rpm=1100,
        mode="manual",
        pwm_value=128,
    )

    coordinator = MagicMock()
    coordinator.last_update_success = True
    coordinator.config_entry = mock_config_entry
    coordinator.data = UnraidData(fan_control=FanControlStatus(fans=[fan]))
    coordinator.async_request_refresh = AsyncMock()

    client = MagicMock()
    client.set_fan_speed = AsyncMock()
    mock_config_entry.runtime_data = UnraidRuntimeData(
        coordinator=coordinator, client=client
    )

    entity = UnraidFanSpeedNumber(coordinator, mock_config_entry, "fan1", "CPU Fan")
    entity.hass = hass

    assert entity.native_value == 50.0
    assert entity.available is True

    # Test setting value
    await entity.async_set_native_value(75.0)
    client.set_fan_speed.assert_called_once_with("fan1", 75)
    coordinator.async_request_refresh.assert_called_once()

    # Test setting value failure
    client.set_fan_speed.side_effect = Exception("API error")
    with pytest.raises(HomeAssistantError):
        await entity.async_set_native_value(80.0)

    # Test unavailable when coordinator fails update
    coordinator.last_update_success = False
    assert entity.available is False
    coordinator.last_update_success = True

    # Test unavailable when fan not controllable or missing
    uncontrollable_fan = FanDevice(
        id="fan1",
        name="CPU Fan",
        controllable=False,
        pwm_percent=50,
    )
    coordinator.data = UnraidData(
        fan_control=FanControlStatus(fans=[uncontrollable_fan])
    )
    assert entity.available is False

    coordinator.data = UnraidData(fan_control=FanControlStatus(fans=[]))
    assert entity.native_value is None
    assert entity.available is False

    coordinator.data = None
    assert entity.native_value is None
    assert entity.extra_state_attributes == {"fan_id": "fan1"}
