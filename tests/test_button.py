"""Test the Unraid Management Agent button platform."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError


@pytest.mark.usefixtures(
    "mock_unraid_client_class",
    "mock_unraid_websocket_client_class",
)
async def test_button_setup(
    hass: HomeAssistant,
    mock_config_entry,
) -> None:
    """Test button platform setup."""
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    # Verify button entities are created
    button_entities = [
        entity_id
        for entity_id in hass.states.async_entity_ids("button")
        if entity_id.startswith("button.unraid_")
    ]

    # Should have array and parity check buttons
    assert len(button_entities) >= 4


@pytest.mark.usefixtures(
    "mock_unraid_client_class",
    "mock_unraid_websocket_client_class",
)
async def test_array_start_button(
    hass: HomeAssistant,
    mock_config_entry,
) -> None:
    """Test array start button."""
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    state = hass.states.get("button.unraid_test_start_array")
    assert state is not None


@pytest.mark.usefixtures(
    "mock_unraid_client_class",
    "mock_unraid_websocket_client_class",
)
async def test_array_stop_button(
    hass: HomeAssistant,
    mock_config_entry,
) -> None:
    """Test array stop button."""
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    state = hass.states.get("button.unraid_test_stop_array")
    assert state is not None


@pytest.mark.usefixtures(
    "mock_unraid_client_class",
    "mock_unraid_websocket_client_class",
)
async def test_parity_check_buttons(
    hass: HomeAssistant,
    mock_config_entry,
) -> None:
    """Test parity check buttons."""
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    state = hass.states.get("button.unraid_test_start_parity_check")
    assert state is not None

    state = hass.states.get("button.unraid_test_stop_parity_check")
    assert state is not None


@pytest.mark.usefixtures(
    "mock_unraid_client_class",
    "mock_unraid_websocket_client_class",
)
async def test_array_start_button_press(
    hass: HomeAssistant,
    mock_config_entry,
    mock_async_unraid_client,
) -> None:
    """Test pressing array start button."""
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    await hass.services.async_call(
        "button",
        "press",
        {"entity_id": "button.unraid_test_start_array"},
        blocking=True,
    )

    mock_async_unraid_client.start_array.assert_called_once()


@pytest.mark.usefixtures(
    "mock_unraid_client_class",
    "mock_unraid_websocket_client_class",
)
async def test_array_stop_button_press(
    hass: HomeAssistant,
    mock_config_entry,
    mock_async_unraid_client,
) -> None:
    """Test pressing array stop button."""
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    await hass.services.async_call(
        "button",
        "press",
        {"entity_id": "button.unraid_test_stop_array"},
        blocking=True,
    )

    mock_async_unraid_client.stop_array.assert_called_once()


@pytest.mark.usefixtures(
    "mock_unraid_client_class",
    "mock_unraid_websocket_client_class",
)
async def test_parity_check_start_button_press(
    hass: HomeAssistant,
    mock_config_entry,
    mock_async_unraid_client,
) -> None:
    """Test pressing parity check start button."""
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    await hass.services.async_call(
        "button",
        "press",
        {"entity_id": "button.unraid_test_start_parity_check"},
        blocking=True,
    )

    mock_async_unraid_client.start_parity_check.assert_called_once()


@pytest.mark.usefixtures(
    "mock_unraid_client_class",
    "mock_unraid_websocket_client_class",
)
async def test_parity_check_stop_button_press(
    hass: HomeAssistant,
    mock_config_entry,
    mock_async_unraid_client,
) -> None:
    """Test pressing parity check stop button."""
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    await hass.services.async_call(
        "button",
        "press",
        {"entity_id": "button.unraid_test_stop_parity_check"},
        blocking=True,
    )

    mock_async_unraid_client.stop_parity_check.assert_called_once()


@pytest.mark.usefixtures(
    "mock_unraid_client_class",
    "mock_unraid_websocket_client_class",
)
async def test_user_script_button(
    hass: HomeAssistant,
    mock_config_entry,
) -> None:
    """Test user script buttons are created (but disabled by default)."""
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    # User script buttons are created but disabled by default
    # They won't appear in hass.states until enabled
    # Verify other buttons were created properly
    button_entities = [
        entity_id
        for entity_id in hass.states.async_entity_ids("button")
        if entity_id.startswith("button.unraid_")
    ]
    # Should have at least the array and parity check buttons
    assert len(button_entities) >= 4


@pytest.mark.usefixtures(
    "mock_unraid_client_class",
    "mock_unraid_websocket_client_class",
)
async def test_button_entity_icon(
    hass: HomeAssistant,
    mock_config_entry,
) -> None:
    """Test button entity icons."""
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    # Check array button icon
    state = hass.states.get("button.unraid_test_start_array")
    if state:
        assert state.attributes.get("icon") == "mdi:harddisk"

    # Check parity check button icon
    state = hass.states.get("button.unraid_test_start_parity_check")
    if state:
        assert state.attributes.get("icon") == "mdi:shield-check"


@pytest.mark.usefixtures(
    "mock_unraid_client_class",
    "mock_unraid_websocket_client_class",
)
async def test_user_script_button_entity_registry(
    hass: HomeAssistant,
    mock_config_entry,
    mock_async_unraid_client,
) -> None:
    """Test user script buttons are in entity registry."""
    from unittest.mock import MagicMock

    from homeassistant.helpers import entity_registry as er

    # Create mock user scripts
    mock_script1 = MagicMock()
    mock_script1.name = "backup_script"
    mock_script1.description = "Daily backup script"
    mock_script2 = MagicMock()
    mock_script2.name = "cleanup_script"
    mock_script2.description = "Cleanup temporary files"

    # Set up mock to return user scripts
    mock_async_unraid_client.list_user_scripts.return_value = [
        mock_script1,
        mock_script2,
    ]

    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    # Check entity registry for user script buttons (they're disabled by default)
    entity_reg = er.async_get(hass)
    entities = er.async_entries_for_config_entry(entity_reg, mock_config_entry.entry_id)

    # Find user script entities
    user_script_entities = [e for e in entities if "user_script" in e.unique_id]

    # We have 2 user scripts in mock data
    assert len(user_script_entities) == 2


@pytest.mark.usefixtures(
    "mock_unraid_client_class",
    "mock_unraid_websocket_client_class",
)
async def test_array_start_button_error(
    hass: HomeAssistant,
    mock_config_entry,
    mock_async_unraid_client,
) -> None:
    """Test array start button error handling."""
    from homeassistant.exceptions import HomeAssistantError

    mock_async_unraid_client.start_array.side_effect = Exception("Array start failed")

    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    with pytest.raises(HomeAssistantError):
        await hass.services.async_call(
            "button",
            "press",
            {"entity_id": "button.unraid_test_start_array"},
            blocking=True,
        )


@pytest.mark.usefixtures(
    "mock_unraid_client_class",
    "mock_unraid_websocket_client_class",
)
async def test_array_stop_button_error(
    hass: HomeAssistant,
    mock_config_entry,
    mock_async_unraid_client,
) -> None:
    """Test array stop button error handling."""
    from homeassistant.exceptions import HomeAssistantError

    mock_async_unraid_client.stop_array.side_effect = Exception("Array stop failed")

    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    with pytest.raises(HomeAssistantError):
        await hass.services.async_call(
            "button",
            "press",
            {"entity_id": "button.unraid_test_stop_array"},
            blocking=True,
        )


@pytest.mark.usefixtures(
    "mock_unraid_client_class",
    "mock_unraid_websocket_client_class",
)
async def test_parity_check_start_button_error(
    hass: HomeAssistant,
    mock_config_entry,
    mock_async_unraid_client,
) -> None:
    """Test parity check start button error handling."""
    from homeassistant.exceptions import HomeAssistantError

    mock_async_unraid_client.start_parity_check.side_effect = Exception(
        "Parity check start failed"
    )

    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    with pytest.raises(HomeAssistantError):
        await hass.services.async_call(
            "button",
            "press",
            {"entity_id": "button.unraid_test_start_parity_check"},
            blocking=True,
        )


@pytest.mark.usefixtures(
    "mock_unraid_client_class",
    "mock_unraid_websocket_client_class",
)
async def test_parity_check_stop_button_error(
    hass: HomeAssistant,
    mock_config_entry,
    mock_async_unraid_client,
) -> None:
    """Test parity check stop button error handling."""
    from homeassistant.exceptions import HomeAssistantError

    mock_async_unraid_client.stop_parity_check.side_effect = Exception(
        "Parity check stop failed"
    )

    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    with pytest.raises(HomeAssistantError):
        await hass.services.async_call(
            "button",
            "press",
            {"entity_id": "button.unraid_test_stop_parity_check"},
            blocking=True,
        )


# ==================== Unit tests for button classes ====================


async def test_button_entity_no_press_fn() -> None:
    """Test button with no press_fn does nothing."""
    from unittest.mock import MagicMock

    from custom_components.unraid_management_agent.button import (
        UnraidButtonEntity,
        UnraidButtonEntityDescription,
    )

    # Create description with no press_fn
    description = UnraidButtonEntityDescription(
        key="test_button",
        translation_key="test_button",
        icon="mdi:test",
        press_fn=None,
    )

    # Create a mock button entity without full coordinator
    button = object.__new__(UnraidButtonEntity)
    button.entity_description = description
    button.coordinator = MagicMock()

    # Pressing should not raise an error and just return
    await button.async_press()  # Should do nothing


async def test_button_entity_press_fn_called() -> None:
    """Test button with press_fn calls the function."""
    from unittest.mock import AsyncMock, MagicMock

    from custom_components.unraid_management_agent.button import (
        UnraidButtonEntity,
        UnraidButtonEntityDescription,
    )

    # Create a mock press function
    mock_press_fn = AsyncMock()

    description = UnraidButtonEntityDescription(
        key="test_button",
        translation_key="test_button",
        icon="mdi:test",
        press_fn=mock_press_fn,
    )

    button = object.__new__(UnraidButtonEntity)
    button.entity_description = description
    button.coordinator = MagicMock()

    await button.async_press()

    mock_press_fn.assert_called_once_with(button.coordinator)


async def test_button_entity_press_fn_error() -> None:
    """Test button press error raises HomeAssistantError."""
    from unittest.mock import AsyncMock, MagicMock

    from homeassistant.exceptions import HomeAssistantError

    from custom_components.unraid_management_agent.button import (
        UnraidButtonEntity,
        UnraidButtonEntityDescription,
    )

    # Create a mock press function that fails
    mock_press_fn = AsyncMock(side_effect=Exception("Press failed"))

    description = UnraidButtonEntityDescription(
        key="test_button",
        translation_key="test_button",
        icon="mdi:test",
        press_fn=mock_press_fn,
    )

    button = object.__new__(UnraidButtonEntity)
    button.entity_description = description
    button.coordinator = MagicMock()

    with pytest.raises(HomeAssistantError):
        await button.async_press()


async def test_user_script_button_press_success() -> None:
    """Test pressing user script button calls execute_user_script."""
    from unittest.mock import AsyncMock, MagicMock

    from custom_components.unraid_management_agent.button import (
        UnraidUserScriptButton,
    )

    # Create mock script
    mock_script = MagicMock()
    mock_script.name = "test_script"
    mock_script.description = "Test script"

    # Create mock coordinator
    mock_coordinator = MagicMock()
    mock_coordinator.client = MagicMock()
    mock_coordinator.client.execute_user_script = AsyncMock()

    # Create button without full initialization
    button = object.__new__(UnraidUserScriptButton)
    button._script_name = "test_script"
    button._script_description = "Test script"
    button.coordinator = mock_coordinator

    await button.async_press()

    mock_coordinator.client.execute_user_script.assert_called_once_with("test_script")


async def test_user_script_button_press_error() -> None:
    """Test user script button error raises HomeAssistantError."""
    from unittest.mock import AsyncMock, MagicMock

    from homeassistant.exceptions import HomeAssistantError

    from custom_components.unraid_management_agent.button import (
        UnraidUserScriptButton,
    )

    # Create mock coordinator with failing client
    mock_coordinator = MagicMock()
    mock_coordinator.client = MagicMock()
    mock_coordinator.client.execute_user_script = AsyncMock(
        side_effect=Exception("Script failed")
    )

    # Create button without full initialization
    button = object.__new__(UnraidUserScriptButton)
    button._script_name = "failing_script"
    button._script_description = "Script that fails"
    button.coordinator = mock_coordinator

    with pytest.raises(HomeAssistantError):
        await button.async_press()


async def test_user_script_button_extra_attributes() -> None:
    """Test user script button extra_state_attributes."""
    from custom_components.unraid_management_agent.button import (
        UnraidUserScriptButton,
    )

    # Create button without full initialization
    button = object.__new__(UnraidUserScriptButton)
    button._script_name = "my_script"
    button._script_description = "My awesome script"

    attrs = button.extra_state_attributes

    assert attrs["script_name"] == "my_script"
    assert attrs["description"] == "My awesome script"


async def test_user_script_button_extra_attributes_no_description() -> None:
    """Test user script button extra_state_attributes with no description."""
    from custom_components.unraid_management_agent.button import (
        UnraidUserScriptButton,
    )

    # Create button without full initialization
    button = object.__new__(UnraidUserScriptButton)
    button._script_name = "simple_script"
    button._script_description = ""

    attrs = button.extra_state_attributes

    assert attrs["script_name"] == "simple_script"
    assert attrs["description"] == "No description"


@pytest.mark.usefixtures(
    "mock_unraid_client_class",
    "mock_unraid_websocket_client_class",
)
async def test_system_shutdown_button(
    hass: HomeAssistant,
    mock_config_entry,
) -> None:
    """Test system shutdown button is created."""
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    state = hass.states.get("button.unraid_test_shutdown_system")
    assert state is not None
    assert state.attributes.get("icon") == "mdi:power"


@pytest.mark.usefixtures(
    "mock_unraid_client_class",
    "mock_unraid_websocket_client_class",
)
async def test_system_reboot_button(
    hass: HomeAssistant,
    mock_config_entry,
) -> None:
    """Test system reboot button is created."""
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    state = hass.states.get("button.unraid_test_reboot_system")
    assert state is not None
    assert state.attributes.get("icon") == "mdi:restart"


@pytest.mark.usefixtures(
    "mock_unraid_client_class",
    "mock_unraid_websocket_client_class",
)
async def test_system_shutdown_button_press(
    hass: HomeAssistant,
    mock_config_entry,
    mock_async_unraid_client,
) -> None:
    """Test pressing system shutdown button."""
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    await hass.services.async_call(
        "button",
        "press",
        {"entity_id": "button.unraid_test_shutdown_system"},
        blocking=True,
    )

    mock_async_unraid_client.shutdown_system.assert_called_once()


@pytest.mark.usefixtures(
    "mock_unraid_client_class",
    "mock_unraid_websocket_client_class",
)
async def test_system_reboot_button_press(
    hass: HomeAssistant,
    mock_config_entry,
    mock_async_unraid_client,
) -> None:
    """Test pressing system reboot button."""
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    await hass.services.async_call(
        "button",
        "press",
        {"entity_id": "button.unraid_test_reboot_system"},
        blocking=True,
    )

    mock_async_unraid_client.reboot_system.assert_called_once()


@pytest.mark.usefixtures(
    "mock_unraid_client_class",
    "mock_unraid_websocket_client_class",
)
async def test_system_shutdown_button_error(
    hass: HomeAssistant,
    mock_config_entry,
    mock_async_unraid_client,
) -> None:
    """Test system shutdown button error raises HomeAssistantError."""
    mock_async_unraid_client.shutdown_system = AsyncMock(
        side_effect=Exception("Shutdown failed")
    )

    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    with pytest.raises(HomeAssistantError):
        await hass.services.async_call(
            "button",
            "press",
            {"entity_id": "button.unraid_test_shutdown_system"},
            blocking=True,
        )


@pytest.mark.usefixtures(
    "mock_unraid_client_class",
    "mock_unraid_websocket_client_class",
)
async def test_system_reboot_button_error(
    hass: HomeAssistant,
    mock_config_entry,
    mock_async_unraid_client,
) -> None:
    """Test system reboot button error raises HomeAssistantError."""
    mock_async_unraid_client.reboot_system = AsyncMock(
        side_effect=Exception("Reboot failed")
    )

    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    with pytest.raises(HomeAssistantError):
        await hass.services.async_call(
            "button",
            "press",
            {"entity_id": "button.unraid_test_reboot_system"},
            blocking=True,
        )


async def test_button_helper_press_functions() -> None:
    """Test button helper press functions."""
    from custom_components.unraid_management_agent.button import (
        _async_archive_all_notifications,
        _async_clear_array_disk_stats,
        _async_pause_parity_check,
        _async_resume_parity_check,
    )

    coordinator = MagicMock()
    coordinator.client = MagicMock()
    coordinator.client.pause_parity_check = AsyncMock()
    coordinator.client.resume_parity_check = AsyncMock()
    coordinator.client.clear_array_disk_stats = AsyncMock()
    coordinator.client.archive_all_notifications = AsyncMock()
    coordinator.async_request_refresh = AsyncMock()

    await _async_pause_parity_check(coordinator)
    coordinator.client.pause_parity_check.assert_called_once()
    coordinator.async_request_refresh.assert_called_once()

    coordinator.async_request_refresh.reset_mock()
    await _async_resume_parity_check(coordinator)
    coordinator.client.resume_parity_check.assert_called_once()
    coordinator.async_request_refresh.assert_called_once()

    coordinator.async_request_refresh.reset_mock()
    await _async_clear_array_disk_stats(coordinator)
    coordinator.client.clear_array_disk_stats.assert_called_once()
    coordinator.async_request_refresh.assert_called_once()

    coordinator.async_request_refresh.reset_mock()
    await _async_archive_all_notifications(coordinator)
    coordinator.client.archive_all_notifications.assert_called_once()
    coordinator.async_request_refresh.assert_called_once()


async def test_container_restart_button_methods() -> None:
    """Test UnraidContainerRestartButton methods and error handling."""
    from custom_components.unraid_management_agent.button import (
        UnraidContainerRestartButton,
    )

    coordinator = MagicMock()
    coordinator.config_entry.entry_id = "test_entry"
    coordinator.last_update_success = True
    coordinator.client = MagicMock()
    coordinator.client.restart_container = AsyncMock()

    # No data
    coordinator.data = None
    btn = UnraidContainerRestartButton(coordinator, "plex")
    assert btn._find_container() is None
    assert btn.available is False

    # Press when container not found
    await btn.async_press()
    coordinator.client.restart_container.assert_not_called()

    # Container found
    container = MagicMock()
    container.name = "plex"
    container.id = "c123"
    coordinator.data = MagicMock()
    coordinator.data.containers = [container]
    assert btn._find_container() == container
    assert btn.available is True

    # Successful press
    await btn.async_press()
    coordinator.client.restart_container.assert_called_once_with("c123")

    # Error press raises HomeAssistantError
    coordinator.client.restart_container = AsyncMock(side_effect=Exception("API Error"))
    with pytest.raises(HomeAssistantError):
        await btn.async_press()


async def test_vm_buttons_methods() -> None:
    """Test Unraid VM button classes, finding VM and press actions."""
    from custom_components.unraid_management_agent.button import (
        UnraidVMForceStopButton,
        UnraidVMPauseButton,
        UnraidVMResetButton,
        UnraidVMRestartButton,
        UnraidVMResumeButton,
    )

    coordinator = MagicMock()
    coordinator.config_entry.entry_id = "test_entry"
    coordinator.last_update_success = True
    coordinator.client = MagicMock()
    coordinator.client.force_stop_vm = AsyncMock()
    coordinator.client.restart_vm = AsyncMock()
    coordinator.client.pause_vm = AsyncMock()
    coordinator.client.resume_vm = AsyncMock()
    coordinator.client.reset_vm = AsyncMock()

    # No data
    coordinator.data = None
    btn_force = UnraidVMForceStopButton(coordinator, "vm-1", "Windows 11")
    assert btn_force._find_vm() is None
    assert btn_force.available is False

    # VM found by id and name
    vm = MagicMock()
    vm.id = "vm-1"
    vm.name = "Windows 11"
    coordinator.data = MagicMock()
    coordinator.data.vms = [vm]
    assert btn_force._find_vm() == vm
    assert btn_force.available is True

    # Test press and error for force stop
    await btn_force.async_press()
    coordinator.client.force_stop_vm.assert_called_once_with("vm-1")
    coordinator.client.force_stop_vm = AsyncMock(side_effect=Exception("Stop failed"))
    with pytest.raises(HomeAssistantError):
        await btn_force.async_press()

    # Test restart button
    btn_restart = UnraidVMRestartButton(coordinator, "vm-1", "Windows 11")
    await btn_restart.async_press()
    coordinator.client.restart_vm.assert_called_once_with("vm-1")
    coordinator.client.restart_vm = AsyncMock(side_effect=Exception("Restart failed"))
    with pytest.raises(HomeAssistantError):
        await btn_restart.async_press()

    # Test pause button
    btn_pause = UnraidVMPauseButton(coordinator, "vm-1", "Windows 11")
    await btn_pause.async_press()
    coordinator.client.pause_vm.assert_called_once_with("vm-1")
    coordinator.client.pause_vm = AsyncMock(side_effect=Exception("Pause failed"))
    with pytest.raises(HomeAssistantError):
        await btn_pause.async_press()

    # Test resume button
    btn_resume = UnraidVMResumeButton(coordinator, "vm-1", "Windows 11")
    await btn_resume.async_press()
    coordinator.client.resume_vm.assert_called_once_with("vm-1")
    coordinator.client.resume_vm = AsyncMock(side_effect=Exception("Resume failed"))
    with pytest.raises(HomeAssistantError):
        await btn_resume.async_press()

    # Test reset button
    btn_reset = UnraidVMResetButton(coordinator, "vm-1", "Windows 11")
    await btn_reset.async_press()
    coordinator.client.reset_vm.assert_called_once_with("vm-1")
    coordinator.client.reset_vm = AsyncMock(side_effect=Exception("Reset failed"))
    with pytest.raises(HomeAssistantError):
        await btn_reset.async_press()
