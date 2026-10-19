"""Headway là ràng buộc cả phiên, áp dụng cho hai policy và cả bốn làn."""
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import pytest

from src.core.comparison import compare_policies
from src.core.simulation import SimulationEngine
from src.models.config import Config


def crossing_times(engine, direction):
    vehicles = (*engine.movement.active_crossing.values(), *engine.movement.exited_vehicles)
    return sorted(v.crossed_stop_t for v in vehicles if v.origin == direction)


def short_cycle_config(direction='N'):
    return Config(
        rates_per_min=dict.fromkeys('NSEW', 0),
        initial_queue={d: 3 if d == direction else 0 for d in 'NSEW'},
        green_budget_s=20, min_green_s=3, yellow_s=1, all_red_s=1,
        startup_delay_s=0, headway_s=13, cycles_to_run=2,
    )


@pytest.mark.parametrize('policy', ['adaptive', 'fixed'])
@pytest.mark.parametrize('direction', 'NSEW')
@pytest.mark.parametrize('headway', [13, 100])
def test_headway_holds_across_cycles_for_every_lane_and_policy(policy, direction, headway):
    if headway == 13:
        config, horizon = short_cycle_config(direction), 72
    else:
        config = Config(
            rates_per_min=dict.fromkeys('NSEW', 0),
            initial_queue={d: 3 if d == direction else 0 for d in 'NSEW'},
            headway_s=100, cycles_to_run=2,
        )
        horizon = 240
    engine = SimulationEngine(config, policy=policy, horizon_s=horizon)
    engine.start()
    engine.run_ticks(horizon)

    assert engine.session_state == 'STOPPED'
    assert engine.cycle_index >= 3
    times = crossing_times(engine, direction)
    assert len(times) >= 2  # Có ít nhất một khoảng cách giữa hai crossing để xét.
    assert all(b - a >= headway - 1e-9 for a, b in zip(times, times[1:])), times
    assert engine.stats.crossed_stop_total == len(times)
    assert engine.summary()['min_gap_violations'] == 0


@pytest.mark.parametrize('policy', ['adaptive', 'fixed'])
def test_reset_starts_new_crossing_history(policy):
    config = Config(
        rates_per_min=dict.fromkeys('NSEW', 0),
        initial_queue=dict(N=2, S=0, E=0, W=0), headway_s=100,
    )
    engine = SimulationEngine(config, policy=policy, horizon_s=140)
    engine.start()
    engine.run_ticks(80)
    before_reset = crossing_times(engine, 'N')
    assert len(before_reset) == 1

    engine.reset()
    engine.start()
    engine.run_ticks(10)
    assert crossing_times(engine, 'N') == before_reset
    assert engine.stats.crossed_stop_total == 1


def test_comparison_reproduces_both_policies_with_valid_headway():
    config, horizon = short_cycle_config(), 48
    result = compare_policies(config, horizon)
    assert result.comparable
    assert result.adaptive.arrivals_by_direction == result.fixed.arrivals_by_direction

    for policy, run in [('adaptive', result.adaptive), ('fixed', result.fixed)]:
        engine = SimulationEngine(config, policy=policy, arrival_tape=result.arrivals,
                                  horizon_s=horizon)
        engine.start()
        engine.run_ticks(horizon)
        times = crossing_times(engine, 'N')
        assert len(times) >= 2
        assert all(b - a >= config.headway_s - 1e-9 for a, b in zip(times, times[1:])), times
        assert engine.summary() == dict(run.summary)
        if policy == 'adaptive':
            assert times[:2] == pytest.approx([.8, 14.6])
            assert times[2] >= 27.6 - 1e-9
