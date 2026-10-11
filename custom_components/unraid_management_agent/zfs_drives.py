"""
Drive health aggregates for ZFS pool devices.

The agent (2026.10+) lists each pool's leaf members with the whole disk they
are on and that disk's SMART summary. These helpers roll the members up into
per-pool values (hottest drive, worst NVMe wear, media errors, failing
drives) and per-drive details. Serial numbers are never reported by the
agent, so they cannot leak into attributes.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from .api.models import DriveHealth, StorageTopology, ZFSDrive, ZFSPool


def _label(drive: ZFSDrive) -> str | None:
    """Return the name used for a drive in attributes (its disk, else member)."""
    return drive.disk or drive.name


def _healthy_rows(pool: ZFSPool) -> list[tuple[ZFSDrive, DriveHealth]]:
    """Return the members that have a SMART reading."""
    return [(d, d.health) for d in pool.drives or [] if d.health is not None]


def hottest_drive(pool: ZFSPool) -> tuple[int | None, dict[str, Any]]:
    """
    Return the highest temperature among awake drives and which drive it is.

    Drives in standby are skipped: their last reading is from before they
    spun down. None when no awake drive reports a temperature.
    """
    rows = [
        (d, h.temperature_celsius)
        for d, h in _healthy_rows(pool)
        if not h.standby and h.temperature_celsius is not None
    ]
    if not rows:
        return None, {}
    drive, temp = max(rows, key=lambda row: row[1])
    return temp, {"drive": _label(drive)}


def worst_wear(pool: ZFSPool) -> tuple[int | None, dict[str, Any]]:
    """Return the highest NVMe "percentage used" and which drive it is."""
    rows = [
        (d, h.percentage_used)
        for d, h in _healthy_rows(pool)
        if h.percentage_used is not None
    ]
    if not rows:
        return None, {}
    drive, wear = max(rows, key=lambda row: row[1])
    return wear, {"drive": _label(drive)}


def has_wear(pool: ZFSPool) -> bool:
    """Return True when any member reports NVMe wear."""
    return any(h.percentage_used is not None for _, h in _healthy_rows(pool))


def media_errors(pool: ZFSPool) -> tuple[int | None, dict[str, Any]]:
    """Return the media errors summed over members, and the drives that have any."""
    rows = [
        (d, h.media_errors)
        for d, h in _healthy_rows(pool)
        if h.media_errors is not None
    ]
    if not rows:
        return None, {}
    with_errors = {_label(d): n for d, n in rows if n}
    return sum(n for _, n in rows), ({"drives": with_errors} if with_errors else {})


def failing_drives(pool: ZFSPool) -> tuple[int | None, dict[str, Any]]:
    """
    Return how many members fail SMART or have an NVMe critical warning.

    None when the agent reported no drive health for the pool at all.
    """
    rows = _healthy_rows(pool)
    if not rows:
        return None, {}
    failing = [_label(d) for d, h in rows if h.is_failing]
    return len(failing), ({"drives": failing} if failing else {})


# Keys of the per-pool drive roll-up sensors (unique ID: zfs_<pool>_<key>).
ROLL_UP_KEYS: tuple[str, ...] = (
    "drive_count",
    "drive_max_temperature",
    "drive_max_wear",
    "drive_media_errors",
    "drives_failing",
)


def roll_up_keys(pool: ZFSPool) -> list[str]:
    """
    Return the roll-up sensors to create for a pool.

    None without member drives (an agent older than 2026.10), and no wear
    sensor until a member reports NVMe wear.
    """
    if pool.drives is None:
        return []
    return [key for key in ROLL_UP_KEYS if key != "drive_max_wear" or has_wear(pool)]


def _has_nvme(pool: ZFSPool) -> bool:
    """Return True when any member is an NVMe drive, with or without a reading."""
    return any(
        (d.disk or "").startswith("nvme")
        or (d.health is not None and d.health.media_type == "nvme")
        for d in pool.drives or []
    )


def retained_roll_up_keys(pool: ZFSPool) -> list[str]:
    """
    Return the roll-up sensors stale cleanup must keep for a pool.

    Wider than roll_up_keys(), so a gap in SMART data never deletes an entity
    (and its customizations): the wear sensor stays while the pool has NVMe
    members, and every roll-up stays while the pool's status could not be
    read (no vdevs and no drives). They go when they no longer apply: the
    agent stops reporting members (rollback), the NVMe members are replaced,
    the pool is removed or the option is turned off.
    """
    if pool.drives is None:
        return list(ROLL_UP_KEYS) if pool.vdevs is None else []
    keys = roll_up_keys(pool)
    if "drive_max_wear" not in keys and _has_nvme(pool):
        keys.append("drive_max_wear")
    return keys


def drive_locations(
    topology: StorageTopology | None,
) -> dict[str, tuple[str, int]]:
    """
    Map disk names to the enclosure and slot they sit in.

    Uses the storage topology's drive list, which the agent matches to Linux
    block devices. Drives behind controllers without topology support (for
    example NVMe on a PCIe switch card) have no location.
    """
    # Imported here: storage imports cleanup, which imports this module.
    from .storage import enclosure_name

    if topology is None:
        return {}
    by_id = {e.id: e for e in topology.enclosures or []}
    by_eid = {
        (e.controller_index, e.enclosure_device_id): e
        for e in topology.enclosures or []
        if e.enclosure_device_id is not None
    }
    locations: dict[str, tuple[str, int]] = {}
    for drive in topology.drives or []:
        if not drive.device:
            continue
        enclosure = by_id.get(drive.enclosure_id or "") or by_eid.get(
            (drive.controller_index, drive.enclosure_device_id)
        )
        if enclosure is not None:
            locations[drive.device] = (enclosure_name(enclosure), drive.slot)
    return locations


def drive_details(
    pool: ZFSPool, locations: dict[str, tuple[str, int]]
) -> list[dict[str, Any]]:
    """Return one dict per member: identity, health values and location."""
    details: list[dict[str, Any]] = []
    for drive in pool.drives or []:
        row: dict[str, Any] = {"name": drive.name, "disk": drive.disk}
        if drive.vdev:
            row["vdev"] = drive.vdev
        row["state"] = drive.state
        health = drive.health
        if health is not None:
            values = {
                "model": health.model,
                "media_type": health.media_type,
                "temperature": health.temperature_celsius,
                "percentage_used": health.percentage_used,
                "power_on_hours": health.power_on_hours,
                "media_errors": health.media_errors,
                "smart_passed": health.smart_passed,
            }
            row.update({k: v for k, v in values.items() if v is not None})
            if health.critical_warning:
                row["critical_warning"] = health.critical_warning
            if health.standby:
                row["standby"] = True
        location = locations.get(drive.disk or "")
        if location is not None:
            row["enclosure"], row["slot"] = location
        details.append(row)
    return details
