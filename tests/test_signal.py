"""Tín hiệu, lịch sáu đoạn và hợp đồng với Config/Algorithm."""

import sys
from dataclasses import FrozenInstanceError
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from src.models import Config, SignalPlan, SignalSegment


@pytest.mark.parametrize('code,phase,color,greens', [
    ('NS_GREEN', 'NS', 'GREEN', ('N', 'S')),
    ('NS_YELLOW', None, 'YELLOW', ()),
    ('ALL_RED_1', None, 'RED', ()),
    ('EW_GREEN', 'EW', 'GREEN', ('E', 'W')),
    ('EW_YELLOW', None, 'YELLOW', ()),
    ('ALL_RED_2', None, 'RED', ()),
])
def test_segment_permissions(code, phase, color, greens):
    segment = SignalSegment(code, phase, color, 3)
    assert segment.green_directions == greens
    for direction in 'NSEW':
        assert segment.is_green_for(direction) == (direction in greens)


@pytest.mark.parametrize('code,phase,color', [
    ('BAD', 'NS', 'GREEN'), ('NS_GREEN', 'EW', 'GREEN'),
    ('NS_GREEN', None, 'GREEN'), ('NS_GREEN', 'NS', 'RED'),
    ('NS_YELLOW', 'NS', 'YELLOW'), ('EW_YELLOW', 'EW', 'YELLOW'),
    ('ALL_RED_1', 'NS', 'RED'), ('ALL_RED_2', None, 'GREEN'),
    ('EW_GREEN', 'EW', 'green'),
])
def test_inconsistent_segment(code, phase, color):
    with pytest.raises(ValueError):
        SignalSegment(code, phase, color, 3)


@pytest.mark.parametrize('field,value', [('code', []), ('color', 1), ('active_phase', True)])
def test_wrong_segment_types(field, value):
    data = dict(code='NS_GREEN', active_phase='NS', color='GREEN', duration_s=3)
    with pytest.raises(TypeError):
        SignalSegment(**(data | {field: value}))


@pytest.mark.parametrize('value,error', [
    (0, ValueError), (-1, ValueError), (1.5, TypeError), (3.0, TypeError),
    (True, TypeError), ('3', TypeError), (float('nan'), TypeError),
    (float('inf'), TypeError), (None, TypeError),
])
def test_bad_segment_duration(value, error):
    with pytest.raises(error):
        SignalSegment('NS_GREEN', 'NS', 'GREEN', value)


@pytest.mark.parametrize('field', ['green_ns_s', 'green_ew_s', 'yellow_s', 'all_red_s', 'cycle_no'])
@pytest.mark.parametrize('value,error', [(0, ValueError), (-1, ValueError),
                                      (1.5, TypeError), (True, TypeError)])
def test_bad_plan_parameters(field, value, error):
    with pytest.raises(error):
        SignalPlan(**(dict(green_ns_s=21, green_ew_s=39) | {field: value}))


def test_schedule_and_complete_progression():
    plan = SignalPlan(21, 39)
    codes = ['NS_GREEN', 'NS_YELLOW', 'ALL_RED_1', 'EW_GREEN', 'EW_YELLOW', 'ALL_RED_2']
    assert [s.code for s in plan.segments] == codes
    assert [s.duration_s for s in plan.segments] == [21, 3, 1, 39, 3, 1]
    assert plan.nominal_duration_s == 68
    for i, code in enumerate(codes):
        assert not plan.is_cycle_end()
        current = plan.current()
        assert current.code == code
        assert plan.current() is current
        following = plan.move_next()
        assert following is (plan.segments[i + 1] if i < 5 else None)
    assert plan.is_cycle_end()
    assert plan.current() is None
    assert plan.move_next() is None
    assert len(plan.segments) == 6
    assert plan.nominal_duration_s == 68


def test_independence_and_immutability():
    first, second = SignalPlan(21, 39), SignalPlan(21, 39)
    first.move_next()
    assert first.current().code == 'NS_YELLOW'
    assert second.current().code == 'NS_GREEN'
    assert isinstance(first.segments, tuple)
    with pytest.raises(TypeError):
        first.segments[0] = second.segments[0]
    for field, value in [('green_ns_s', 1), ('segments', ()), ('cycle_no', 9)]:
        with pytest.raises(FrozenInstanceError):
            setattr(first, field, value)
    for field, value in [('code', 'EW_GREEN'), ('duration_s', 1),
                         ('active_phase', 'EW'), ('color', 'RED')]:
        with pytest.raises(FrozenInstanceError):
            setattr(first.segments[0], field, value)


@pytest.mark.parametrize('ns,ew', [(21, 39), (10, 50), (30, 30)])
def test_from_config_valid(ns, ew):
    plan = SignalPlan.from_config(Config(), ns, ew, cycle_no=2)
    assert plan.green_ns_s == ns
    assert plan.green_ew_s == ew
    assert plan.nominal_duration_s == 68
    assert plan.cycle_no == 2


@pytest.mark.parametrize('ns,ew,error', [
    (5, 55, ValueError), (55, 5, ValueError), (20, 50, ValueError),
    (0, 60, ValueError), (-1, 61, ValueError), (21.5, 38.5, TypeError),
    (21.0, 39, TypeError), (True, 59, TypeError),
])
def test_from_config_bad_allocation(ns, ew, error):
    with pytest.raises(error):
        SignalPlan.from_config(Config(), ns, ew)


@pytest.mark.parametrize('field', ['yellow_s', 'all_red_s'])
def test_config_fractional_seconds_not_truncated(field):
    config = Config()
    setattr(config, field, 3.5)
    with pytest.raises(TypeError):
        SignalPlan.from_config(config, 21, 39)


def test_config_snapshot_and_invalid_mutation():
    config = Config()
    plan = SignalPlan.from_config(config, 21, 39)
    config.yellow_s = 5
    assert plan.yellow_s == 3
    config.min_green_s = 40
    with pytest.raises(ValueError):
        SignalPlan.from_config(config, 21, 39)
    with pytest.raises(TypeError):
        SignalPlan.from_config({}, 21, 39)


@pytest.mark.parametrize('value,error', [('X', ValueError), (None, TypeError)])
def test_invalid_direction(value, error):
    with pytest.raises(error):
        SignalSegment('NS_GREEN', 'NS', 'GREEN', 21).is_green_for(value)
