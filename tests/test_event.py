"""Tests for the Unraid Management Agent event platform."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from homeassistant.core import HomeAssistant

from custom_components.unraid_management_agent.api.models import (
    Notification,
    NotificationsResponse,
)
from custom_components.unraid_management_agent.coordinator import UnraidData
from custom_components.unraid_management_agent.event import (
    UnraidNotificationEvent,
)


async def test_event_setup_entry(
    hass: HomeAssistant,
    mock_config_entry,
    mock_async_unraid_client,
    mock_websocket_client,
) -> None:
    """Test setting up event platform."""
    with (
        patch(
            "custom_components.unraid_management_agent.UnraidClient",
            return_value=mock_async_unraid_client,
        ),
        patch(
            "custom_components.unraid_management_agent.UnraidWebSocketClient",
            return_value=mock_websocket_client,
        ),
    ):
        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    state = hass.states.get("event.unraid_test_notification")
    assert state is not None


async def test_notification_event_fire_and_deduplicate(
    hass: HomeAssistant,
    mock_config_entry,
) -> None:
    """Test notification events are fired and deduplicated by id."""
    coordinator = MagicMock()
    coordinator.config_entry = mock_config_entry
    coordinator.data = None

    event_entity = UnraidNotificationEvent(coordinator, mock_config_entry)
    event_entity.hass = hass
    event_entity.entity_id = "event.unraid_test_notification"
    event_entity.platform = MagicMock(platform_name="unraid_management_agent")
    event_entity.async_write_ha_state = MagicMock()
    event_entity._trigger_event = MagicMock()

    # Coordinator update with no data
    event_entity._handle_coordinator_update()
    event_entity._trigger_event.assert_not_called()

    # Coordinator update with notifications
    n1 = Notification(
        id="notif_1",
        subject="Array Started",
        description="Array is now online",
        importance="info",
        timestamp="2026-10-09T00:00:00Z",
    )
    n2 = Notification(
        id="notif_2",
        subject="Disk Error",
        description="Disk 1 error count increased",
        importance="alert",
        timestamp="2026-10-09T00:01:00Z",
    )
    n3 = Notification(
        id="notif_3",
        subject="High Temperature",
        description="CPU reached 80C",
        importance="warning",
        timestamp="2026-10-09T00:02:00Z",
    )
    n4 = Notification(
        id="notif_4",
        subject="Custom Notice",
        description="Unknown severity",
        importance="notice",  # fallback to 'info'
        timestamp="2026-10-09T00:03:00Z",
    )

    coordinator.data = UnraidData(
        notifications=NotificationsResponse(notifications=[n1, n2, n3, n4])
    )

    event_entity._handle_coordinator_update()

    assert event_entity._trigger_event.call_count == 4
    event_entity._trigger_event.assert_any_call(
        "info",
        {
            "id": "notif_1",
            "subject": "Array Started",
            "description": "Array is now online",
            "importance": "info",
            "timestamp": "2026-10-09T00:00:00Z",
        },
    )
    event_entity._trigger_event.assert_any_call(
        "alert",
        {
            "id": "notif_2",
            "subject": "Disk Error",
            "description": "Disk 1 error count increased",
            "importance": "alert",
            "timestamp": "2026-10-09T00:01:00Z",
        },
    )
    event_entity._trigger_event.assert_any_call(
        "warning",
        {
            "id": "notif_3",
            "subject": "High Temperature",
            "description": "CPU reached 80C",
            "importance": "warning",
            "timestamp": "2026-10-09T00:02:00Z",
        },
    )
    event_entity._trigger_event.assert_any_call(
        "info",
        {
            "id": "notif_4",
            "subject": "Custom Notice",
            "description": "Unknown severity",
            "importance": "notice",
            "timestamp": "2026-10-09T00:03:00Z",
        },
    )

    # Subsequent update with same notifications should not re-trigger
    event_entity._trigger_event.reset_mock()
    event_entity._handle_coordinator_update()
    event_entity._trigger_event.assert_not_called()
