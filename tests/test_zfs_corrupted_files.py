"""Test ZFS pool corrupted files parsing and the Corrupted Files sensor."""

from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock

import pytest

from custom_components.unraid_management_agent.api.events import (
    ZFSPoolUpdateEvent,
    parse_event,
)
from custom_components.unraid_management_agent.api.models import ZFSPool
from custom_components.unraid_management_agent.sensor import (
    ZFS_CORRUPTED_FILES_ATTR_LIMIT,
    UnraidZFSPoolCorruptedFilesSensor,
)

# The forms zpool_obj_to_path() in OpenZFS prints under "errors: Permanent
# errors have been detected in the following files:" in `zpool status -v`.
CORRUPTED_PATHS = [
    "/mnt/tank/media/movie.mkv",
    "<metadata>:<0x1a>",
    "tank/appdata:<0x2f1>",
    "tank/backups:/2026/09/db.dump",
    "<0x5f>:<0x3>",
]


def _agent_pool(**overrides: Any) -> dict[str, Any]:
    """Return a pool as the agent's /zfs/pools endpoint sends it."""
    return {
        "name": "tank",
        "state": "ONLINE",
        "health": "ONLINE",
        "size_bytes": 400,
        "allocated_bytes": 100,
        "free_bytes": 300,
        **overrides,
    }


@pytest.mark.parametrize(
    ("value", "expected", "count", "paths"),
    [
        (CORRUPTED_PATHS, CORRUPTED_PATHS, 5, CORRUPTED_PATHS),
        ([], [], 0, []),
        (["/mnt/tank/a", None, 7], ["/mnt/tank/a", "7"], 2, ["/mnt/tank/a", "7"]),
        (("/mnt/tank/a",), ["/mnt/tank/a"], 1, ["/mnt/tank/a"]),
        (3, 3, 3, []),
        ("2", 2, 2, []),
        (None, None, None, []),
        (True, None, None, []),
        ({"unexpected": 1}, None, None, []),
    ],
)
def test_zfs_pool_corrupted_files_types(
    value: Any, expected: Any, count: int | None, paths: list[str]
) -> None:
    """Path lists from the agent, legacy counts and junk all validate."""
    pool = ZFSPool.model_validate(_agent_pool(corrupted_files=value))
    assert pool.corrupted_files == expected
    assert pool.corrupted_file_count == count
    assert pool.corrupted_file_paths == paths


def test_zfs_pool_corrupted_files_absent() -> None:
    """The agent omits corrupted_files when a pool has no permanent errors."""
    pool = ZFSPool.model_validate(_agent_pool())
    assert pool.corrupted_files is None
    assert pool.corrupted_file_count is None
    assert pool.corrupted_file_paths == []


def test_zfs_pool_update_event_with_corrupted_files() -> None:
    """A pool with corrupted files no longer fails the whole pool list."""
    event = parse_event(
        [
            _agent_pool(name="tank", corrupted_files=CORRUPTED_PATHS),
            _agent_pool(name="cache"),
        ]
    )
    assert isinstance(event, ZFSPoolUpdateEvent)
    assert [pool.name for pool in event.data] == ["tank", "cache"]
    assert event.data[0].corrupted_file_count == 5
    assert event.data[1].corrupted_file_count is None


def _sensor(pools: list[ZFSPool] | None) -> UnraidZFSPoolCorruptedFilesSensor:
    coordinator = MagicMock()
    if pools is None:
        coordinator.data = None
    else:
        coordinator.data = MagicMock()
        coordinator.data.zfs_pools = pools
    entry = MagicMock()
    entry.entry_id = "test_entry"
    return UnraidZFSPoolCorruptedFilesSensor(coordinator, entry, "tank")


def test_zfs_corrupted_files_sensor_counts_paths() -> None:
    """The state is the number of files and the paths are an attribute."""
    sensor = _sensor(
        [ZFSPool.model_validate(_agent_pool(corrupted_files=CORRUPTED_PATHS))]
    )
    assert sensor.native_value == 5
    assert sensor.extra_state_attributes == {"files": CORRUPTED_PATHS}


def test_zfs_corrupted_files_sensor_truncates_paths() -> None:
    """Only the first paths are exposed; the state is still the full count."""
    paths = [f"/mnt/tank/file{i}.bin" for i in range(250)]
    sensor = _sensor([ZFSPool.model_validate(_agent_pool(corrupted_files=paths))])
    assert sensor.native_value == 250
    assert sensor.extra_state_attributes == {
        "files": paths[:ZFS_CORRUPTED_FILES_ATTR_LIMIT]
    }
    assert "files" in sensor._unrecorded_attributes


@pytest.mark.parametrize(
    ("pool", "value"),
    [
        (_agent_pool(corrupted_files=2), 2),
        (_agent_pool(corrupted_files=[]), 0),
        (_agent_pool(), None),
    ],
)
def test_zfs_corrupted_files_sensor_without_paths(
    pool: dict[str, Any], value: int | None
) -> None:
    """A count, an empty list or a missing field exposes no paths."""
    sensor = _sensor([ZFSPool.model_validate(pool)])
    assert sensor.native_value == value
    assert sensor.extra_state_attributes == {}


@pytest.mark.parametrize(
    "pools", [None, [], [ZFSPool.model_validate(_agent_pool(name="other"))]]
)
def test_zfs_corrupted_files_sensor_pool_missing(
    pools: list[ZFSPool] | None,
) -> None:
    """Without data for the pool there is no value and no attributes."""
    sensor = _sensor(pools)
    assert sensor.native_value is None
    assert sensor.extra_state_attributes == {}
