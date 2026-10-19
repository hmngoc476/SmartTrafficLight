from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from collections import Counter
from dataclasses import FrozenInstanceError
import pytest
from src.core.algorithms import allocate_green_fixed
from src.core.arrivals import ArrivalTape
from src.core.comparison import compare_policies
from src.core.experiment import run_experiment
from src.core.simulation import SimulationEngine
from src.models.config import Config, Motion2DConfig


@pytest.mark.parametrize('budget,minimum,expected', [(60,10,(30,30)), (61,10,(30,31)), (20,10,(10,10))])
def test_fixed_budget(budget, minimum, expected):
    assert allocate_green_fixed(budget, minimum) == expected


@pytest.mark.parametrize('budget,minimum', [(15,10), (True,1), (60.,10), (60,0)])
def test_fixed_rejects_invalid_budget(budget, minimum):
    with pytest.raises((ValueError, TypeError)): allocate_green_fixed(budget, minimum)


def test_arrival_tape_is_detached_replayable_and_seeded():
    config = Config(seed=2026)
    assert ArrivalTape.from_config(config,100) == ArrivalTape.from_config(config,100)
    assert ArrivalTape.from_config(config,100) != ArrivalTape.from_config(Config(seed=42),100)
    rows = [[1,2,3,4]]
    tape = ArrivalTape(rows)
    rows[0][0] = 99
    assert tape.at(0) == (1,2,3,4)
    with pytest.raises(FrozenInstanceError): tape.rows = ()
    with pytest.raises(TypeError): tape.at(True)


@pytest.mark.parametrize('row', [(1,2,3), (1,-1,0,0), (1,True,0,0), (1.,0,0,0)])
def test_bad_arrival_tape(row):
    with pytest.raises((TypeError, ValueError)): ArrivalTape([row])


def test_policies_consume_the_same_arrivals_per_tick_and_direction():
    config = Config(seed=42)
    tape = ArrivalTape.from_config(config,90)
    for policy in ('adaptive','fixed'):
        engine = SimulationEngine(config,policy=policy,arrival_tape=tape,horizon_s=90)
        engine.start(); engine.run_ticks(90)
        assert engine.sim_time == 90
        vehicles = [v for lane in engine._lanes.values() for v in lane.get_vehicles()]
        vehicles += list(engine.movement.active_crossing.values()) + list(engine.movement.exited_vehicles)
        actual = Counter((v.arrival_t,v.origin) for v in vehicles)
        for t,row in enumerate(tape.rows):
            assert tuple(actual[t,d] for d in 'NSEW') == row


@pytest.mark.parametrize('horizon', [1,68,69,170])
def test_horizon_overrides_cycle_limit_and_reset_preserves_replay(horizon):
    config = Config(cycles_to_run=1, rates_per_min=dict.fromkeys('NSEW',0))
    tape = ArrivalTape.from_config(config,horizon)
    engine = SimulationEngine(config,policy='fixed',arrival_tape=tape,horizon_s=horizon)
    engine.start(); engine.run_ticks(horizon+10)
    first = engine.snapshot().to_dict()
    assert engine.sim_time == horizon
    assert engine.session_state == 'STOPPED'
    assert len(engine.stats.cycles) == horizon // 68
    engine.reset(); engine.start(); engine.run_ticks(horizon)
    assert engine.snapshot().to_dict() == first
    assert engine.policy == 'fixed'


def test_comparison_handles_unequal_cycles_but_equal_seconds():
    config = Config(initial_queue=dict(N=100,S=100,E=1,W=1), cycles_to_run=1,
                    motion_2d=Motion2DConfig(max_speed_mps=2))
    result = compare_policies(config,170)
    assert result.comparable
    for run in (result.adaptive,result.fixed):
        assert run.summary['simulation_seconds'] == 170
        assert run.summary['min_gap_violations'] == 0
        assert run.summary['initial_total']+run.summary['total_arrivals'] == run.summary['remaining_vehicles']+run.summary['crossed_stop_total']
    assert result.adaptive.arrivals_by_direction == result.fixed.arrivals_by_direction
    assert result.adaptive.summary['avg_green_ns_s'] != result.fixed.summary['avg_green_ns_s']
    with pytest.raises(TypeError): result.fixed.summary['max_queue'] = 999


def test_early_error_is_not_reported_as_complete_comparison():
    config = Config(initial_queue=dict(N=1,S=0,E=1,W=0),startup_delay_s=0,
                    rates_per_min=dict.fromkeys('NSEW',0),
                    motion_2d=Motion2DConfig(max_speed_mps=.1,stop_margin_m=.05,clearance_limit_s=2))
    result = compare_policies(config,80)
    assert not result.comparable
    assert not result.fixed.reached_horizon
    assert result.fixed.summary['status'] == 'ERROR'
    assert result.fixed.summary['simulation_seconds'] < 80


def test_aggregate_only_comparable_pairs_and_preserves_absent_wait():
    config = Config(rates_per_min=dict.fromkeys('NSEW',0))
    report = run_experiment({'empty':config}, [0,1,2],68)
    assert len(report['records']) == 3
    assert all(r['comparable'] for r in report['records'])
    for a in report['aggregates']:
        assert a['comparable_pairs'] == 3
        assert a['metrics']['departed_vehicles'] == dict(samples=3,mean=0,population_std=0)
        assert a['metrics']['avg_wait_departed_s'] == dict(samples=0,mean=None,population_std=None)


@pytest.mark.parametrize('kwargs', [dict(policy='unknown'),dict(horizon_s=0),
    dict(arrival_tape=ArrivalTape(((0,0,0,0),))),
    dict(arrival_tape=ArrivalTape(()),horizon_s=1)])
def test_invalid_run_options_fail_at_construction(kwargs):
    with pytest.raises((TypeError,ValueError)): SimulationEngine(Config(),**kwargs)
