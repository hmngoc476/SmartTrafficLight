"""Vòng đời Vehicle và tính nguyên vẹn khi từ chối thao tác."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from dataclasses import FrozenInstanceError
import json
import pytest
from src.models.vehicle import Vehicle, MotionState


def test_vehicle_lifecycle():
    v = Vehicle('v1', 'N', arrival_t=2)
    assert v.status == 'WAITING'
    assert v.elapsed_to_stopline() is None
    v.add_stopped_delay(0.2)
    assert v.stopped_delay_s == 0.2
    v.update_motion(-1, 3)
    assert v.motion_state == MotionState.APPROACHING
    assert v.crossed_stop_t is None
    v.update_motion(0, 3)
    assert v.status == 'WAITING'
    v.mark_crossed(5)
    assert v.elapsed_to_stopline() == 3
    assert v.motion_state == MotionState.CROSSING
    v.mark_exited(8)
    assert v.status == 'PASSED'
    assert v.motion_state == MotionState.EXITED
    assert v.speed_mps == 0
    json.dumps(v.snapshot())
    with pytest.raises(FrozenInstanceError):
        v.origin = 'S'


@pytest.mark.parametrize('field,value', [
    ('vehicle_id', ''), ('origin', 'X'), ('origin', 1), ('speed_mps', -1),
    ('speed_mps', True), ('arrival_t', -1), ('length_m', 0),
    ('s_front_m', float('nan')), ('s_front_m', float('inf')), ('s_front_m', 1),
])
def test_invalid_constructor(field, value):
    data = dict(vehicle_id='v1', origin='N') | {field: value}
    with pytest.raises((TypeError, ValueError)):
        Vehicle(**data)


@pytest.mark.parametrize('position,speed', [(-101, 1), (-90, -1), (-90, float('inf'))])
def test_invalid_motion_is_atomic(position, speed):
    v = Vehicle('v', 'N')
    before = v.snapshot()
    with pytest.raises(ValueError):
        v.update_motion(position, speed)
    assert v.snapshot() == before


def test_crossing_guards_and_exit_guards():
    v = Vehicle('v', 'N', arrival_t=2)
    for method, t in ((v.mark_crossed, 3), (v.mark_exited, 3)):
        before = v.snapshot()
        with pytest.raises(ValueError):
            method(t)
        assert v.snapshot() == before
    v.update_motion(0, 1)
    with pytest.raises(ValueError):
        v.mark_crossed(1)
    v.mark_crossed(5)
    before = v.snapshot()
    for method, t in ((v.mark_crossed, 6), (v.mark_exited, 4)):
        with pytest.raises(ValueError):
            method(t)
        assert v.snapshot() == before
    v.mark_exited(6)
    with pytest.raises(ValueError):
        v.mark_exited(7)
    with pytest.raises(ValueError):
        v.update_motion(1, 1)


def test_delay_and_geometry_contract():
    v = Vehicle('v', 'W')
    class FakeGeometry:
        def lane_to_xy(self, origin, s_front_m):
            assert origin == 'W'
            return (s_front_m, 2.0)
    assert v.to_xy(FakeGeometry()) == (-100, 2)
    for dt in (-1, float('nan'), True):
        with pytest.raises((ValueError, TypeError)):
            v.add_stopped_delay(dt)
    v.update_motion(-99, 1)
    with pytest.raises(ValueError):
        v.add_stopped_delay(1)
    assert v.stopped_delay_s == 0
    v.update_motion(0, 0)
    v.mark_crossed(1)
    with pytest.raises(ValueError):
        v.add_stopped_delay(1)
