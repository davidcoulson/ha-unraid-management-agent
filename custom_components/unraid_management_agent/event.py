"""Event platform for Unraid Management Agent — notification and alert events."""

from __future__ import annotations

import logging
from typing import Any, ClassVar

from homeassistant.components.event import EventEntity
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import UnraidConfigEntry
from .alerts import ALERT_STATE_FIRING, alert_since
from .api.models import AlertStatus
from .coordinator import UnraidDataUpdateCoordinator
from .entity import UnraidBaseEntity

_LOGGER = logging.getLogger(__name__)

PARALLEL_UPDATES = 0


async def async_setup_entry(
    hass: HomeAssistant,
    entry: UnraidConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Unraid event entities."""
    coordinator = entry.runtime_data.coordinator
    async_add_entities([UnraidNotificationEvent(coordinator, entry)])

    # The alert event entity is added once the agent reports alert status, so
    # older agents without the alerting engine don't get an entity that never
    # fires, and an agent upgraded later gets it without a reload.
    alert_event_added = False

    @callback
    def _add_alert_event() -> None:
        nonlocal alert_event_added
        data = coordinator.data
        if alert_event_added or not data or data.alert_statuses is None:
            return
        alert_event_added = True
        async_add_entities([UnraidAlertEvent(coordinator)])

    _add_alert_event()
    entry.async_on_unload(coordinator.async_add_listener(_add_alert_event))


class UnraidNotificationEvent(UnraidBaseEntity, EventEntity):
    """Event entity that fires when Unraid notifications arrive."""

    _attr_translation_key = "notification_event"
    _attr_event_types: ClassVar[list[str]] = ["info", "warning", "alert"]
    _attr_icon = "mdi:bell-ring"

    def __init__(
        self,
        coordinator: UnraidDataUpdateCoordinator,
        entry: UnraidConfigEntry,
    ) -> None:
        """Initialize the event entity."""
        super().__init__(coordinator, "notification_event")
        self._seen_ids: set[str] = set()

    @callback
    def _handle_coordinator_update(self) -> None:
        """Fire an HA event for each new Unraid notification."""
        data = self.coordinator.data
        if not data or not data.notifications:
            super()._handle_coordinator_update()
            return

        notifications_response = data.notifications
        notif_list = getattr(notifications_response, "notifications", None) or []

        new_notifications = [
            n for n in notif_list if n.id and n.id not in self._seen_ids
        ]

        if new_notifications:
            for notif in new_notifications:
                if notif.id:
                    self._seen_ids.add(notif.id)
                importance = (notif.importance or "info").lower()
                event_type = (
                    importance if importance in self._attr_event_types else "info"
                )
                event_data: dict[str, Any] = {}
                if notif.id:
                    event_data["id"] = notif.id
                if notif.subject:
                    event_data["subject"] = notif.subject
                if notif.description:
                    event_data["description"] = notif.description
                if notif.importance:
                    event_data["importance"] = notif.importance
                if notif.timestamp:
                    event_data["timestamp"] = notif.timestamp
                self._trigger_event(event_type, event_data)

        super()._handle_coordinator_update()


def _firing_rule_ids(statuses: list[AlertStatus]) -> set[str]:
    """Return the IDs of the rules that are firing."""
    return {
        status.rule_id
        for status in statuses
        if status.rule_id and status.state == ALERT_STATE_FIRING
    }


class UnraidAlertEvent(UnraidBaseEntity, EventEntity):
    """
    Event entity that fires when an agent alert rule starts firing or resolves.

    Transitions are found by comparing each rule's state with the previous
    poll. A rule that fires and resolves between two polls (30 seconds) is not
    seen, and a rule that is disabled or deleted while firing does not resolve.
    """

    _attr_translation_key = "alert_event"
    _attr_event_types: ClassVar[list[str]] = ["firing", "resolved"]

    def __init__(self, coordinator: UnraidDataUpdateCoordinator) -> None:
        """Initialize the event entity with the rules' current states."""
        super().__init__(coordinator, "alert_event")
        # Rules already firing when the entity is created are not new events
        data = coordinator.data
        self._firing: set[str] | None = (
            _firing_rule_ids(data.alert_statuses)
            if data and data.alert_statuses is not None
            else None
        )

    @callback
    def _handle_coordinator_update(self) -> None:
        """Fire an event for each rule that started firing or resolved."""
        data = self.coordinator.data
        statuses = data.alert_statuses if data else None
        if statuses is None:
            # Alert status unavailable this cycle; keep the last known states
            super()._handle_coordinator_update()
            return

        previous = self._firing
        firing = _firing_rule_ids(statuses)
        self._firing = firing
        if previous is not None:
            for status in statuses:
                rule_id = status.rule_id
                if rule_id and (rule_id in firing) != (rule_id in previous):
                    self._fire_alert_event(status, rule_id, rule_id in firing)

        super()._handle_coordinator_update()

    def _fire_alert_event(
        self, status: AlertStatus, rule_id: str, firing: bool
    ) -> None:
        """Trigger a firing or resolved event for one rule."""
        event_data: dict[str, Any] = {
            "rule_id": rule_id,
            "rule_name": status.rule_name or rule_id,
        }
        if status.severity:
            event_data["severity"] = status.severity
        since = alert_since(status)
        if firing and since is not None:
            event_data["since"] = since.isoformat()
        self._trigger_event("firing" if firing else "resolved", event_data)
        # Write each event so two transitions in one poll are both recorded
        self.async_write_ha_state()
