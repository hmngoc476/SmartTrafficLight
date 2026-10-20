"""CSV contract, real statistics, interrupted writes and concurrent Streamlit sessions."""
from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
from pathlib import Path
import csv
import re
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import pytest
from src.core import history_storage as hs
from src.core.simulation import SimulationEngine
from src.models.config import Config

STAMP = '2026-10-19T12:00:00+07:00'


@pytest.fixture
def report():
    engine = SimulationEngine(Config(rates_per_min=dict.fromkeys('NSEW', 0),
                                    initial_queue=dict(N=2,S=0,E=0,W=0)))
    engine.start()
    engine.run_ticks(69)
    engine.stop()
    return engine.summary(), engine.cycle_metrics()


def read(path):
    with path.open(encoding='utf-8', newline='') as f:
        return list(csv.DictReader(f))


def save(report, tmp_path, run_id='run-1'):
    return hs.HistoryStorage.append_run(*report, tmp_path/'history.csv', tmp_path/'cycles.csv',
                                        run_id=run_id, started_at_iso=STAMP)


def test_written_headers_match_markdown_and_real_statistics(report, tmp_path):
    summary, cycles = report
    assert cycles[-1].provisional
    assert save(report, tmp_path)
    expected = re.findall(r'```text\n([^`]+)\n```',
                          (Path(__file__).resolve().parents[1]/'docs/ui_storage_contracts.md').read_text(encoding='utf-8'))
    assert len(expected) == 2
    for filename, header in zip(('history.csv','cycles.csv'), expected):
        with (tmp_path/filename).open(encoding='utf-8', newline='') as f:
            assert next(csv.reader(f)) == header.split(',')
    history = read(tmp_path/'history.csv')
    records = read(tmp_path/'cycles.csv')
    assert len(history) == len(records) == 1
    assert history[0]['crossed_stop_total'] == history[0]['departed_vehicles'] == '2'
    assert history[0]['initial_vehicles'] == '2'
    assert history[0]['arrived_vehicles'] == '0'
    assert history[0]['mode'] == 'adaptive'
    assert float(records[0]['avg_queue_cycle']) == cycles[0].avg_queue_cycle
    assert records[0]['actual_cycle_s'] == '68'
    text = hs.summary_csv_text(summary, cycles, run_id='run-1', started_at_iso=STAMP)
    assert text.splitlines()[0].split(',') == hs.HISTORY_HEADER
    assert 'provisional' not in text
    assert not save(report, tmp_path)
    assert len(read(tmp_path/'history.csv')) == len(read(tmp_path/'cycles.csv')) == 1


def test_no_samples_export_as_empty_cells_and_no_fake_cycle(tmp_path):
    engine = SimulationEngine(Config(rates_per_min=dict.fromkeys('NSEW',0)))
    engine.start()
    engine.stop()
    save((engine.summary(), engine.cycle_metrics()), tmp_path)
    row = read(tmp_path/'history.csv')[0]
    for name in ('avg_wait_departed_s','avg_stopped_delay_s','avg_queue'):
        assert row[name] == ''
    assert not (tmp_path/'cycles.csv').exists()


def test_partial_cycles_write_recovers_without_duplicates(report, tmp_path, monkeypatch):
    original = hs._write_atomic
    def fail_history(path, header, rows):
        if path.name == 'history.csv':
            raise OSError('Injected history failure after cycles succeeded')
        original(path,header,rows)
    with monkeypatch.context() as patch:
        patch.setattr(hs,'_write_atomic',fail_history)
        with pytest.raises(RuntimeError, match='Injected history failure'):
            save(report,tmp_path)
    assert len(read(tmp_path/'cycles.csv')) == 1
    assert not (tmp_path/'history.csv').exists()
    assert save(report,tmp_path)
    assert not save(report,tmp_path)
    assert len(read(tmp_path/'history.csv')) == len(read(tmp_path/'cycles.csv')) == 1


def test_history_already_exists_still_repairs_missing_cycles(report, tmp_path):
    save(report,tmp_path)
    before = (tmp_path/'history.csv').read_bytes()
    (tmp_path/'cycles.csv').unlink()
    assert save(report,tmp_path)
    assert (tmp_path/'history.csv').read_bytes() == before
    assert len(read(tmp_path/'cycles.csv')) == 1


