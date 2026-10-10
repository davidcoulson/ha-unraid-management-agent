"""
Keep hwmon sensors (temperatures, fans) on their entities when their keys change.

USB HID sensor chips (Aquacomputer Octo, Corsair Commander, ...) used to be
keyed by their lm-sensors address, which changes on every USB reconnect, or by
their driver name only, which two identical controllers share. Newer agents
report a device_id (USB serial or port) for them. When a sensor's key moves to
the device-based form, its existing registry entry is given the new unique ID
so the entity keeps its entity ID, name, area and enabled state.
"""

from __future__ import annotations

import logging
import re
from typing import Any

from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import entity_registry as er
from homeassistant.util import slugify

from .api.models import FanInfo, TemperatureInfo
from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)


@callback
def async_adopt_unique_id(
    hass: HomeAssistant, domain: str, target: str, candidates: list[str]
) -> None:
    """Give the first existing candidate entity the target unique ID, if free."""
    registry = er.async_get(hass)
    if registry.async_get_entity_id(domain, DOMAIN, target):
        return
    for candidate in candidates:
        if candidate == target:
            continue
        entity_id = registry.async_get_entity_id(domain, DOMAIN, candidate)
        if entity_id is None:
            continue
        registry.async_update_entity(entity_id, new_unique_id=target)
        _LOGGER.info("Moved %s from unique ID %s to %s", entity_id, candidate, target)
        return


def _registry_matches(
    hass: HomeAssistant, entry_id: str, pattern: re.Pattern[str]
) -> list[str]:
    """Return matching sensor unique IDs of the entry, enabled entities first."""
    registry = er.async_get(hass)
    entries = [
        entity
        for entity in er.async_entries_for_config_entry(registry, entry_id)
        if entity.domain == "sensor" and pattern.match(entity.unique_id)
    ]
    entries.sort(key=lambda entity: entity.disabled_by is not None)
    return [entity.unique_id for entity in entries]


def temperature_legacy_unique_ids(
    hass: HomeAssistant,
    entry_id: str,
    reading: TemperatureInfo,
    readings: list[TemperatureInfo],
) -> list[str]:
    """
    Return earlier unique IDs a USB HID temperature channel may be stored under.

    The channel's own address-based ID first. The driver-only ID and IDs at
    other addresses could belong to any controller of that model, so they are
    only offered when this is the only one present.
    """
    hid_chip = reading.hwmon_hid_chip
    feature = reading.hwmon_feature
    if not hid_chip or not feature:
        return []
    prefix = f"{entry_id}_temperature_"
    ids = [f"{prefix}{slugify(reading.hwmon_address_key or '')}"]
    same_model = {
        other.source
        for other in readings
        if other.hwmon_hid_chip == hid_chip and other.hwmon_feature == feature
    }
    if len(same_model) == 1:
        chip = slugify(hid_chip)
        ids.append(f"{prefix}{chip}_{feature}")
        ids.extend(
            _registry_matches(
                hass,
                entry_id,
                re.compile(
                    re.escape(f"{prefix}{chip}_")
                    + r"\d+_[0-9a-f]+_"
                    + re.escape(feature)
                    + "$"
                ),
            )
        )
    return ids


def fan_legacy_unique_ids(entry_id: str, fan: Any, fans: list[Any]) -> list[str]:
    """
    Return the name-based unique ID a device-keyed fan was stored under.

    Only when this is the only controller of its model: the name-based ID
    ('octo_fan8') does not say which of two identical controllers it was.
    """
    if not isinstance(fan, FanInfo) or not fan.device_key or not fan.chip_short:
        return []
    chip = fan.chip_short
    devices = {
        other.device_id
        for other in fans
        if isinstance(other, FanInfo) and other.chip_short == chip
    }
    if len(devices) != 1:
        return []
    channel = (fan.name or "").rsplit("_", 1)[-1]
    return [f"{entry_id}_fan_{chip}_{channel}".lower()]
