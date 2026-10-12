"""Tests for the formatting helpers."""

from __future__ import annotations

from custom_components.unraid_management_agent.api.formatting import format_bytes


def test_format_bytes_defaults():
    """Values pick their own unit by default."""
    assert format_bytes(4000000000000) == "3.6 TB"
    assert format_bytes(536870912) == "512.0 MB"
    assert format_bytes(1024, precision=0) == "1 KB"


def test_format_bytes_unit_of():
    """unit_of shows the value in the reference value's unit."""
    total = 80 * 1024**4
    assert format_bytes(431_000_000, unit_of=total) == "0.0 TB"
    assert format_bytes(431_000_000, unit_of=total) == format_bytes(
        432_000_000, unit_of=total
    )
    assert format_bytes(40 * 1024**4, unit_of=total) == "40.0 TB"
    # No reference falls back to the value's own unit
    assert format_bytes(5, unit_of=0) == "5.0 B"
