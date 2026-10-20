"""Compare actual browser-style runs and export reproducible, honest CSV reports."""

import csv
from dataclasses import replace
import io
import json
from pathlib import Path
import sys

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.core.comparison import compare_finished_run, compare_policies, comparison_csv_text, comparison_rows
from src.core.simulation import SimulationEngine
from src.models.config import Config


def finish(config, ticks):
    engine = SimulationEngine(config)
    engine.start()
    engine.run_ticks(ticks)
    if engine.session_state == 'RUNNING':
        engine.stop()
    return engine


@pytest.mark.parametrize('cycles', [1, 2, 3])
def test_comparison_replays_real_arrivals_and_does_not_change_original_run(cycles):
    config = Config(id='CUSTOM-7', name='Kịch bản mới', seed=2026, cycles_to_run=cycles,
                    initial_queue=dict(N=12, S=8, E=2, W=1),
                    rates_per_min=dict(N=24, S=18, E=6, W=3))
    engine = finish(config, cycles * 68)
    assert engine.session_state == 'COMPLETED'
    original_summary = engine.summary()
    original_snapshot = engine.snapshot().to_dict()
    result = compare_finished_run(config, original_summary)

    assert result.comparable
    assert result.horizon_s == engine.sim_time
    assert result.adaptive.summary == original_summary
    assert result.adaptive.arrivals_by_direction == result.fixed.arrivals_by_direction
    assert result.fixed.summary['simulation_seconds'] == engine.sim_time
    assert result.fixed.summary['initial_total'] == original_summary['initial_total']
    assert engine.summary() == original_summary
    assert engine.snapshot().to_dict() == original_snapshot
    original_summary['departed_vehicles'] = -1
    assert result.adaptive.summary['departed_vehicles'] >= 0


def test_completed_run_retains_completed_status_and_config_in_csv():
    config = Config(id='JCT-NEW', name='Ngã tư mới, "giờ cao điểm"', seed=17, cycles_to_run=1,
                    rates_per_min=dict.fromkeys('NSEW', 0))
    engine = finish(config, 100)
    assert engine.session_state == 'COMPLETED'
    result = compare_finished_run(config, engine.summary())
    report = comparison_csv_text(result, config, run_id='browser-run-7',
                                 started_at_iso='2026-10-19T12:00:00+07:00')
    rows = list(csv.DictReader(io.StringIO(report)))

    assert rows and all(None not in row for row in rows)
    assert all(row['run_id'] == 'browser-run-7' for row in rows)
    assert all(row['config_name'] == config.name for row in rows)
    assert all(json.loads(row['config_json']) == config.to_dict() for row in rows)
    assert all(row['seed'] == '17' and row['horizon_s'] == '68' for row in rows)
    assert all(row['adaptive_status'] == 'COMPLETED' and row['fixed_status'] == 'STOPPED' for row in rows)
    assert all(row['fixed_green_ns_s'] == row['fixed_green_ew_s'] == '30' for row in rows)
    by_metric = {row['metric']: row for row in rows}
    assert by_metric['departed_vehicles']['adaptive'] == '0'
    assert by_metric['departed_vehicles']['improvement_pct'] == ''
    assert by_metric['avg_stopped_delay_s']['adaptive'] == ''
    assert by_metric['avg_stopped_delay_s']['adaptive_minus_fixed'] == ''


def test_percentages_use_correct_direction_and_hold_is_context_only():
    config = Config(initial_queue=dict(N=16, S=12, E=2, W=1),
                    rates_per_min=dict(N=24, S=20, E=6, W=6), seed=0)
    result = compare_policies(config, 180)
    rows = {row['metric']: row for row in comparison_rows(result)}
    departures = rows['departed_vehicles']
    assert departures['adaptive'] == 108
    assert departures['fixed'] == 91
    assert departures['adaptive_minus_fixed'] == 17
    assert departures['improvement_pct'] == pytest.approx(17 / 91 * 100)
    queue = rows['avg_queue']
    assert queue['improvement_pct'] == pytest.approx((queue['fixed'] - queue['adaptive']) / queue['fixed'] * 100)
    assert queue['improvement_pct'] > 0
    assert rows['clearance_hold_s']['improvement_pct'] is None
    assert rows['cycles_completed']['improvement_pct'] is None


def test_incomplete_fixed_run_exports_diagnostics_without_claiming_improvement():
    config = Config(cycles_to_run=1)
    result = compare_finished_run(config, finish(config, 100).summary())
    failed_fixed = replace(result.fixed, reached_horizon=False,
                           summary=dict(result.fixed.summary, status='ERROR',
                                        simulation_seconds=5, error_message='Clearance timeout'))
    incomplete = replace(result, fixed=failed_fixed)
    assert not incomplete.comparable
    report = comparison_csv_text(incomplete, config, run_id='diagnostic',
                                 started_at_iso='2026-10-19T12:00:00+07:00')
    rows = list(csv.DictReader(io.StringIO(report)))
    assert all(row['comparable'] == 'False' for row in rows)
    assert all(row['fixed_error'] == 'Clearance timeout' for row in rows)
    assert all(row['adaptive_minus_fixed'] == row['improvement_pct'] == '' for row in rows)


@pytest.mark.parametrize('status', ['RUNNING', 'PAUSED', 'STOPPED', 'ERROR'])
def test_unfinished_or_error_sessions_are_rejected(status):
    engine = finish(Config(), 5)
    with pytest.raises(ValueError, match='Adaptive'):
        compare_finished_run(Config(), dict(engine.summary(), status=status))


def test_zero_duration_and_changed_configuration_are_rejected():
    config = Config(cycles_to_run=1)
    engine = SimulationEngine(config)
    engine.start()
    engine.stop()
    with pytest.raises(ValueError):
        compare_finished_run(config, engine.summary())
    summary = finish(config, 90).summary()
    changed = Config(seed=config.seed + 1, cycles_to_run=1)
    with pytest.raises(ValueError, match='tái lập'):
        compare_finished_run(changed, summary)


@pytest.mark.parametrize('ticks', [1, 40, 68, 90])
def test_early_stop_is_rejected_even_at_a_cycle_boundary(ticks):
    config = Config(cycles_to_run=2)
    engine = finish(config, ticks)
    assert engine.session_state == 'STOPPED'
    with pytest.raises(ValueError, match='đủ số chu kỳ'):
        compare_finished_run(config, engine.summary())


def test_completed_label_without_all_configured_cycles_is_rejected():
    config = Config(cycles_to_run=2)
    summary = finish(config, 68).summary()
    with pytest.raises(ValueError, match='đủ số chu kỳ'):
        compare_finished_run(config, dict(summary, status='COMPLETED'))
