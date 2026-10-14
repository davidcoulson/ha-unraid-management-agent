"""Test parity support on servers with and without Unraid array disks."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ServiceValidationError
from homeassistant.helpers import entity_registry as er

from custom_components.unraid_management_agent import PARITY_ENTITY_KEYS
from custom_components.unraid_management_agent.api.models import (
    ParityCheckRecord,
    ParityHistory,
    ParitySchedule,
)
from custom_components.unraid_management_agent.const import DOMAIN
from custom_components.unraid_management_agent.coordinator import (
    UnraidData,
    array_disks_absent,
    has_no_array_disks,
)

from .const import mock_array_status

PARITY_SERVICES = (
    ("parity_check_start", "start_parity_check"),
    ("parity_check_stop", "stop_parity_check"),
    ("parity_check_pause", "pause_parity_check"),
    ("parity_check_resume", "resume_parity_check"),
)

# Entities the default fixtures create on a server with a parity array
# (schedule/history are None in the fixtures, so those sensors are absent).
CREATED_PARITY_KEYS = (
    ("sensor", "parity_progress"),
    ("binary_sensor", "parity_check_running"),
    ("binary_sensor", "parity_valid"),
    ("button", "parity_check_start"),
    ("button", "parity_check_stop"),
    ("button", "parity_check_pause"),
    ("button", "parity_check_resume"),
)


def _pool_only_array() -> MagicMock:
    """Array status as reported by a ZFS-only server (mdNumDisks=0)."""
    array = mock_array_status()
    array.num_disks = 0
    array.num_data_disks = 0
    array.num_parity_disks = 0
    array.parity_valid = None
    return array


@pytest.fixture
def pool_only_client(mock_async_unraid_client: MagicMock) -> MagicMock:
    """Client for a server without Unraid array disks."""
    mock_async_unraid_client.get_array_status.return_value = _pool_only_array()
    return mock_async_unraid_client


def _entity_id(hass: HomeAssistant, entry_id: str, domain: str, key: str) -> str | None:
    return er.async_get(hass).async_get_entity_id(domain, DOMAIN, f"{entry_id}_{key}")


def _array(**counts: int | None) -> MagicMock:
    array = MagicMock()
    for name in ("num_data_disks", "num_parity_disks"):
        setattr(array, name, counts.get(name))
    return array


@pytest.mark.parametrize(
    ("data", "expected"),
    [
        (None, False),
        (UnraidData(), False),
        (UnraidData(array=_array(num_data_disks=0, num_parity_disks=0)), True),
        (UnraidData(array=_array(num_data_disks=3, num_parity_disks=1)), False),
        # Data disks without parity still support read-checks
        (UnraidData(array=_array(num_data_disks=3, num_parity_disks=0)), False),
        # Unknown counts never hide parity support
        (UnraidData(array=_array(num_data_disks=None, num_parity_disks=None)), False),
        (UnraidData(array=_array(num_data_disks=0, num_parity_disks=None)), False),
    ],
)
def test_has_no_array_disks(data: UnraidData | None, expected: bool) -> None:
    """Only explicit zero data and parity disk counts mean a pool-only server."""
    assert has_no_array_disks(data) is expected


@pytest.mark.parametrize(
    ("data", "expected"),
    [
        (None, None),
        (UnraidData(), None),
        (UnraidData(array=_array(num_data_disks=0, num_parity_disks=None)), None),
        (UnraidData(array=_array(num_data_disks=0, num_parity_disks=0)), True),
        (UnraidData(array=_array(num_data_disks=3, num_parity_disks=0)), False),
    ],
)
def test_array_disks_absent(data: UnraidData | None, expected: bool | None) -> None:
    """Missing array data or counts are reported as unknown."""
    assert array_disks_absent(data) is expected


@pytest.mark.usefixtures("mock_unraid_websocket_client_class")
async def test_parity_entities_created_with_parity_array(
    hass: HomeAssistant,
    mock_config_entry,
    mock_async_unraid_client,
) -> None:
    """Servers with a parity array keep every parity entity."""
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    for domain, key in CREATED_PARITY_KEYS:
        entity_id = _entity_id(hass, mock_config_entry.entry_id, domain, key)
        assert entity_id is not None, key
        assert hass.states.get(entity_id) is not None, key


@pytest.mark.usefixtures("pool_only_client", "mock_unraid_websocket_client_class")
async def test_parity_entities_not_created_without_array_disks(
    hass: HomeAssistant,
    mock_config_entry,
) -> None:
    """Pool-only servers get no parity entities, but keep array usage."""
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    for domain, key in PARITY_ENTITY_KEYS:
        assert _entity_id(hass, mock_config_entry.entry_id, domain, key) is None, key
    assert (
        _entity_id(hass, mock_config_entry.entry_id, "sensor", "array_usage")
        is not None
    )


@pytest.mark.usefixtures("mock_unraid_websocket_client_class")
async def test_parity_schedule_entities_created_with_parity_array(
    hass: HomeAssistant,
    mock_config_entry,
    mock_async_unraid_client,
) -> None:
    """A parity schedule and history add entities when the array has disks."""
    mock_async_unraid_client.get_parity_schedule.return_value = ParitySchedule(
        mode="custom", cron="0 7 * * 6"
    )
    mock_async_unraid_client.get_parity_history.return_value = ParityHistory(
        records=[
            ParityCheckRecord(
                action="Parity-Check", date="2026-10-01T03:00:00Z", status="OK"
            )
        ]
    )

    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    for key in ("next_parity_check", "last_parity_check"):
        entity_id = _entity_id(hass, mock_config_entry.entry_id, "sensor", key)
        assert entity_id is not None, key
        assert hass.states.get(entity_id) is not None, key


@pytest.mark.usefixtures("pool_only_client", "mock_unraid_websocket_client_class")
async def test_parity_schedule_entities_not_created_without_array_disks(
    hass: HomeAssistant,
    mock_config_entry,
    pool_only_client,
) -> None:
    """A parity schedule or history from the agent does not add entities."""
    schedule = MagicMock()
    schedule.is_enabled = True
    pool_only_client.get_parity_schedule.return_value = schedule
    history = MagicMock()
    history.records = [MagicMock()]
    pool_only_client.get_parity_history.return_value = history

    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    for domain, key in (
        ("sensor", "next_parity_check"),
        ("sensor", "last_parity_check"),
        ("binary_sensor", "parity_check_scheduled"),
    ):
        assert _entity_id(hass, mock_config_entry.entry_id, domain, key) is None, key


@pytest.mark.usefixtures("pool_only_client", "mock_unraid_websocket_client_class")
async def test_existing_parity_entities_disabled_without_array_disks(
    hass: HomeAssistant,
    mock_config_entry,
) -> None:
    """Parity entities from earlier releases are disabled, not deleted."""
    registry = er.async_get(hass)
    for domain, key in PARITY_ENTITY_KEYS:
        registry.async_get_or_create(
            domain,
            DOMAIN,
            f"{mock_config_entry.entry_id}_{key}",
            config_entry=mock_config_entry,
        )

    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    for domain, key in PARITY_ENTITY_KEYS:
        entity_id = _entity_id(hass, mock_config_entry.entry_id, domain, key)
        assert entity_id is not None, key
        entry = registry.async_get(entity_id)
        assert entry is not None
        assert entry.disabled_by is er.RegistryEntryDisabler.INTEGRATION, key


@pytest.mark.usefixtures("mock_unraid_websocket_client_class")
async def test_parity_entities_reenabled_when_array_disks_appear(
    hass: HomeAssistant,
    mock_config_entry,
    mock_async_unraid_client,
) -> None:
    """Entities the integration disabled come back once array disks exist."""
    registry = er.async_get(hass)
    integration_disabled = registry.async_get_or_create(
        "sensor",
        DOMAIN,
        f"{mock_config_entry.entry_id}_parity_progress",
        config_entry=mock_config_entry,
        disabled_by=er.RegistryEntryDisabler.INTEGRATION,
    )
    user_disabled = registry.async_get_or_create(
        "button",
        DOMAIN,
        f"{mock_config_entry.entry_id}_parity_check_start",
        config_entry=mock_config_entry,
        disabled_by=er.RegistryEntryDisabler.USER,
    )

    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    restored = registry.async_get(integration_disabled.entity_id)
    assert restored is not None
    assert restored.disabled_by is None
    # A user's choice to disable an entity is left alone
    still_disabled = registry.async_get(user_disabled.entity_id)
    assert still_disabled is not None
    assert still_disabled.disabled_by is er.RegistryEntryDisabler.USER


@pytest.mark.usefixtures("pool_only_client", "mock_unraid_websocket_client_class")
@pytest.mark.parametrize(("service", "client_method"), PARITY_SERVICES)
async def test_parity_actions_refused_without_array_disks(
    hass: HomeAssistant,
    mock_config_entry,
    pool_only_client,
    service: str,
    client_method: str,
) -> None:
    """Parity actions stay registered but raise a translated error."""
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert hass.services.has_service(DOMAIN, service)
    with pytest.raises(ServiceValidationError) as err:
        await hass.services.async_call(DOMAIN, service, {}, blocking=True)

    assert err.value.translation_key == "no_parity_array"
    getattr(pool_only_client, client_method).assert_not_called()


@pytest.mark.usefixtures("mock_unraid_websocket_client_class")
@pytest.mark.parametrize(("service", "client_method"), PARITY_SERVICES)
async def test_parity_actions_call_agent_with_parity_array(
    hass: HomeAssistant,
    mock_config_entry,
    mock_async_unraid_client,
    service: str,
    client_method: str,
) -> None:
    """Parity actions reach the agent on servers with a parity array."""
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    await hass.services.async_call(DOMAIN, service, {}, blocking=True)

    getattr(mock_async_unraid_client, client_method).assert_called_once()


@pytest.mark.usefixtures("pool_only_client", "mock_unraid_websocket_client_class")
@pytest.mark.parametrize(
    ("service", "client_method"),
    [("array_start", "start_array"), ("array_stop", "stop_array")],
)
async def test_array_actions_work_without_array_disks(
    hass: HomeAssistant,
    mock_config_entry,
    pool_only_client,
    service: str,
    client_method: str,
) -> None:
    """Array start/stop still run on pool-only servers (pools, Docker, VMs)."""
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    await hass.services.async_call(DOMAIN, service, {}, blocking=True)

    getattr(pool_only_client, client_method).assert_called_once()


async def _refresh(hass: HomeAssistant, entry) -> None:
    await entry.runtime_data.coordinator.async_refresh()
    await hass.async_block_till_done()


def _stopped(array: MagicMock) -> MagicMock:
    array.state = "Stopped"
    return array


async def _restart_array(hass: HomeAssistant, entry, client, array) -> None:
    """Report the array stopped with the new layout, then started again."""
    client.get_array_status.return_value = _stopped(array)
    await _refresh(hass, entry)
    array.state = "Started"
    await _refresh(hass, entry)


@pytest.mark.usefixtures("mock_unraid_websocket_client_class")
async def test_reload_when_array_disks_disappear(
    hass: HomeAssistant,
    mock_config_entry,
    mock_async_unraid_client,
) -> None:
    """Parity entities are disabled once the restarted array has no disks."""
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()
    entity_id = _entity_id(
        hass, mock_config_entry.entry_id, "button", "parity_check_start"
    )
    assert entity_id is not None

    await _restart_array(
        hass, mock_config_entry, mock_async_unraid_client, _pool_only_array()
    )

    entry = er.async_get(hass).async_get(entity_id)
    assert entry is not None
    assert entry.disabled_by is er.RegistryEntryDisabler.INTEGRATION


@pytest.mark.usefixtures("mock_unraid_websocket_client_class")
async def test_reload_when_array_disks_appear(
    hass: HomeAssistant,
    mock_config_entry,
    pool_only_client,
) -> None:
    """Parity entities are created once the restarted array has disks."""
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()
    assert (
        _entity_id(hass, mock_config_entry.entry_id, "button", "parity_check_start")
        is None
    )

    await _restart_array(hass, mock_config_entry, pool_only_client, mock_array_status())

    entity_id = _entity_id(
        hass, mock_config_entry.entry_id, "button", "parity_check_start"
    )
    assert entity_id is not None
    assert hass.states.get(entity_id) is not None


@pytest.mark.usefixtures("mock_unraid_websocket_client_class")
async def test_no_recheck_while_array_stays_started(
    hass: HomeAssistant,
    mock_config_entry,
    pool_only_client,
) -> None:
    """Disk counts are not re-checked on routine updates of a started array."""
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    pool_only_client.get_array_status.return_value = mock_array_status()
    with patch.object(hass.config_entries, "async_schedule_reload") as reload:
        await _refresh(hass, mock_config_entry)
        pool_only_client.get_array_status.return_value = _stopped(mock_array_status())
        await _refresh(hass, mock_config_entry)

    reload.assert_not_called()


@pytest.mark.usefixtures("mock_unraid_websocket_client_class")
async def test_recheck_when_agent_answers_again(
    hass: HomeAssistant,
    mock_config_entry,
    pool_only_client,
) -> None:
    """Disk counts are re-checked after the agent was unreachable."""
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()
    coordinator = mock_config_entry.runtime_data.coordinator

    pool_only_client.get_array_status.return_value = mock_array_status()
    with patch.object(hass.config_entries, "async_schedule_reload") as reload:
        coordinator.async_set_update_error(Exception("agent restarting"))
        reload.assert_not_called()
        await _refresh(hass, mock_config_entry)

    reload.assert_called_once_with(mock_config_entry.entry_id)


@pytest.mark.usefixtures("mock_unraid_websocket_client_class")
async def test_unknown_disk_counts_keep_recheck_pending(
    hass: HomeAssistant,
    mock_config_entry,
    pool_only_client,
) -> None:
    """Unknown counts after an array start defer the re-check, never reload."""
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    unknown = _pool_only_array()
    unknown.num_data_disks = None
    unknown.num_parity_disks = None
    with patch.object(hass.config_entries, "async_schedule_reload") as reload:
        await _restart_array(hass, mock_config_entry, pool_only_client, unknown)
        reload.assert_not_called()

        pool_only_client.get_array_status.return_value = mock_array_status()
        await _refresh(hass, mock_config_entry)

    reload.assert_called_once_with(mock_config_entry.entry_id)


@pytest.mark.usefixtures("mock_unraid_websocket_client_class")
async def test_recheck_pending_when_counts_unknown_at_setup(
    hass: HomeAssistant,
    mock_config_entry,
    mock_async_unraid_client,
) -> None:
    """Unknown counts at setup are re-checked once the agent reports them."""
    unknown = mock_array_status()
    unknown.num_data_disks = None
    unknown.num_parity_disks = None
    mock_async_unraid_client.get_array_status.return_value = unknown
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    mock_async_unraid_client.get_array_status.return_value = _pool_only_array()
    with patch.object(hass.config_entries, "async_schedule_reload") as reload:
        await _refresh(hass, mock_config_entry)

    reload.assert_called_once_with(mock_config_entry.entry_id)


@pytest.mark.usefixtures("mock_unraid_websocket_client_class")
async def test_disabled_parity_entities_kept_when_counts_unknown(
    hass: HomeAssistant,
    mock_config_entry,
    mock_async_unraid_client,
) -> None:
    """Unknown counts at setup do not re-enable integration-disabled entities."""
    registry = er.async_get(hass)
    registry_entry = registry.async_get_or_create(
        "button",
        DOMAIN,
        f"{mock_config_entry.entry_id}_parity_check_start",
        config_entry=mock_config_entry,
        disabled_by=er.RegistryEntryDisabler.INTEGRATION,
    )
    unknown = mock_array_status()
    unknown.num_data_disks = None
    unknown.num_parity_disks = None
    mock_async_unraid_client.get_array_status.return_value = unknown

    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    entry = registry.async_get(registry_entry.entity_id)
    assert entry is not None
    assert entry.disabled_by is er.RegistryEntryDisabler.INTEGRATION
