"""Test the per-update lookup caches."""

from __future__ import annotations

from custom_components.unraid_management_agent.api.models import CollectorStatus
from custom_components.unraid_management_agent.update import _plugins_by_name
from custom_components.unraid_management_agent.util import cached_slugify


def test_cached_slugify_matches_slugify_and_caches() -> None:
    """The cached slug equals the plain slug and repeat calls hit the cache."""
    cached_slugify.cache_clear()
    assert cached_slugify("My Disk 1") == "my_disk_1"
    assert cached_slugify("My Disk 1") == "my_disk_1"
    assert cached_slugify.cache_info().hits == 1


def test_collector_lookup_is_case_insensitive_and_first_wins() -> None:
    """The first collector of a name wins; unnamed ones and unknown names give None."""
    status = CollectorStatus.model_validate(
        {
            "collectors": [
                {"name": "Docker", "enabled": True},
                {"name": "docker", "enabled": False},
                {"enabled": True},
            ]
        }
    )
    found = status.get_collector_by_name("DOCKER")
    assert found is not None
    assert found.enabled is True
    assert status.get_collector_by_name("vm") is None
    assert CollectorStatus().get_collector_by_name("docker") is None


def test_plugin_lookup_first_wins() -> None:
    """Two plugins with one name resolve to the first."""

    class Plugin:
        def __init__(self, name: str, version: str) -> None:
            self.name = name
            self.version = version

    plugins = [Plugin("a", "1"), Plugin("a", "2"), Plugin("b", "3")]
    by_name = _plugins_by_name(plugins)
    assert by_name["a"].version == "1"
    assert by_name["b"].version == "3"
    assert _plugins_by_name(plugins) is by_name
