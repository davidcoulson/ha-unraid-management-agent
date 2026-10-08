"""Test per-VM devices and their sensors."""

from __future__ import annotations

from collections.abc import Generator
from datetime import UTC, datetime, timedelta
from unittest.mock import MagicMock

import pytest
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers import entity_registry as er

from custom_components.unraid_management_agent.api.models import VMInfo, ZFSPool
from custom_components.unraid_management_agent.const import DOMAIN

GIB = 1024**3
T0 = datetime(2026, 10, 8, 12, 0, 0, tzinfo=UTC)


def _vm(  # noqa: PLR0913
    *,
    vm_id: str = "b823288b65f87be1e892140bb4a8929b",
    name: str = "Windows 10",
    state: str = "running",
    rx: int = 1_000_000,
    tx: int = 500_000,
    at: datetime = T0,
) -> VMInfo:
    """Build a VMInfo the way the agent reports it."""
    return VMInfo(
        id=vm_id,
        name=name,
        state=state,
        cpu_count=16,
        guest_cpu_percent=12.5,
        memory_allocated_bytes=32 * GIB,
        memory_used_bytes=32 * GIB,
        disk_size_bytes=0,
        disk_read_bytes=0,
        disk_write_bytes=0,
        network_rx_bytes=rx,
        network_tx_bytes=tx,
        autostart=False,
        persistent=True,
        timestamp=at.isoformat(),
    )


@pytest.fixture
def vm_client(mock_async_unraid_client: MagicMock) -> Generator[MagicMock]:
    """Serve real VMInfo models: one running VM and one stopped VM."""
    mock_async_unraid_client.list_vms.return_value = [
        _vm(),
        _vm(vm_id="985351ae2bb817c5484904fc57076fa5", name="Ubuntu", state="shut off"),
    ]
    return mock_async_unraid_client


async def _push_vms(hass: HomeAssistant, entry, vms: list[VMInfo]) -> None:
    """Deliver new VM data through the coordinator, as a websocket event would."""
    coordinator = entry.runtime_data.coordinator
    coordinator.data.vms = vms
    coordinator.async_set_updated_data(coordinator.data)
    await hass.async_block_till_done()


@pytest.mark.usefixtures("vm_client", "mock_unraid_websocket_client_class")
async def test_each_vm_gets_a_device_linked_to_the_server(
    hass: HomeAssistant, mock_config_entry
) -> None:
    """VM controls and metrics live on a per-VM device under the server."""
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    devices = dr.async_get(hass)
    server = devices.async_get_device_by_identifier(
        (DOMAIN, "test_entry_id"), "test_entry_id"
    )
    vm_device = devices.async_get_device_by_identifier(
        (DOMAIN, "test_entry_id_vm_b823288b65f87be1e892140bb4a8929b"), "test_entry_id"
    )
    assert server is not None
    assert vm_device is not None
    assert vm_device.name == "Windows 10"
    assert vm_device.model == "Virtual Machine"
    assert vm_device.via_device_id == server.id

    entities = er.async_get(hass)
    on_vm_device = {
        e.entity_id
        for e in er.async_entries_for_device(
            entities, vm_device.id, include_disabled_entities=True
        )
    }
    assert "switch.windows_10_power" in on_vm_device
    assert "button.windows_10_force_stop" in on_vm_device
    assert "sensor.windows_10_cpu_usage" in on_vm_device
    assert "sensor.windows_10_disk_read_rate" in on_vm_device


@pytest.mark.usefixtures("vm_client", "mock_unraid_websocket_client_class")
async def test_vm_metric_sensors(hass: HomeAssistant, mock_config_entry) -> None:
    """Metrics are numeric sensors with units, not formatted attribute strings."""
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert hass.states.get("sensor.windows_10_state").state == "running"
    assert hass.states.get("sensor.windows_10_state").attributes["autostart"] is False
    assert float(hass.states.get("sensor.windows_10_cpu_usage").state) == 12.5
    assert hass.states.get("sensor.windows_10_vcpus").state == "16"
    memory = hass.states.get("sensor.windows_10_memory_allocated")
    assert float(memory.state) == 32
    assert memory.attributes["unit_of_measurement"] == "GiB"
    assert hass.states.get("sensor.ubuntu_state").state == "shut off"

    # Disabled by default: disk counters are often 0 and memory used == allocated
    entities = er.async_get(hass)
    assert entities.async_get("sensor.windows_10_disk_read_rate").disabled_by
    assert entities.async_get("sensor.windows_10_memory_used").disabled_by


