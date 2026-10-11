"""
Helpers for NUT (Network UPS Tools) devices beyond the primary UPS.

The primary UPS keeps its original ``ups_*`` entities, which read ``/ups``.
Every other NUT device the agent reports in ``/nut`` ``statuses`` (a second
UPS, an ATS, ...) gets its own ``nut_<device>_*`` entities.
"""

from __future__ import annotations

import hashlib
from collections.abc import Iterable
from typing import TYPE_CHECKING, Final

from homeassistant.core import HomeAssistant, callback
from homeassistant.util import slugify

from .hwmon import async_adopt_unique_id

if TYPE_CHECKING:
    from .api.models import NUTDeviceStatus
    from .coordinator import UnraidData

NUT_KEY_PREFIX: Final = "nut_"

# Suffixes of the per-device entity keys: nut_<device>_<suffix>
NUT_SENSOR_SUFFIXES: Final = ("battery", "load", "runtime", "power", "energy")
NUT_BINARY_SENSOR_SUFFIXES: Final = ("connected",)


def nut_device_key(device_name: str) -> str:
    """
    Return the entity key prefix for a NUT device, e.g. ``nut_ups-1a2b3c4d``.

    NUT device names are case-sensitive and may contain ``-`` and ``.``, which
    slugify folds together (``UPS`` and ``ups``, ``ups-gpu`` and ``ups_gpu``).
    The key is the slug plus a hash of the exact name after a ``-``, so two
    different names never share a key, and no key equals the slug-only key of
    earlier versions (see nut_legacy_unique_ids).
    """
    digest = hashlib.sha256(device_name.encode()).hexdigest()[:8]
    return f"{NUT_KEY_PREFIX}{slugify(device_name)}-{digest}"


def nut_legacy_unique_ids(
    entry_id: str, device_name: str, suffix: str, device_names: Iterable[str]
) -> list[str]:
    """
    Return the unique ID an entity had under the slug-only key used before.

    Earlier versions keyed a device by ``nut_<slug>`` alone. That old ID is
    only offered when no other current device (the primary UPS included, see
    all_nut_device_names) has the same slug, since it cannot say which of them
    it was.
    """
    slug = slugify(device_name)
    if any(other != device_name and slugify(other) == slug for other in device_names):
        return []
    return [f"{entry_id}_{NUT_KEY_PREFIX}{slug}_{suffix}"]


def _primary_nut_device_name(data: UnraidData) -> str | None:
    """
    Return the NUT device that the ``ups_*`` entities already cover.

    That is the device ``/ups`` reports (``device_name``). Without a device
    name, ``/ups`` comes from apcupsd or an older agent, so no NUT device is
    covered. Without ``/ups`` data at all, the first listed NUT device is
    assumed to be the primary, as the agent's ``/ups`` and ``status`` use it;
    the first status is only used when there is no device list. If ``/ups``
    really comes from apcupsd, that device's entities are only delayed until
    ``/ups`` answers again (discovery runs on every update), which is better
    than giving the usual NUT-only primary duplicate entities to remove later.
    """
    if data.ups is not None:
        return data.ups.device_name
    if data.nut is not None and data.nut.devices:
        return data.nut.devices[0].name
    if data.nut is not None and data.nut.statuses:
        return data.nut.statuses[0].device_name
    return None


def secondary_nut_statuses(
    data: UnraidData | None,
) -> list[tuple[str, NUTDeviceStatus]]:
    """Return (name, status) of every NUT device other than the primary UPS."""
    if data is None or data.nut is None or not data.nut.statuses:
        return []
    primary = _primary_nut_device_name(data)
    return [
        (status.device_name, status)
        for status in data.nut.statuses
        if status.device_name and status.device_name != primary
    ]


def secondary_nut_device_names(data: UnraidData) -> set[str]:
    """
    Return the NUT devices whose ``nut_*`` entities cleanup keeps.

    Uses the device list (``upsc -l``) as well as the statuses, so a device
    that misses one query is still known and its entities are kept. Only the
    device ``/ups`` reports is left out; without ``/ups`` data the primary is
    not certain (``/ups`` may come from apcupsd), so every device is kept.
    """
    names = all_nut_device_names(data)
    if data.ups is None:
        return names
    return names - {data.ups.device_name}


def listed_secondary_nut_devices(data: UnraidData | None) -> list[str]:
    """
    Return every listed NUT device other than the primary UPS, sorted.

    A device that does not answer is included: it gets a ``Connected`` binary
    sensor that shows it as disconnected. Older agents (no ``statuses``) get
    none.
    """
    if data is None or data.nut is None or data.nut.statuses is None:
        return []
    primary = _primary_nut_device_name(data)
    return sorted(name for name in all_nut_device_names(data) if name != primary)


@callback
def async_move_legacy_nut_entities(
    hass: HomeAssistant, entry_id: str, data: UnraidData | None
) -> None:
    """
    Move entities keyed ``nut_<slug>_*`` by earlier builds to the hashed keys.

    Covers the devices whose keys cleanup keeps (secondary_nut_device_names),
    whether or not they answer or report a reading, so cleanup never sees the
    old key of a listed device. Only registry entries move; no entity is
    created. Both platforms call this before adding entities, so no entity
    takes a new key before the old entity has moved to it.
    """
    if data is None:
        return
    names = all_nut_device_names(data)
    for name in sorted(secondary_nut_device_names(data)):
        prefix = nut_device_key(name)
        for domain, suffixes in (
            ("sensor", NUT_SENSOR_SUFFIXES),
            ("binary_sensor", NUT_BINARY_SENSOR_SUFFIXES),
        ):
            for suffix in suffixes:
                async_adopt_unique_id(
                    hass,
                    domain,
                    f"{entry_id}_{prefix}_{suffix}",
                    nut_legacy_unique_ids(entry_id, name, suffix, names),
                )


def all_nut_device_names(data: UnraidData | None) -> set[str]:
    """Return every NUT device name the agent reports, the primary UPS included."""
    if data is None or data.nut is None:
        return set()
    names = {d.name for d in data.nut.devices or [] if d.name}
    names.update(s.device_name for s in data.nut.statuses or [] if s.device_name)
    return names


def find_nut_status(
    data: UnraidData | None, device_name: str
) -> NUTDeviceStatus | None:
    """Return the current status of a NUT device, or None if it did not answer."""
    if data is None or data.nut is None:
        return None
    return next(
        (s for s in data.nut.statuses or [] if s.device_name == device_name), None
    )
