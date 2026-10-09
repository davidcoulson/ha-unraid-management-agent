"""Test ZFS pool usage parsing."""

from __future__ import annotations

from custom_components.unraid_management_agent.api.models import ZFSPool


def test_zfs_pool_usage_from_allocated_bytes() -> None:
    """The agent reports pool usage as allocated_bytes (zpool ALLOC)."""
    pool = ZFSPool.model_validate(
        {"name": "tank", "size_bytes": 400, "allocated_bytes": 100, "free_bytes": 300}
    )
    assert pool.used_bytes == 100
    assert pool.computed_used_percent == 25.0


def test_zfs_pool_usage_from_used_bytes() -> None:
    """used_bytes still works for agents that send it."""
    pool = ZFSPool(name="tank", size_bytes=400, used_bytes=200)
    assert pool.computed_used_percent == 50.0