@pytest.mark.usefixtures("vm_client", "mock_unraid_websocket_client_class")
async def test_vm_network_rate(hass: HomeAssistant, mock_config_entry) -> None:
    """Network rate comes from successive agent samples of the byte counters."""
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()
    rx = "sensor.windows_10_network_receive_rate"
    # One sample is not a rate yet; like the host network sensors it reads 0
    assert float(hass.states.get(rx).state) == 0

    # 7.5 MB in 60 s = 1 Mbit/s
    later = T0 + timedelta(seconds=60)
    await _push_vms(hass, mock_config_entry, [_vm(rx=8_500_000, at=later)])
    state = hass.states.get(rx)
    assert float(state.state) == pytest.approx(1.0)
    assert state.attributes["unit_of_measurement"] == "Mbit/s"

    # A websocket push that re-delivers the same VM sample changes nothing
    await _push_vms(hass, mock_config_entry, [_vm(rx=8_500_000, at=later)])
    assert float(hass.states.get(rx).state) == pytest.approx(1.0)

    # A new sample with no traffic is a real zero
    await _push_vms(
        hass,
        mock_config_entry,
        [_vm(rx=8_500_000, at=later + timedelta(seconds=60))],
    )
    assert float(hass.states.get(rx).state) == 0

    # VM restarted: the counter dropped, so no huge "wrapped" rate
    await _push_vms(
        hass,
        mock_config_entry,
        [_vm(rx=10_000, at=later + timedelta(seconds=120))],
    )
    assert float(hass.states.get(rx).state) == 0

    # A stopped VM has no traffic
    await _push_vms(
        hass,
        mock_config_entry,
        [_vm(state="shut off", at=later + timedelta(seconds=180))],
    )
    assert float(hass.states.get(rx).state) == 0


@pytest.mark.usefixtures("vm_client", "mock_unraid_websocket_client_class")
async def test_vm_sensors_unavailable_when_vm_removed(
    hass: HomeAssistant, mock_config_entry
) -> None:
    """Sensors of a VM the agent no longer reports become unavailable."""
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    await _push_vms(hass, mock_config_entry, [_vm()])
    assert hass.states.get("sensor.ubuntu_state").state == "unavailable"


@pytest.mark.usefixtures("vm_client", "mock_unraid_websocket_client_class")
async def test_vm_added_later_gets_sensors(
    hass: HomeAssistant, mock_config_entry
) -> None:
    """A VM created after setup gets its device and sensors without a reload."""
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    await _push_vms(
        hass,
        mock_config_entry,
        [_vm(), _vm(vm_id="cc51802580ace090e783627716506e13", name="k3s-ag-2")],
    )
    assert hass.states.get("sensor.k3s_ag_2_state").state == "running"


@pytest.mark.usefixtures("vm_client", "mock_unraid_websocket_client_class")
async def test_renamed_vm_is_not_confused_with_one_reusing_its_name(
    hass: HomeAssistant, mock_config_entry
) -> None:
    """The VM identifier wins over a name match on another VM."""
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    # Windows 10 is renamed; a new VM (listed first) takes its old name
    await _push_vms(
        hass,
        mock_config_entry,
        [
            _vm(vm_id="aaaa", name="Windows 10", state="shut off"),
            _vm(name="Windows 10 (old)"),
        ],
    )
    assert hass.states.get("sensor.windows_10_state").state == "running"


def test_zfs_pool_usage_from_allocated_bytes() -> None:
    """The agent reports pool usage as allocated_bytes (zpool ALLOC)."""
    pool = ZFSPool.model_validate(
        {"name": "tank", "size_bytes": 400, "allocated_bytes": 100, "free_bytes": 300}
    )
    assert pool.used_bytes == 100
    assert pool.computed_used_percent == 25.0
    # used_bytes still works for agents that send it
    assert (
        ZFSPool(name="tank", size_bytes=400, used_bytes=200).computed_used_percent
        == 50.0
    )
