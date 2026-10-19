"""Hồi quy các lỗi review và luồng tích hợp đến hết task 17/10."""

from dataclasses import FrozenInstanceError
from pathlib import Path
import sys
from unittest.mock import patch

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.core import algorithms
from src.core.controller import TrafficLightController
from src.core.manager import ConfigManager
from src.core.movement import MovementEngine
from src.core.simulation import SimulationEngine
from src.models.config import Config
from src.models.lane import Lane
from src.models.snapshot import SimulationSnapshot


def config(**kwargs):
    return Config(rates_per_min=dict.fromkeys('NSEW', 0), initial_queue=dict.fromkeys('NSEW', 0), **kwargs)


def test_initial_queue_at_stop_margin_and_new_arrivals_at_approach():
    cfg = config()
    cfg.initial_queue['N'] = 2
    engine = SimulationEngine(cfg)
    assert [v.s_front_m for v in engine.snapshot().vehicles] == pytest.approx([-.5, -7])
    assert all(v.speed_mps == 0 for v in engine.snapshot().vehicles)
    arrival = engine.movement.spawn_and_enqueue('N', 0)
    assert arrival.s_front_m == -60


def test_crossing_moves_once_and_timestamps_end_of_substep():
    cfg = config(startup_delay_s=0)
    lanes = {d: Lane(d) for d in 'NSEW'}
    movement = MovementEngine(cfg, lanes)
    controller = TrafficLightController(cfg)
    controller.start_next_cycle(dict.fromkeys('NSEW', 0), cycle_no=1, started_at=0, conflict_clear=True)
    # Xe tồn ban đầu: TC-23 ngày 18 chặn xe MỚI trước arrival+1s.
    # Test này chỉ kiểm tra một lần cập nhật/crossing trong mỗi substep.
    movement.initialize_queue('N', 1)
    vehicle = lanes['N'].peek()
    vehicle.update_motion(-.01, 1)
    lanes['N'].reset_green_clock(0, 0, cfg.headway_s)
    movement.advance_substep(0, .2, controller)
    assert vehicle.s_front_m == pytest.approx(.27)
    assert vehicle.speed_mps == pytest.approx(1.4)
    assert vehicle.crossed_stop_t == pytest.approx(.2)
    assert movement.active_crossing[vehicle.vehicle_id] is vehicle
    assert lanes['N'].count() == 0
    movement.advance_substep(.2, .2, controller)
    assert vehicle.s_front_m == pytest.approx(.63)
    assert vehicle.crossed_stop_t == pytest.approx(.2)
    assert len(movement.active_crossing) == 1


def test_poisson_direction_order_five_substeps_and_arrival_counters():
    cfg = config()
    cfg.rates_per_min = dict(N=6, S=12, E=18, W=24)
    engine = SimulationEngine(cfg)
    engine.start()
    with patch('src.core.simulation.poisson_sample', return_value=1) as sampler, patch.object(engine.movement, 'advance_substep', wraps=engine.movement.advance_substep) as movement:
        snapshot = engine.tick()
    assert [c.args[0] for c in sampler.call_args_list] == pytest.approx([.1, .2, .3, .4])
    assert [c.kwargs['t'] for c in movement.call_args_list] == pytest.approx([0, .2, .4, .6, .8])
    assert len(movement.call_args_list) == 5
    assert snapshot.metrics.total_arrivals == 4
    assert engine.stats.arrivals_total == 4
    assert {v.origin for v in snapshot.vehicles} == set('NSEW')


def test_pause_step_advances_once_then_resume():
    engine = SimulationEngine(config())
    engine.start()
    engine.tick()
    engine.pause()
    before = engine.snapshot().to_dict()
    assert engine.snapshot().to_dict() == before
    with pytest.raises(RuntimeError):
        engine.tick()
    snapshot = engine.run_ticks(1)
    assert snapshot.sim_time == 2
    assert snapshot.session_state == 'PAUSED'
    assert len(engine.stats.ticks) == 2
    engine.resume()
    assert engine.tick().sim_time == 3


def test_stop_requires_new_session_and_cannot_bypass_completion():
    engine = SimulationEngine(config(cycles_to_run=1))
    engine.start()
    engine.tick()
    engine.stop()
    stopped = engine.snapshot().to_dict()
    for action in [engine.start, engine.resume, engine.tick, lambda: engine.run_ticks(1)]:
        with pytest.raises(RuntimeError):
            action()
    assert engine.snapshot().to_dict() == stopped
    engine.reset()
    engine.start()
    engine.run_ticks(68)
    assert engine.session_state == 'COMPLETED'
    with pytest.raises(RuntimeError):
        engine.stop()
    with pytest.raises(RuntimeError):
        engine.start()
    assert engine.session_state == 'COMPLETED'


@pytest.mark.parametrize('count', [0, -1, True, 1.5, '1'])
def test_invalid_run_count_keeps_state(count):
    engine = SimulationEngine(config())
    engine.start()
    before = engine.snapshot().to_dict()
    with pytest.raises((TypeError, ValueError)):
        engine.run_ticks(count)
    assert engine.snapshot().to_dict() == before


def test_reset_replays_seed_and_detaches_original_configuration():
    cfg = config()
    cfg.rates_per_min = dict(N=20, S=10, E=30, W=8)
    cfg.initial_queue['N'] = 2
    engine = SimulationEngine(cfg)
    initial = engine.snapshot().to_dict()
    engine.start()
    first = [engine.tick().to_dict() for _ in range(40)]
    cfg.initial_queue['N'] = 100
    cfg.rates_per_min['N'] = 0
    engine.reset()
    assert engine.snapshot().to_dict() == initial
    engine.start()
    assert [engine.tick().to_dict() for _ in range(40)] == first


