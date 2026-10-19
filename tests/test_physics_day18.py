"""Nghiệm thu hình bao, spawn, crossing, exit và guard trên Core thật."""
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import pytest
from src.core.geometry import Geometry
from src.core.simulation import SimulationEngine
from src.core.controller import TrafficLightController
from src.models.config import Config, Motion2DConfig
from src.models.vehicle import Vehicle


def cfg(**kwargs):
    return Config(rates_per_min=dict.fromkeys('NSEW', 0), **kwargs)


@pytest.mark.parametrize('width', [3.6, 4, 8, 16, 40])
def test_config_and_engine_agree_on_feasible_lane_geometry(width):
    config = cfg(motion_2d=Motion2DConfig(intersection_width_m=width))
    geometry = SimulationEngine(config).snapshot().geometry
    assert geometry.vehicle_width_m == 1.8
    assert geometry.lane_offset_m >= .9
    assert geometry.lane_offset_m + .9 <= width / 2 + 1e-9
    assert set(config.to_dict()['motion_2d']) == set(Motion2DConfig().__dict__)


@pytest.mark.parametrize('width', [.1, 1.8, 3.59])
def test_physically_impossible_road_is_rejected_before_engine(width):
    with pytest.raises(ValueError, match='3.6'):
        Motion2DConfig(intersection_width_m=width)


@pytest.mark.parametrize('direction', ['N', 'S', 'E', 'W'])
def test_full_body_occupies_until_rear_clears_closed_region(direction):
    g = Geometry.for_motion(Motion2DConfig())
    assert g.occupies_conflict(direction, 18, 4.5)  # đầu đã ra, đuôi còn trong
    assert g.occupies_conflict(direction, 20.5, 4.5)  # đuôi chạm biên
    assert not g.occupies_conflict(direction, 20.500001, 4.5)
    assert not g.outside_world(direction, 80.5, 4.5)  # đuôi chạm +/-68m
    assert g.outside_world(direction, 80.500001, 4.5)


def test_missing_physical_width_cannot_report_region_clear():
    with pytest.raises(ValueError, match='bề rộng'):
        Geometry().occupies_conflict('N', 2, 4.5)


@pytest.mark.parametrize('seed', [0, 1, 42, 2026])
def test_short_approach_spawns_behind_active_and_preserves_conservation(seed):
    config = Config(seed=seed, rates_per_min=dict(N=30, S=0, E=0, W=0),
                    initial_queue=dict(N=1, S=0, E=0, W=0), startup_delay_s=0,
                    motion_2d=Motion2DConfig(approach_visible_m=.1))
    engine = SimulationEngine(config)
    engine.start()
    for _ in range(30):
        m = engine.run_ticks(1).metrics
        engine.movement.assert_physical_invariants()
        assert m.initial_total + m.total_arrivals == sum(m.queue_lengths.values()) + m.crossed_stop_total
        assert m.crossed_stop_total == m.active_crossing_count + m.exited_world_total
    assert engine.summary()['min_gap_violations'] == 0


def test_new_arrival_cannot_cross_before_one_second_TC23():
    config = Config(seed=0, rates_per_min=dict(N=30, S=0, E=0, W=0), startup_delay_s=0,
                    motion_2d=Motion2DConfig(approach_visible_m=.1))
    engine = SimulationEngine(config)
    engine.start()
    engine.run_ticks(10)
    vehicles = (*engine.movement.active_crossing.values(), *engine.movement.exited_vehicles)
    assert vehicles
    assert all(v.crossed_stop_t >= v.arrival_t + 1 - 1e-9 for v in vehicles)


@pytest.mark.parametrize('direction', ['N', 'S', 'E', 'W'])
def test_real_vehicle_exit_uses_world_rear_and_does_not_count_second_crossing(direction):
    config = cfg(initial_queue={d: int(d == direction) for d in 'NSEW'}, startup_delay_s=0)
    engine = SimulationEngine(config)
    engine.start()
    while not engine.movement.exited_vehicles:
        engine.run_ticks(1)
    vehicle = engine.movement.exited_vehicles[0]
    g = Geometry.for_motion(config.motion_2d)
    assert g.outside_world(direction, vehicle.s_front_m, vehicle.length_m)
    assert engine.stats.crossed_stop_total == 1
    assert engine.snapshot().metrics.exited_world_total == 1
    assert vehicle.exited_world_t >= vehicle.crossed_stop_t


def test_real_occupancy_causes_timeout_and_all_red():
    config = cfg(initial_queue=dict(N=1, S=0, E=1, W=0), startup_delay_s=0,
                 motion_2d=Motion2DConfig(max_speed_mps=.1, stop_margin_m=.05, clearance_limit_s=2))
    engine = SimulationEngine(config)
    engine.start()
    engine.run_ticks(34)
    assert engine.movement.conflict_occupancy_count == 1
    assert engine.controller.current_segment_code == 'ALL_RED_1'
    for _ in range(3):
        snap = engine.run_ticks(1)
        assert set(snap.signals.signal_colors.values()) == {'RED'}
    assert engine.session_state == 'ERROR'
    assert engine.sim_time == 37
    assert engine.summary()['clearance_hold_s'] == 3


def test_unknown_owner_fails_safe_and_cannot_continue():
    engine = SimulationEngine(cfg())
    engine.start()
    # Inject a foreign vehicle to prove ID membership is checked, not only counts.
    engine._lanes['N'].enqueue(Vehicle('foreign', 'N'))
    with pytest.raises(AssertionError, match='kho'):
        engine.tick()
    assert engine.session_state == 'ERROR'
    assert set(engine.controller.to_signal_snapshot().signal_colors.values()) == {'RED'}
    assert engine.error_message
    with pytest.raises(RuntimeError):
        engine.tick()
    engine.reset()
    engine.start()
    assert engine.tick().sim_time == 1


@pytest.mark.parametrize('segment', ['ALL_RED_1', 'ALL_RED_2'])
@pytest.mark.parametrize('limit', [.5, 2, 30])
def test_both_all_red_boundaries_timeout_without_conflicting_green(segment, limit):
    controller = TrafficLightController(cfg(motion_2d=Motion2DConfig(clearance_limit_s=limit)))
    controller.start_next_cycle(dict.fromkeys('NSEW',1),cycle_no=1,started_at=0,conflict_clear=True)
    while controller.current_segment_code != segment: controller.tick(conflict_clear=True)
    while not controller.in_error:
        controller.tick(conflict_clear=False)
        assert set(controller.to_signal_snapshot().signal_colors.values()) == {'RED'}
    assert controller.clearance_hold_s > limit
    assert not controller.cycle_complete


def test_real_all_red_2_releases_only_after_last_body_leaves():
    engine = SimulationEngine(cfg(initial_queue=dict(N=0,S=0,E=4,W=0),cycles_to_run=2,
                                  motion_2d=Motion2DConfig(max_speed_mps=.5,clearance_limit_s=100)))
    engine.start()
    held = False
    while engine.cycle_index == 1 and engine.sim_time < 180:
        snap = engine.run_ticks(1)
        if snap.signals.current_segment == 'ALL_RED_2' and snap.metrics.clearance_hold_s > 0:
            held = True
            assert set(snap.signals.signal_colors.values()) == {'RED'}
    assert held
    assert engine.session_state == 'RUNNING'
    assert engine.cycle_index == 2
    assert engine.movement.is_conflict_clear()
    assert engine.controller.current_segment_code == 'NS_GREEN'
    assert engine.stats.cycles[0].actual_cycle_s > 68
