"""Kiểm thử hình học tĩnh đã hiện thực; không kiểm thử MovementEngine."""

from dataclasses import FrozenInstanceError
from pathlib import Path
import sys

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.core.geometry import DIRECTION_VECTORS, Geometry, to_xy


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
    assert to_xy(direction, -10, geometry) == before
    assert to_xy(direction, 0, geometry) == stop
    assert to_xy(direction, 10, geometry) == after
    dx, dy = DIRECTION_VECTORS[direction]
    assert after == pytest.approx((before[0] + 20 * dx, before[1] + 20 * dy))


@pytest.mark.parametrize("direction", ["X", "n", "", None])
def test_g05_invalid_direction(direction):
    with pytest.raises(ValueError):
        to_xy(direction, 0, Geometry())


def test_configured_geometry_and_purity():
    geometry = Geometry(intersection_width_m=20, lane_offset_m=3)
    assert to_xy("N", -4, geometry) == (-3.0, -14.0)
    assert to_xy("N", -4, geometry) == to_xy("N", -4, geometry)
    assert geometry.conflict_bounds == (-10.0, -10.0, 10.0, 10.0)
    assert geometry.to_snapshot().lane_offset_m == 3.0
    with pytest.raises(FrozenInstanceError):
        geometry.lane_offset_m = 5


@pytest.mark.parametrize("position", [float("nan"), float("inf"), -float("inf")])
def test_nonfinite_position(position):
    with pytest.raises(ValueError):
        to_xy("N", position, Geometry())


@pytest.mark.parametrize("position", [True, "1", None])
def test_invalid_position_type(position):
    with pytest.raises(TypeError):
        to_xy("N", position, Geometry())


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
