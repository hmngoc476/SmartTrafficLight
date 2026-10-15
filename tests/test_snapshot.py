"""Kiểm tra DTO và dữ liệu minh họa, không tuyên bố engine đã hoạt động."""

from dataclasses import FrozenInstanceError, replace
import json
from pathlib import Path
import sys

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.core.geometry import Geometry, to_xy
from src.models.snapshot import SignalSnapshot, SimulationSnapshot


@pytest.fixture
def example_data():
    return json.loads((ROOT / "docs/examples/simulation_snapshot_example.json").read_text(encoding="utf-8"))


def test_g11_json_schema_and_roundtrip(example_data):
    snapshot = SimulationSnapshot.from_dict(example_data)
    encoded = json.dumps(snapshot.to_dict(), allow_nan=False)
    restored = SimulationSnapshot.from_dict(json.loads(encoded))
    assert restored == snapshot
    assert snapshot.sim_time == 20 and snapshot.cycle_index == 1
    assert snapshot.signals.current_segment == "NS_GREEN"
    assert type(snapshot.signals.remaining_s) is int
    assert all(type(vehicle.x) is float and type(vehicle.y) is float for vehicle in snapshot.vehicles)


def test_g06_deep_read_only_and_detached_data(example_data):
    snapshot = SimulationSnapshot.from_dict(example_data)
    with pytest.raises(FrozenInstanceError):
        snapshot.sim_time = 99
    with pytest.raises(FrozenInstanceError):
        snapshot.vehicles[0].x = 99
    with pytest.raises(FrozenInstanceError):
        snapshot.signals.remaining_s = 99
    with pytest.raises(TypeError):
        snapshot.signals.signal_colors["N"] = "RED"
    with pytest.raises(TypeError):
        snapshot.metrics.queue_lengths["N"] = 99
    with pytest.raises(TypeError):
        snapshot.vehicles[0] = snapshot.vehicles[1]
    example_data["signals"]["signal_colors"]["N"] = "RED"
    example_data["metrics"]["queue_lengths"]["N"] = 99
    example_data["vehicles"][0]["x"] = 99
    exported = snapshot.to_dict()
    exported["signals"]["signal_colors"]["N"] = "RED"
    exported["vehicles"].clear()
    assert snapshot.signals.signal_colors["N"] == "GREEN"
    assert snapshot.metrics.queue_lengths["N"] == 1
    assert snapshot.vehicles[0].x == -2.0
    assert len(snapshot.vehicles) == 5


def test_caller_vehicle_list_is_copied(example_data):
    snapshot = SimulationSnapshot.from_dict(example_data)
    vehicles = list(snapshot.vehicles)
    copied = replace(snapshot, vehicles=vehicles)
    vehicles.clear()
    assert len(copied.vehicles) == 5
    assert isinstance(copied.vehicles, tuple)


def test_g07_duplicate_vehicle_id_rejected(example_data):
    example_data["vehicles"][1]["vehicle_id"] = example_data["vehicles"][0]["vehicle_id"]
    with pytest.raises(ValueError, match="vehicle_id"):
        SimulationSnapshot.from_dict(example_data)


def test_g08_example_ownership_and_conservation(example_data):
    """Chỉ kiểm tra ownership của mẫu; lifecycle engine chưa được kiểm thử."""
    snapshot = SimulationSnapshot.from_dict(example_data)
    queued = [vehicle for vehicle in snapshot.vehicles if vehicle.motion_state != "CROSSING"]
    active = [vehicle for vehicle in snapshot.vehicles if vehicle.motion_state == "CROSSING"]
    assert {vehicle.vehicle_id for vehicle in queued}.isdisjoint(vehicle.vehicle_id for vehicle in active)
    assert all(vehicle.s_front_m <= 0 for vehicle in queued)
    assert all(vehicle.s_front_m >= 0 for vehicle in active)
    assert len(active) == snapshot.metrics.active_crossing_count == 1
    assert snapshot.metrics.initial_total + snapshot.metrics.total_arrivals == len(queued) + snapshot.metrics.crossed_stop_total
    assert snapshot.metrics.crossed_stop_total == len(active) + snapshot.metrics.exited_world_total


def test_example_coordinates_and_gap(example_data):
    """Kiểm chứng dữ liệu mẫu, không kiểm thử luật di chuyển theo substep."""
    snapshot = SimulationSnapshot.from_dict(example_data)
    geometry = Geometry()
    assert snapshot.geometry == geometry.to_snapshot()
    for vehicle in snapshot.vehicles:
        assert (vehicle.x, vehicle.y) == to_xy(vehicle.origin, vehicle.s_front_m, geometry)
        assert vehicle.motion_state != "EXITED"
    leader = next(vehicle for vehicle in snapshot.vehicles if vehicle.vehicle_id == "V-N-002")
    follower = next(vehicle for vehicle in snapshot.vehicles if vehicle.vehicle_id == "V-N-001")
    gap = leader.s_front_m - leader.length_m - follower.s_front_m
    assert gap >= geometry.min_gap_m - 1e-6
    assert -8 <= leader.x <= 8 and -8 <= leader.y <= 8


def test_g10_conflicting_greens_rejected(example_data):
    example_data["signals"]["signal_colors"]["E"] = "GREEN"
    example_data["signals"]["signal_colors"]["W"] = "GREEN"
    with pytest.raises(ValueError, match="xung đột"):
        SimulationSnapshot.from_dict(example_data)


@pytest.mark.parametrize(
    "segment,phase,colors",
    [
        ("NS_GREEN", "NS", ("GREEN", "GREEN", "RED", "RED")),
        ("NS_YELLOW", "NS", ("YELLOW", "YELLOW", "RED", "RED")),
        ("ALL_RED_1", None, ("RED", "RED", "RED", "RED")),
        ("EW_GREEN", "EW", ("RED", "RED", "GREEN", "GREEN")),
        ("EW_YELLOW", "EW", ("RED", "RED", "YELLOW", "YELLOW")),
        ("ALL_RED_2", None, ("RED", "RED", "RED", "RED")),
    ],
)
def test_signal_segment_contract(segment, phase, colors):
    signals = SignalSnapshot(segment, phase, 1, dict(zip(("N", "S", "E", "W"), colors)))
    assert signals.active_phase == phase
    assert tuple(signals.signal_colors.values()) == colors


@pytest.mark.parametrize(
    "section,field,value,error",
    [
        (None, "sim_time", True, TypeError),
        (None, "cycle_index", 0, ValueError),
        (None, "schema_version", 2, ValueError),
        ("signals", "remaining_s", -1, ValueError),
        ("metrics", "crossed_stop_total", 4, ValueError),
        ("metrics", "initial_total", 4, ValueError),
    ],
)
def test_invalid_snapshot_values(example_data, section, field, value, error):
    target = example_data if section is None else example_data[section]
    target[field] = value
    with pytest.raises(error):
        SimulationSnapshot.from_dict(example_data)


def test_exited_vehicle_not_listed(example_data):
    example_data["vehicles"][0]["motion_state"] = "EXITED"
    with pytest.raises(ValueError, match="EXITED"):
        SimulationSnapshot.from_dict(example_data)


def test_error_requires_all_red(example_data):
    example_data["session_state"] = "ERROR"
    with pytest.raises(ValueError, match="ERROR"):
        SimulationSnapshot.from_dict(example_data)


def test_vehicle_counts_match_metrics(example_data):
    example_data["vehicles"].pop()
    with pytest.raises(ValueError, match="counters"):
        SimulationSnapshot.from_dict(example_data)