def test_replace_failure_preserves_existing_files_and_removes_own_temp(report,tmp_path,monkeypatch):
    save(report,tmp_path)
    before = {p.name:p.read_bytes() for p in tmp_path.iterdir()}
    with monkeypatch.context() as patch:
        def fail(*args):
            raise OSError('Injected atomic replace failure')
        patch.setattr(hs.os,'replace',fail)
        with pytest.raises(RuntimeError,match='atomic replace'):
            save(report,tmp_path,'run-2')
    assert {p.name:p.read_bytes() for p in tmp_path.iterdir()} == before
    assert save(report,tmp_path,'run-2')


@pytest.mark.parametrize('key,value', [
    ('status','RUNNING'), ('status','ERROR'), ('policy','unknown'), ('seed',True),
    ('avg_queue',float('nan')), ('avg_wait_departed_s',float('inf')),
    ('clearance_hold_s',-1), ('initial_total',99), ('departed_vehicles',99),
    ('exited_world_total',99), ('simulation_seconds',1.0), ('config_id',''),
    ('cycles_completed',0), ('avg_stopped_delay_s',None),
])
def test_invalid_summary_cannot_create_files(report,tmp_path,key,value):
    summary,cycles=report
    with pytest.raises((TypeError,ValueError)):
        save((dict(summary,**{key:value}),cycles),tmp_path)
    assert not list(tmp_path.iterdir())


@pytest.mark.parametrize('run_id,stamp', [('',STAMP), ('run','2026-10-19T12:00:00'), ('run','bad-date')])
def test_metadata_must_be_stable_and_timezone_aware(report,tmp_path,run_id,stamp):
    with pytest.raises(ValueError):
        hs.HistoryStorage.append_run(*report,tmp_path/'h.csv',tmp_path/'c.csv',
                                    run_id=run_id,started_at_iso=stamp)
    assert not list(tmp_path.iterdir())


def test_invalid_cycle_payload_cannot_create_files(report,tmp_path):
    summary,cycles=report
    invalid=replace(cycles[0],avg_queue_cycle=float('nan'))
    with pytest.raises(ValueError):
        save((summary,(invalid,)),tmp_path)
    assert not list(tmp_path.iterdir())


def test_both_headers_checked_before_any_write(report,tmp_path):
    bad=tmp_path/'cycles.csv'
    bad.write_text('run_id,wrong\nold,value\n')
    with pytest.raises(ValueError,match='Header CSV'):
        save(report,tmp_path)
    assert bad.read_text() == 'run_id,wrong\nold,value\n'
    assert not (tmp_path/'history.csv').exists()


def test_malformed_existing_rows_are_preserved(report,tmp_path):
    path=tmp_path/'history.csv'
    data=','.join(hs.HISTORY_HEADER)+'\nonly-one-cell\n'
    path.write_text(data)
    with pytest.raises(ValueError,match='thiếu/thừa'):
        save(report,tmp_path)
    assert path.read_text() == data
    assert not (tmp_path/'cycles.csv').exists()


def test_conflicting_retry_does_not_silently_accept_changed_report(report,tmp_path):
    save(report,tmp_path)
    before={p.name:p.read_bytes() for p in tmp_path.iterdir()}
    summary,cycles=report
    with pytest.raises(ValueError,match='nội dung khác'):
        save((dict(summary,config_id='different-config'),cycles),tmp_path)
    assert {p.name:p.read_bytes() for p in tmp_path.iterdir()} == before


def test_concurrent_runs_and_retries_keep_both_files_consistent(report,tmp_path):
    run_ids=[f'run-{i}' for _ in range(3) for i in range(8)]
    with ThreadPoolExecutor(max_workers=8) as pool:
        results=list(pool.map(lambda run_id:save(report,tmp_path,run_id),run_ids))
    history=read(tmp_path/'history.csv')
    cycles=read(tmp_path/'cycles.csv')
    assert sum(results) == 8
    assert len(history) == len(cycles) == 8
    assert {r['run_id'] for r in history} == {r['run_id'] for r in cycles} == set(run_ids)
