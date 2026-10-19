from dataclasses import FrozenInstanceError
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import pytest
from src.core.simulation import SimulationEngine
from src.models.config import Config, Motion2DConfig


def config(**kwargs):
    return Config(rates_per_min=dict.fromkeys('NSEW', 0), **kwargs)


def test_reports_are_readonly_and_do_not_reallocate_or_advance(monkeypatch):
    from src.core import algorithms
    engine = SimulationEngine(config(initial_queue=dict(N=3, S=0, E=0, W=0)))
    engine.start()
    engine.run_ticks(7)
    before = engine.snapshot().to_dict()
    def forbidden(*args):
        raise AssertionError('Render must not allocate another plan')
    monkeypatch.setattr(algorithms, 'allocate_green_adaptive', forbidden)
    for _ in range(3):
        report = engine.dashboard_data()
        assert report.summary is None
        assert report.current_green == (50, 10)
        assert report.previous_green is None
        assert report.cycle_metrics[-1].provisional
        assert report.cycle_metrics[-1].actual_cycle_s == 7
        assert report.snapshot.to_dict() == before
    with pytest.raises(FrozenInstanceError):
        report.current_green = (1, 1)
    engine.stop()
    report = engine.dashboard_data()
    with pytest.raises(TypeError):
        report.summary['status'] = 'RUNNING'
    assert isinstance(engine.summary(), dict)


def test_report_retains_closed_cycles_and_current_previous_green():
    engine = SimulationEngine(config(initial_queue=dict(N=3, S=0, E=0, W=0)))
    engine.start()
    engine.run_ticks(69)
    report = engine.dashboard_data()
    assert report.current_green == (30, 30)
    assert report.previous_green == (50, 10)
    assert [m.provisional for m in report.cycle_metrics] == [False, True]
    assert report.cycle_metrics[0] == engine.stats.cycles[0]
    assert report.cycle_metrics[0].departures == 3
    assert report.cycle_metrics[1].actual_cycle_s == 1
    assert report.queue_series == tuple((t.sim_time, sum(t.metrics.queue_lengths.values()))
                                       for t in engine.stats.ticks)


@pytest.mark.parametrize('policy', ['adaptive', 'fixed'])
def test_cycle_command_preserves_paused_and_finishes_at_exact_boundary(policy):
    engine = SimulationEngine(config(cycles_to_run=2), policy=policy)
    assert not engine.has_started
    with pytest.raises(RuntimeError):
        engine.run_until_cycle_end()
    engine.start()
    with pytest.raises(RuntimeError):
        engine.run_until_cycle_end()
    engine.pause()
    snap = engine.run_until_cycle_end()
    assert snap.sim_time == 68
    assert engine.session_state == 'PAUSED'
    assert len(engine.stats.cycles) == 1
    snap = engine.run_until_cycle_end()
    assert snap.sim_time == 136
    assert engine.session_state == 'COMPLETED'
    assert not engine.cycle_metrics()[-1].provisional
    assert engine.dashboard_data().previous_green == (30, 30)
    engine.reset()
    assert not engine.has_started
    assert engine.sim_time == 0
    assert engine.dashboard_data().summary is None


def test_cycle_command_includes_clearance_and_uses_no_fixed_tick_count():
    engine = SimulationEngine(config(initial_queue=dict(N=0, S=0, E=4, W=0),
        motion_2d=Motion2DConfig(max_speed_mps=.5, clearance_limit_s=100)))
    engine.start()
    engine.pause()
    engine.run_until_cycle_end()
    metric = engine.stats.cycles[0]
    assert metric.actual_cycle_s > 68
    assert metric.clearance_hold_s > 0
    assert engine.sim_time == metric.actual_cycle_s
    assert engine.session_state == 'PAUSED'


def test_cycle_command_stops_on_clearance_error():
    engine = SimulationEngine(config(initial_queue=dict(N=1, S=0, E=1, W=0), startup_delay_s=0,
        motion_2d=Motion2DConfig(max_speed_mps=.1, stop_margin_m=.05, clearance_limit_s=2)))
    engine.start()
    engine.pause()
    snap = engine.run_until_cycle_end()
    assert engine.session_state == 'ERROR'
    assert snap.sim_time == 37
    assert set(snap.signals.signal_colors.values()) == {'RED'}
    assert engine.dashboard_data().summary['status'] == 'ERROR'
    assert engine.cycle_metrics()[-1].provisional


def test_cycle_activation_reporting_failure_keeps_original_message(monkeypatch):
    engine = SimulationEngine(config())
    engine.start()
    engine.run_ticks(67)
    def fail(*args):
        raise RuntimeError('Reporting failed after activation')
    monkeypatch.setattr(engine.stats, 'begin_cycle', fail)
    snap = engine.tick()
    assert engine.error_message == 'Reporting failed after activation'
    assert engine.session_state == 'ERROR'
    assert set(snap.signals.signal_colors.values()) == {'RED'}


def test_gap_report_measures_pairs_without_inventing_a_zero():
    assert SimulationEngine(config()).dashboard_data().observed_min_gap_m is None
    engine = SimulationEngine(config(initial_queue=dict(N=2, S=0, E=0, W=0)))
    report = engine.dashboard_data()
    assert report.observed_min_gap_m == pytest.approx(2)
    assert report.conflict_occupancy_count == 0
