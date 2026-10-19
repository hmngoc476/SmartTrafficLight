"""Kiểm thử hình học tĩnh đã hiện thực; không kiểm thử MovementEngine."""

from dataclasses import FrozenInstanceError
from pathlib import Path
import sys

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.core.geometry import DIRECTION_VECTORS, Geometry
from src.models.vehicle import Vehicle


@pytest.mark.parametrize(
    "direction,stop,before,after",
    [
        pytest.param("N", (-2.0, -8.0), (-2.0, -18.0), (-2.0, 2.0), id="G-01-N"),
        pytest.param("S", (2.0, 8.0), (2.0, 18.0), (2.0, -2.0), id="G-02-S"),
        pytest.param("E", (8.0, -2.0), (18.0, -2.0), (-2.0, -2.0), id="G-03-E"),
        pytest.param("W", (-8.0, 2.0), (-18.0, 2.0), (2.0, 2.0), id="G-04-W"),
    ],
)
def test_four_direction_coordinates(direction, stop, before, after):
    geometry = Geometry()
    assert geometry.lane_to_xy(direction, -10) == before
    assert geometry.lane_to_xy(direction, 0) == stop
    assert geometry.lane_to_xy(direction, 10) == after
    dx, dy = DIRECTION_VECTORS[direction]
    assert after == pytest.approx((before[0] + 20 * dx, before[1] + 20 * dy))


@pytest.mark.parametrize("direction", ["X", "n", "", None])
def test_g05_invalid_direction(direction):
    with pytest.raises(ValueError):
        Geometry().lane_to_xy(direction, 0)


def test_configured_geometry_and_purity():
    geometry = Geometry(intersection_width_m=20, lane_offset_m=3)
    assert geometry.lane_to_xy("N", -4) == (-3.0, -14.0)
    assert geometry.lane_to_xy("N", -4) == geometry.lane_to_xy("N", -4)
    assert geometry.conflict_bounds == (-10.0, -10.0, 10.0, 10.0)
    assert geometry.to_snapshot().lane_offset_m == 3.0
    with pytest.raises(FrozenInstanceError):
        geometry.lane_offset_m = 5


@pytest.mark.parametrize("position", [float("nan"), float("inf"), -float("inf")])
def test_nonfinite_position(position):
    with pytest.raises(ValueError):
        Geometry().lane_to_xy("N", position)


@pytest.mark.parametrize("position", [True, "1", None])
def test_invalid_position_type(position):
    with pytest.raises(TypeError):
        Geometry().lane_to_xy("N", position)


@pytest.mark.parametrize(
    "parameters",
    [
        {"intersection_width_m": 0},
        {"approach_visible_m": -1},
        {"vehicle_length_m": 0},
        {"min_gap_m": -1},
        {"stop_margin_m": -1},
        {"lane_offset_m": 8},
        {"vehicle_width_m": 0},
        {"intersection_width_m": float("nan")},
    ],
)
def test_invalid_geometry_values(parameters):
    with pytest.raises(ValueError):
        Geometry(**parameters)


@pytest.mark.parametrize(
    "direction,stop,before,after",
    [
        ("N", (-2.0, -8.0), (-2.0, -18.0), (-2.0, 2.0)),
        ("S", (2.0, 8.0), (2.0, 18.0), (2.0, -2.0)),
        ("E", (8.0, -2.0), (18.0, -2.0), (-2.0, -2.0)),
        ("W", (-8.0, 2.0), (-18.0, 2.0), (2.0, 2.0)),
    ],
)
def test_real_vehicle_passes_coordinates_directly_to_real_geometry(direction, stop, before, after):
    """Integration: một API tính tọa độ; không còn Vehicle.to_xy wrapper."""
    geometry = Geometry()
    vehicle = Vehicle(f"V-{direction}", direction, s_front_m=-10)
    assert not hasattr(vehicle, "to_xy")
    assert geometry.lane_to_xy(vehicle.origin, vehicle.s_front_m) == before

    vehicle.update_motion(0, 1)
    assert geometry.lane_to_xy(vehicle.origin, vehicle.s_front_m) == stop

    vehicle.mark_crossed(1)
    vehicle.update_motion(10, 2)
    assert geometry.lane_to_xy(vehicle.origin, vehicle.s_front_m) == after
    assert vehicle.origin == direction
    assert vehicle.s_front_m == 10