def test_export_csv_after_class_reload(report):
    from dataclasses import asdict, fields, make_dataclass
    from src.core.statistics import CycleMetrics

    summary, cycles = report

    # Mo phong class CycleMetrics cua phien Python cu
    OldCycleMetrics = make_dataclass(
        "CycleMetrics",
        [(f.name, object) for f in fields(CycleMetrics)],
        module=CycleMetrics.__module__,
    )

    old_cycles = tuple(
        OldCycleMetrics(**asdict(metric))
        for metric in cycles
    )

    # Class cu khong cung danh tinh voi class hien tai
    assert not isinstance(old_cycles[0], CycleMetrics)

    # Nhung van phai xuat duoc CSV neu schema hop le
    result = hs.summary_csv_text(
        summary,
        old_cycles,
        run_id="test-reload",
        started_at_iso=STAMP
    )

    assert result.startswith("run_id,started_at_iso")


def test_real_module_reload_preserves_csv_and_idempotent_storage(tmp_path):
    """Reload in another interpreter so class identities cannot leak to other tests."""
    import subprocess
    import textwrap

    script = textwrap.dedent('''
        import csv
        import importlib
        import sys
        from dataclasses import asdict
        from pathlib import Path
        from src.core import statistics, history_storage as hs
        from src.core.simulation import SimulationEngine
        from src.models.config import Config

        engine = SimulationEngine(Config(
            cycles_to_run=2, rates_per_min=dict.fromkeys('NSEW', 0),
            initial_queue=dict(N=2, S=0, E=0, W=0)))
        engine.start()
        engine.run_ticks(69)
        engine.stop()
        summary, old_cycles = engine.summary(), engine.cycle_metrics()
        assert len(old_cycles) == 2 and old_cycles[-1].provisional
        metadata = dict(run_id='reload', started_at_iso='2026-10-19T12:00:00+07:00')
        before = hs.summary_csv_text(summary, old_cycles, **metadata)
        importlib.reload(statistics)
        importlib.reload(hs)
        assert not isinstance(old_cycles[0], hs.CycleMetrics)
        mixed_cycles = (old_cycles[0], hs.CycleMetrics(**asdict(old_cycles[1])))
        assert hs.summary_csv_text(summary, old_cycles, **metadata) == before
        assert hs.summary_csv_text(summary, mixed_cycles, **metadata) == before
        root = Path(sys.argv[1])
        history, cycles = root/'history.csv', root/'cycles.csv'
        assert hs.HistoryStorage.append_run(summary, old_cycles, history, cycles, **metadata)
        assert not hs.HistoryStorage.append_run(summary, mixed_cycles, history, cycles, **metadata)
        for path in (history, cycles):
            with path.open(encoding='utf-8', newline='') as stream:
                assert len(list(csv.DictReader(stream))) == 1
        assert engine.summary() == summary
        print('reload regression passed')
    ''')
    result = subprocess.run(
        [sys.executable, '-B', '-c', script, str(tmp_path)],
        cwd=Path(__file__).resolve().parents[1], capture_output=True, text=True, timeout=30,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    assert 'reload regression passed' in result.stdout


@pytest.mark.parametrize('invalid_kind', ['dict', 'wrong_module', 'wrong_name', 'changed_schema', 'nan'])
def test_reload_compatibility_does_not_accept_invalid_cycles(report, tmp_path, invalid_kind):
    from dataclasses import asdict, fields, make_dataclass
    from src.core.statistics import CycleMetrics

    summary, cycles = report
    save(report, tmp_path)
    before = {p.name: p.read_bytes() for p in tmp_path.iterdir()}
    values = asdict(cycles[0])
    schema = [(field.name, object) for field in fields(CycleMetrics)]
    if invalid_kind == 'dict':
        invalid = values
    else:
        if invalid_kind == 'changed_schema':
            schema = [(name, kind) for name, kind in schema if name != 'provisional']
            values.pop('provisional')
        if invalid_kind == 'nan':
            values['avg_queue_cycle'] = float('nan')
        old_type = make_dataclass(
            'OtherMetrics' if invalid_kind == 'wrong_name' else 'CycleMetrics', schema,
            module='unrelated.statistics' if invalid_kind == 'wrong_module' else CycleMetrics.__module__,
        )
        invalid = old_type(**values)
    invalid_cycles = (invalid, *cycles[1:])
    with pytest.raises((TypeError, ValueError)):
        hs.summary_csv_text(summary, invalid_cycles, run_id='bad', started_at_iso=STAMP)
    with pytest.raises((TypeError, ValueError)):
        save((summary, invalid_cycles), tmp_path, run_id='bad')
    assert {p.name: p.read_bytes() for p in tmp_path.iterdir()} == before
