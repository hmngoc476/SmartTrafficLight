from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from statistics import mean
import pytest
from src.core.simulation import SimulationEngine
from src.models.config import Config, Motion2DConfig


def test_summary_before_ticks_and_no_departures_uses_null_averages():
    engine = SimulationEngine(Config(rates_per_min=dict.fromkeys('NSEW', 0)))
    before = engine.summary()
    assert before['avg_queue'] is None
    assert before['avg_wait_departed_s'] is None
    assert before['avg_stopped_delay_s'] is None
    assert before['throughput_per_min'] is None
    engine.start(); engine.run_ticks(68); engine.stop()
    result = engine.summary()
    assert result['avg_queue'] == 0
    assert result['avg_wait_departed_s'] is None
    assert result['throughput_per_min'] == 0
    before['max_queue'] = 999
    assert engine.summary()['max_queue'] == 0


def test_departure_averages_use_unique_crossed_vehicles_only():
    engine = SimulationEngine(Config(rates_per_min=dict.fromkeys('NSEW', 0),
                                    initial_queue=dict(N=3, S=0, E=1, W=0)))
    engine.start(); engine.run_ticks(15); engine.stop()
    vehicles = (*engine.movement.active_crossing.values(), *engine.movement.exited_vehicles)
    result = engine.summary()
    assert result['departed_vehicles'] == len(vehicles) == 3
    assert result['remaining_vehicles'] == 1
    assert result['avg_wait_departed_s'] == pytest.approx(mean(v.elapsed_to_stopline() for v in vehicles))
    assert result['avg_stopped_delay_s'] == pytest.approx(mean(v.stopped_delay_s for v in vehicles))
    for v in vehicles: engine.stats.record_departure(v)
    assert engine.summary() == result  # ghi lại sự kiện không cộng gấp đôi
    assert result['throughput_per_min'] == 12
    assert result['cycles_completed'] == 0


def test_creeping_vehicle_counts_stopped_threshold_only_before_crossing():
    engine = SimulationEngine(Config(rates_per_min=dict.fromkeys('NSEW', 0),
                                    initial_queue=dict(N=1, S=0, E=0, W=0), startup_delay_s=0,
                                    motion_2d=Motion2DConfig(max_speed_mps=.05)))
    engine.start(); engine.run_ticks(1)
    v = engine._lanes['N'].peek()
    assert v.speed_mps == pytest.approx(.05)
    assert v.stopped_delay_s == pytest.approx(1)
    while not engine.movement.active_crossing: engine.run_ticks(1)
    v = next(iter(engine.movement.active_crossing.values()))
    saved = v.stopped_delay_s
    engine.run_ticks(1)
    assert v.stopped_delay_s == saved


def test_hold_and_queue_statistics_across_two_cycles():
    engine = SimulationEngine(Config(rates_per_min=dict.fromkeys('NSEW', 0), cycles_to_run=2,
                                    initial_queue=dict.fromkeys('NSEW', 100),
                                    motion_2d=Motion2DConfig(max_speed_mps=2)))
    engine.start(); engine.run_ticks(200)
    assert engine.session_state == 'COMPLETED'
    cycles = engine.stats.cycles
    assert [c.actual_cycle_s for c in cycles] == [78, 78]
    assert [c.clearance_hold_s for c in cycles] == [10, 10]
    result = engine.summary()
    assert result['clearance_hold_s'] == 20
    assert result['clearance_hold_s'] != engine.controller.clearance_hold_s
    tick_queues = [sum(t.metrics.queue_lengths.values()) for t in engine.stats.ticks]
    assert result['avg_queue'] == pytest.approx(mean(tick_queues))
    assert result['max_queue'] == max([400, *tick_queues])
    for c in cycles:
        sample = tick_queues[c.started_at_s:c.ended_at_s]
        assert c.avg_queue_cycle == pytest.approx(mean(sample))
    assert result['avg_green_ns_s'] == 30
    assert result['avg_green_ew_s'] == 30


def test_partial_cycle_hold_is_kept_at_stop():
    engine = SimulationEngine(Config(rates_per_min=dict.fromkeys('NSEW', 0),
                                    initial_queue=dict.fromkeys('NSEW', 100),
                                    motion_2d=Motion2DConfig(max_speed_mps=2)))
    engine.start(); engine.run_ticks(115); engine.stop()
    result = engine.summary()
    assert result['cycles_completed'] == 1
    assert result['clearance_hold_s'] == 13
    assert result['simulation_seconds'] == 115
    assert result['status'] == 'STOPPED'
