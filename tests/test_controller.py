"""Controller runtime và hợp đồng tích hợp đến hết task 17/10."""

import sys
from pathlib import Path
from unittest.mock import patch

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.core import algorithms
from src.core.controller import TrafficLightController
from src.models.config import Config


COUNTS = {'N': 7, 'S': 4, 'E': 16, 'W': 5}


def activate(config=None):
    controller = TrafficLightController(config or Config())
    controller.start_next_cycle(COUNTS, cycle_no=1, started_at=0, conflict_clear=True)
    return controller


def test_unstarted_and_detached_configuration():
    config = Config()
    controller = TrafficLightController(config)
    config.green_budget_s = 80
    returned = controller.config
    returned.initial_queue['N'] = 90
    assert controller.config.green_budget_s == 60
    assert controller.config.initial_queue['N'] == 0
    assert controller.current_segment_code is None
    assert not any(controller.is_green_for(d) for d in 'NSEW')
    with pytest.raises(RuntimeError):
        controller.tick(conflict_clear=True)
    with pytest.raises(RuntimeError):
        controller.to_signal_snapshot()


def test_demand_utilization_and_preview_do_not_activate():
    controller = TrafficLightController(Config())
    assert controller.compute_phase_demand(COUNTS) == (11, 21)
    assert controller.compute_utilization(11, 21, (30, 30)) == {
        'eta_ns': 11 / 30, 'eta_ew': 21 / 30, 'eta_bar': 32 / 60,
    }
    plan = controller.build_cycle_plan(COUNTS, cycle_no=1)
    assert (plan.green_ns_s, plan.green_ew_s) == (21, 39)
    assert controller.current_segment_code is None


def test_reference_full_cycle_all_snapshots_and_signal_permissions():
    controller = activate()
    boundaries = {
        0: ('NS_GREEN', 21), 21: ('NS_YELLOW', 3), 24: ('ALL_RED_1', 1),
        25: ('EW_GREEN', 39), 64: ('EW_YELLOW', 3),
        67: ('ALL_RED_2', 1), 68: ('ALL_RED_2', 0),
    }
    for t in range(69):
        snap = controller.to_signal_snapshot()
        if t in boundaries:
            assert (snap.current_segment, snap.remaining_s) == boundaries[t]
        assert controller.elapsed_s == t
        assert not (controller.is_green_for('N') and controller.is_green_for('E'))
        if 'YELLOW' in snap.current_segment or 'ALL_RED' in snap.current_segment:
            assert not any(controller.is_green_for(d) for d in 'NSEW')
        if 'YELLOW' in snap.current_segment:
            assert snap.active_phase == snap.current_segment[:2]
        assert controller.to_signal_snapshot() == snap
        assert controller.elapsed_s == t
        if t < 68:
            controller.tick(conflict_clear=True)
    assert controller.cycle_complete
    assert not any(controller.is_green_for(d) for d in 'NSEW')
    with pytest.raises(RuntimeError):
        controller.tick(conflict_clear=True)


def test_custom_config_durations_are_used():
    controller = activate(Config(green_budget_s=20, min_green_s=5, yellow_s=2, all_red_s=2))
    for _ in range(27):
        controller.tick(conflict_clear=True)
        assert not controller.cycle_complete
    controller.tick(conflict_clear=True)
    assert controller.cycle_complete
    assert controller.elapsed_s == 28


def test_allocation_only_at_activation_and_fresh_counts_next_cycle():
    with patch.object(algorithms, 'allocate_green_adaptive', wraps=algorithms.allocate_green_adaptive) as allocate:
        controller = activate()
        assert allocate.call_args.args == (11, 21, 60, 10)
        assert allocate.call_count == 1
        for _ in range(68):
            controller.to_signal_snapshot()
            controller.tick(conflict_clear=True)
        assert allocate.call_count == 1
        controller.start_next_cycle(dict.fromkeys('NSEW', 0), cycle_no=2, started_at=68, conflict_clear=True)
        assert allocate.call_count == 2
        assert allocate.call_args.args == (0, 0, 60, 10)
        assert controller.remaining_s == 30
        assert controller.last_utilization == dict(eta_ns=0, eta_ew=0, eta_bar=0)
        report = controller.last_utilization
        report['eta_ns'] = 999
        assert controller.last_utilization['eta_ns'] == 0


@pytest.mark.parametrize('counts,error', [
    ({'N': 1}, ValueError), (dict(COUNTS, X=1), ValueError),
    (dict(COUNTS, N=-1), ValueError), (dict(COUNTS, N=True), TypeError),
    (dict(COUNTS, N=1.0), TypeError), (dict(COUNTS, N='1'), TypeError),
    (None, TypeError),
])
def test_invalid_counts_do_not_activate(counts, error):
    controller = TrafficLightController(Config())
    with pytest.raises(error):
        controller.start_next_cycle(counts, cycle_no=1, started_at=0, conflict_clear=True)
    assert controller.current_segment_code is None
    assert controller.elapsed_s == 0


@pytest.mark.parametrize('kwargs,error', [
    ({'cycle_no': 2}, ValueError), ({'cycle_no': True}, TypeError),
    ({'started_at': 1}, RuntimeError), ({'started_at': 0.0}, TypeError),
    ({'conflict_clear': False}, ValueError), ({'conflict_clear': 1}, TypeError),
])
def test_invalid_first_activation_is_atomic(kwargs, error):
    controller = TrafficLightController(Config())
    params = dict(cycle_no=1, started_at=0, conflict_clear=True) | kwargs
    with pytest.raises(error):
        controller.start_next_cycle(COUNTS, **params)
    assert controller.current_segment_code is None


def test_cannot_replace_active_plan_and_rejects_wrong_next_boundary():
    controller = activate()
    initial = controller.to_signal_snapshot()
    with pytest.raises(RuntimeError):
        controller.build_cycle_plan(COUNTS, cycle_no=2)
    with pytest.raises(RuntimeError):
        controller.start_next_cycle(COUNTS, cycle_no=2, started_at=0, conflict_clear=True)
    assert controller.to_signal_snapshot() == initial
    for _ in range(68):
        controller.tick(conflict_clear=True)
    terminal = controller.to_signal_snapshot()
    with pytest.raises(RuntimeError):
        controller.start_next_cycle(COUNTS, cycle_no=2, started_at=67, conflict_clear=True)
    with pytest.raises(ValueError):
        controller.start_next_cycle(COUNTS, cycle_no=3, started_at=68, conflict_clear=True)
    assert controller.to_signal_snapshot() == terminal


@pytest.mark.parametrize('direction,error', [('X', ValueError), ('n', ValueError), (None, TypeError)])
def test_invalid_direction_and_tick_leave_state_unchanged(direction, error):
    controller = activate()
    before = controller.to_signal_snapshot()
    with pytest.raises(error):
        controller.is_green_for(direction)
    with pytest.raises(TypeError):
        controller.tick(conflict_clear=1)
    assert controller.to_signal_snapshot() == before