def test_fifo_startup_headway_and_single_departure_per_vehicle():
    cfg = config()
    cfg.initial_queue['N'] = 3
    engine = SimulationEngine(cfg)
    original = [v.vehicle_id for v in engine.snapshot().vehicles]
    engine.start()
    crossed = {}
    for _ in range(20):
        engine.tick()
        for vehicle in (*engine.movement.active_crossing.values(), *engine.movement.exited_vehicles):
            crossed.setdefault(vehicle.vehicle_id, vehicle.crossed_stop_t)
    assert list(crossed) == original
    times = list(crossed.values())
    assert times[0] >= cfg.startup_delay_s
    assert all(b - a >= cfg.headway_s - 1e-9 for a, b in zip(times, times[1:]))
    assert engine.stats.crossed_stop_total == 3
    assert engine.snapshot().metrics.crossed_stop_total == 3


def test_already_crossed_vehicle_keeps_moving_in_yellow():
    cfg = config(green_budget_s=4, min_green_s=1, yellow_s=1, all_red_s=1, startup_delay_s=0)
    cfg.initial_queue['N'] = 1
    engine = SimulationEngine(cfg)
    engine.start()
    yellow = engine.run_ticks(3)
    assert yellow.signals.current_segment == 'NS_YELLOW'
    vehicle = yellow.vehicles[0]
    after = engine.tick()
    same_vehicle = next(v for v in after.vehicles if v.vehicle_id == vehicle.vehicle_id)
    assert same_vehicle.s_front_m > vehicle.s_front_m
    assert after.metrics.crossed_stop_total == yellow.metrics.crossed_stop_total == 1


def test_cycles_close_before_new_allocation_and_no_extra_cycle_after_completed():
    with patch.object(algorithms, 'allocate_green_adaptive', wraps=algorithms.allocate_green_adaptive) as allocate:
        engine = SimulationEngine(config(cycles_to_run=2))
        engine.start()
        engine.run_ticks(67)
        assert allocate.call_count == 1
        assert engine.stats.cycles == ()
        boundary = engine.tick()
        assert boundary.cycle_index == 2
        assert allocate.call_count == 2
        assert len(engine.stats.cycles) == 1
        first = engine.stats.cycles[0]
        assert (first.cycle_index, first.started_at_s, first.ended_at_s, first.actual_cycle_s) == (1, 0, 68, 68)
        assert first.q_ns_end == first.q_ew_end == first.arrivals_ns == first.departed_ns == 0
        assert (first.green_ns_s, first.green_ew_s) == (30, 30)
        assert engine.stats.ticks[-1].cycle_index == 1
        with pytest.raises(FrozenInstanceError):
            first.green_ns_s = 99
        final = engine.run_ticks(100)
        assert final.session_state == 'COMPLETED'
        assert final.sim_time == 136
        assert len(engine.stats.ticks) == 136
        assert len(engine.stats.cycles) == 2
        assert allocate.call_count == 2


def test_failed_cycle_activation_stays_terminal_red_and_does_not_increment(monkeypatch):
    engine = SimulationEngine(config(cycles_to_run=2))
    engine.start()
    engine.run_ticks(67)

    def fail(*args, **kwargs):
        raise RuntimeError('activation failed')

    monkeypatch.setattr(engine.controller, 'start_next_cycle', fail)
    snapshot = engine.tick()
    assert snapshot.session_state == 'ERROR'
    assert snapshot.cycle_index == 1
    assert snapshot.signals.current_segment == 'ALL_RED_2'
    assert set(snapshot.signals.signal_colors.values()) == {'RED'}
    assert len(engine.stats.cycles) == 1


def test_storage_config_engine_snapshot_pipeline(tmp_path):
    manager = ConfigManager(tmp_path / 'junctions.json')
    cfg = config()
    cfg.initial_queue['N'] = 2
    assert manager.create_config(cfg.to_dict())[0]
    loaded = Config.from_dict(ConfigManager(manager.filepath).get_config(cfg.id))
    engine = SimulationEngine(loaded)
    engine.start()
    for _ in range(20):
        snapshot = engine.tick()
        assert SimulationSnapshot.from_dict(snapshot.to_dict()).to_dict() == snapshot.to_dict()
        metrics = snapshot.metrics
        assert metrics.initial_total + metrics.total_arrivals == sum(metrics.queue_lengths.values()) + metrics.crossed_stop_total
        assert metrics.crossed_stop_total == metrics.active_crossing_count + metrics.exited_world_total
        assert len({v.vehicle_id for v in snapshot.vehicles}) == len(snapshot.vehicles)


def test_cycle_statistics_account_for_real_arrivals_and_departures():
    cfg = config(cycles_to_run=2)
    cfg.initial_queue['N'] = 3
    cfg.rates_per_min = dict(N=30, S=20, E=15, W=10)
    engine = SimulationEngine(cfg)
    engine.start()
    while not engine.stats.cycles:
        engine.tick()
    cycle = engine.stats.cycles[0]
    assert cycle.q_ns_start + cycle.arrivals_ns - cycle.departed_ns == cycle.q_ns_end
    assert cycle.q_ew_start + cycle.arrivals_ew - cycle.departed_ew == cycle.q_ew_end
    assert cycle.actual_cycle_s == engine.stats.ticks[-1].sim_time
    summary = engine.stats.summary()
    assert summary['crossed_stop_total'] == engine.snapshot().metrics.crossed_stop_total
    assert summary['cycles_completed'] == 1
