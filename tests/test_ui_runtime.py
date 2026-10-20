"""Real Streamlit tabs, real Core and temporary JSON/CSV storage."""
from pathlib import Path
from functools import partial
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import json
import pytest
from streamlit.testing.v1 import AppTest
from src.core import history_storage
from src.core.manager import ConfigManager
from src.ui import state

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture
def app(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(state, 'ConfigManager', partial(ConfigManager, tmp_path/'data/junctions.json'))
    monkeypatch.setattr(history_storage, 'HISTORY_PATH', tmp_path/'data/sim_history.csv')
    monkeypatch.setattr(history_storage, 'CYCLES_PATH', tmp_path/'data/cycle_metrics.csv')
    at = AppTest.from_file(str(ROOT/'src/app.py'), default_timeout=30).run()
    assert not at.exception
    return at


def create_config(at, *, cycles=2, queue=None, **motion):
    at.button(key='btn_new').click().run()
    at.text_input(key='f_name').set_value('UI integration')
    for d in 'NSEW':
        at.number_input(key=f'f_rate_{d}').set_value(0.)
        at.number_input(key=f'f_queue_{d}').set_value((queue or dict(N=3)).get(d, 0))
    at.number_input(key='f_cycles_to_run').set_value(cycles)
    for key,value in motion.items():
        at.number_input(key=f'f_m_{key}').set_value(float(value))
    at.run()
    at.button(key='btn_save').click().run()
    assert not at.exception


def test_startup_and_crud_validate_against_new_models(app):
    at = app
    assert [t.label for t in at.tabs] == ['Quản lý cấu hình', 'Mô phỏng và phân tích']
    assert len(at.number_input) == 25
    assert at.button(key='sim_start').disabled
    create_config(at, intersection_width_m=4)
    at.text_input(key='f_name').set_value('Updated').run()
    at.button(key='btn_update').click().run()
    assert at.session_state['manager'].list()[0]['name'] == 'Updated'
    at.number_input(key='f_m_intersection_width_m').set_value(3.5).run()
    assert at.button(key='btn_update').disabled
    assert any('3,6m' in m.value for m in at.markdown)
    assert at.session_state['manager'].list()[0]['motion_2d']['intersection_width_m'] == 4
    at.button(key='btn_reset').click().run()
    at.button(key='btn_confirm').click().run()
    at.button(key='btn_delete').click().run()
    at.button(key='btn_cancel').click().run()
    assert len(at.session_state['manager'].list()) == 1
    at.button(key='btn_delete').click().run()
    at.button(key='btn_confirm').click().run()
    assert at.session_state['manager'].list() == []
    assert json.loads(Path('data/junctions.json').read_text())['configs'] == []
    assert not at.exception


def test_widget_reruns_do_not_tick_and_reset_replays_original_config(app):
    at = app
    create_config(at)
    at.button(key='sim_start').click().run()
    engine = at.session_state['engine']
    assert engine.session_state == 'RUNNING' and engine.sim_time == 0
    assert at.button(key='btn_delete').disabled
    run_id = at.session_state['run_id']
    at.number_input(key='f_headway_s').set_value(7).run()
    at.button(key='btn_update').click().run()
    at.run()
    assert engine.sim_time == 0
    assert engine.controller.config.headway_s == 2
    assert at.session_state['manager'].list()[0]['headway_s'] == 7
    at.button(key='sim_pause').click().run()
    for _ in range(3):
        at.button(key='sim_step').click().run()
    assert engine.sim_time == 3 and engine.session_state == 'PAUSED'
    before = engine.snapshot().to_dict()
    at.button(key='sim_reset').click().run()
    at.button(key='sim_reset_confirm').click().run()
    assert not engine.has_started and engine.sim_time == 0
    assert not at.button(key='sim_start').disabled
    assert at.button(key='sim_resume').disabled
    assert at.button(key='sim_step').disabled
    assert at.button(key='sim_cycle').disabled
    assert at.session_state['run_id'] != run_id
    at.button(key='sim_start').click().run()
    at.button(key='sim_pause').click().run()
    for _ in range(3):
        at.button(key='sim_step').click().run()
    assert engine.snapshot().to_dict() == before
    assert engine.controller.config.headway_s == 2
    assert not at.exception


def test_updating_cycles_from_10_to_3_creates_a_new_run_only_after_confirmation(app):
    """Regression: Tab 1 saved=3, paused run=10 -> explicit new run=3."""
    at = app
    create_config(at, cycles=10, queue={})
    cfg_id = at.session_state['selected_config_id']
    at.button(key='sim_start').click().run()
    at.button(key='sim_pause').click().run()
    old_engine = at.session_state['engine']
    old_run_id = at.session_state['run_id']
    assert old_engine.session_state == 'PAUSED'
    assert at.session_state['run_config_snapshot']['cycles_to_run'] == 10

    at.number_input(key='f_cycles_to_run').set_value(3).run()
    at.button(key='btn_update').click().run()
    assert at.session_state['manager'].get(cfg_id)['cycles_to_run'] == 3
    # Save không được âm thầm làm thay đổi kết quả/snapshot của phiên cũ.
    assert old_engine.cycle_index == 1
    assert at.session_state['run_config_snapshot']['cycles_to_run'] == 10
    assert any('vẫn dùng 10 chu kỳ' in w.value for w in at.warning)

    at.button(key='sim_apply_new_config').click().run()
    at.button(key='sim_apply_new_config_confirm').click().run()
    assert not at.exception
    new_engine = at.session_state['engine']
    assert new_engine is not old_engine
    assert old_engine.session_state == 'STOPPED'
    assert new_engine.session_state == 'RUNNING'
    assert at.session_state['run_id'] != old_run_id
    assert at.session_state['run_config_snapshot']['cycles_to_run'] == 3
    assert new_engine.controller.config.cycles_to_run == 3
    assert new_engine.snapshot().cycle_index == 1
    assert not at.warning

    at.button(key='sim_pause').click().run()
    for _ in range(3):
        at.button(key='sim_cycle').click().run()
    assert new_engine.session_state == 'COMPLETED'
    assert new_engine.cycle_index == 3
    assert at.session_state['summary_saved']
    assert not at.exception


def test_reset_keeps_old_config_until_user_explicitly_applies_new_one(app):
    at = app
    create_config(at, cycles=10, queue={})
    at.button(key='sim_start').click().run()
    at.button(key='sim_pause').click().run()
    at.number_input(key='f_cycles_to_run').set_value(3).run()
    at.button(key='btn_update').click().run()
    at.button(key='sim_reset').click().run()
    at.button(key='sim_reset_confirm').click().run()
    at.button(key='sim_start').click().run()
    assert at.session_state['run_config_snapshot']['cycles_to_run'] == 10
    at.button(key='sim_pause').click().run()
    at.button(key='sim_apply_new_config').click().run()
    at.button(key='sim_apply_new_config_confirm').click().run()
    assert at.session_state['run_config_snapshot']['cycles_to_run'] == 3
    assert at.session_state['engine'].controller.config.cycles_to_run == 3
    assert not at.exception


def test_cycle_completion_and_stop_keep_real_summary_and_save_once(app):
    at = app
    create_config(at, cycles=1)
    at.button(key='sim_start').click().run()
    at.button(key='sim_pause').click().run()
    at.button(key='sim_cycle').click().run()
    engine = at.session_state['engine']
    assert engine.session_state == 'COMPLETED' and engine.sim_time == 68
    assert engine.stats.crossed_stop_total == 3
    assert at.session_state['summary_saved']
    history = history_storage.HISTORY_PATH.read_text()
    at.run()
    assert history_storage.HISTORY_PATH.read_text() == history
    assert not at.exception
    at.button(key='sim_start').click().run()
    at.button(key='sim_stop').click().run()
    assert at.session_state['engine'].session_state == 'STOPPED'
    assert at.session_state['summary_saved']
    assert not at.exception


def test_ui_runs_through_clearance_hold(app):
    at = app
    create_config(at, queue=dict(E=4), max_speed_mps=.5, clearance_limit_s=100)
    at.button(key='sim_start').click().run()
    at.button(key='sim_pause').click().run()
    at.button(key='sim_cycle').click().run()
    engine = at.session_state['engine']
    assert engine.session_state == 'PAUSED'
    assert engine.stats.cycles[0].actual_cycle_s > 68
    assert engine.stats.cycles[0].clearance_hold_s > 0
    assert not history_storage.HISTORY_PATH.exists()
    assert not at.exception


def test_ui_error_stays_all_red_and_does_not_export_as_completed(app):
    at = app
    create_config(at, queue=dict(N=1,E=1), max_speed_mps=.1,
                  stop_margin_m=.05, clearance_limit_s=2)
    at.number_input(key='f_startup_delay_s').set_value(0).run()
    at.button(key='btn_update').click().run()
    at.button(key='sim_start').click().run()
    at.button(key='sim_pause').click().run()
    at.button(key='sim_cycle').click().run()
    engine = at.session_state['engine']
    assert engine.session_state == 'ERROR'
    assert set(engine.snapshot().signals.signal_colors.values()) == {'RED'}
    assert not history_storage.HISTORY_PATH.exists()
    assert at.get('download_button')[0].proto.disabled
    assert at.button(key='sim_compare_fixed').disabled
    assert not at.exception


def test_compare_finished_browser_run_uses_frozen_config_and_keeps_history(app, monkeypatch):
    from src.ui import comparison_panel
    import csv
    import io

    at = app
    assert at.button(key='sim_compare_fixed').disabled
    create_config(at, cycles=1)
    at.button(key='sim_start').click().run()
    assert at.button(key='sim_compare_fixed').disabled
    at.button(key='sim_pause').click().run()
    assert at.button(key='sim_compare_fixed').disabled
    at.button(key='sim_cycle').click().run()
    engine = at.session_state['engine']
    original_summary = engine.summary()
    frozen = at.session_state['run_config_snapshot'].copy()
    at.number_input(key='f_headway_s').set_value(7).run()
    at.text_input(key='f_name').set_value('Saved later').run()
    at.button(key='btn_update').click().run()
    files_before = {p: p.read_bytes() for p in Path('data').iterdir()}
    calls = []
    original_compare = comparison_panel.compare_finished_run

    def compare(config, summary):
        calls.append(config.to_dict())
        return original_compare(config, summary)

    monkeypatch.setattr(comparison_panel, 'compare_finished_run', compare)
    at.button(key='sim_compare_fixed').click().run()
    assert not at.exception
    result = at.session_state['comparison_result']
    assert result.comparable
    assert result.adaptive.summary == original_summary
    assert calls == [frozen]
    assert engine.summary() == original_summary
    assert files_before == {p: p.read_bytes() for p in Path('data').iterdir()}
    export = next(b for b in at.get('download_button') if b.proto.label == 'Tải CSV so sánh')
    assert not export.proto.disabled
    assert any('Fixed-Time: NS 30s / EW 30s' in m.value for m in at.markdown)
    from src.core.comparison import comparison_csv_text
    from src.models.config import Config
    rows = list(csv.DictReader(io.StringIO(comparison_csv_text(
        result, Config.from_dict(frozen), run_id=at.session_state['run_id'],
        started_at_iso=at.session_state['started_at_iso']))))
    assert all(row['config_name'] == 'UI integration' for row in rows)
    at.run()
    assert len(calls) == 1
    assert at.button(key='sim_compare_fixed').disabled
    at.button(key='sim_reset').click().run()
    at.button(key='sim_reset_confirm').click().run()
    assert at.session_state['comparison_result'] is None
    assert at.button(key='sim_compare_fixed').disabled
    assert all(b.proto.label != 'Tải CSV so sánh' for b in at.get('download_button'))


def test_compare_requires_completion_and_failed_comparison_can_retry(app, monkeypatch):
    from src.ui import comparison_panel

    at = app
    create_config(at, cycles=1)
    at.button(key='sim_start').click().run()
    at.button(key='sim_stop').click().run()
    assert at.button(key='sim_compare_fixed').disabled
    at.button(key='sim_start').click().run()
    at.button(key='sim_pause').click().run()
    at.button(key='sim_step').click().run()
    at.button(key='sim_stop').click().run()
    assert at.button(key='sim_compare_fixed').disabled
    assert at.session_state['comparison_result'] is None
    at.button(key='sim_start').click().run()
    at.button(key='sim_pause').click().run()
    at.button(key='sim_cycle').click().run()
    assert at.session_state['engine'].session_state == 'COMPLETED'
    assert not at.button(key='sim_compare_fixed').disabled
    # Completing and rerendering the page must not start a comparison automatically.
    at.run()
    assert at.session_state['comparison_result'] is None
    assert all(b.proto.label != 'Tải CSV so sánh' for b in at.get('download_button'))
    with monkeypatch.context() as patch:
        def fail_compare(*args):
            raise RuntimeError('Comparison unavailable')
        patch.setattr(comparison_panel, 'compare_finished_run', fail_compare)
        at.button(key='sim_compare_fixed').click().run()
        assert not at.exception
        assert at.session_state['comparison_result'] is None
        assert any('Comparison unavailable' in error.value for error in at.error)
    at.button(key='sim_compare_fixed').click().run()
    assert not at.exception
    assert at.session_state['comparison_result'].horizon_s == 68
    assert at.session_state['comparison_error'] is None


def test_stopping_after_one_of_two_cycles_cannot_compare_or_keep_old_report(app, monkeypatch):
    from src.ui import comparison_panel

    at = app
    create_config(at, cycles=2)
    at.button(key='sim_start').click().run()
    at.button(key='sim_pause').click().run()
    at.button(key='sim_cycle').click().run()
    assert at.session_state['engine'].summary()['cycles_completed'] == 1
    assert at.button(key='sim_compare_fixed').disabled
    at.button(key='sim_stop').click().run()
    assert at.button(key='sim_compare_fixed').disabled

    def must_not_compare(*args):
        pytest.fail('An incomplete run must not trigger comparison')

    monkeypatch.setattr(comparison_panel, 'compare_finished_run', must_not_compare)
    # An early-Stop report cached by the previous app version must also disappear.
    at.session_state['comparison_result'] = 'old early-stop report'
    at.run()
    assert not at.exception
    assert at.session_state['comparison_result'] is None
    assert all(b.proto.label != 'Tải CSV so sánh' for b in at.get('download_button'))


def test_timer_uses_unique_events_and_discards_stale_epochs(app):
    # Run the original app plus event dispatch in a Streamlit context. No fake Engine.
    code = f'''
import runpy
import streamlit as st
runpy.run_path({str(ROOT/'src/app.py')!r}, run_name='__main__')
from src.ui.simulation_tab import apply_timer_event
if 'test_event' in st.session_state:
    apply_timer_event(st.session_state.test_event)
'''
    timer_app = AppTest.from_string(code, default_timeout=30).run()
    create_config(timer_app)
    timer_app.button(key='sim_start').click().run()
    epoch = timer_app.session_state['timer_epoch']
    timer_app.session_state['test_event'] = dict(epoch=epoch, sequence=1)
    timer_app.run()
    engine = timer_app.session_state['engine']
    assert engine.sim_time == 1
    timer_app.run()
    assert engine.sim_time == 1
    for event in (None, dict(epoch=epoch,sequence=True), dict(epoch='stale',sequence=2),
                  dict(epoch=epoch,sequence=0)):
        timer_app.session_state['test_event'] = event
        timer_app.run()
        assert engine.sim_time == 1
    timer_app.button(key='sim_pause').click().run()
    timer_app.session_state['test_event'] = dict(epoch=epoch, sequence=3)
    timer_app.run()
    assert engine.sim_time == 1
    timer_app.button(key='sim_resume').click().run()
    new_epoch = timer_app.session_state['timer_epoch']
    assert new_epoch != epoch
    timer_app.session_state['test_event'] = dict(epoch=new_epoch, sequence=1)
    timer_app.run()
    assert engine.sim_time == 2
    assert not timer_app.exception


def test_history_failure_retains_outbox_across_new_run_and_retry(app, monkeypatch):
    at = app
    create_config(at,cycles=1)
    at.button(key='sim_start').click().run()
    at.button(key='sim_pause').click().run()
    run_id = at.session_state['run_id']
    original = history_storage._write_atomic
    attempts = []
    def fail_history(path,header,rows):
        if path == history_storage.HISTORY_PATH:
            attempts.append(path)
            raise OSError('Injected history write failure')
        return original(path,header,rows)
    with monkeypatch.context() as patch:
        patch.setattr(history_storage,'_write_atomic',fail_history)
        at.button(key='sim_cycle').click().run()
        assert not at.session_state['summary_saved']
        assert run_id in at.session_state['history_outbox']
        assert history_storage.CYCLES_PATH.exists()
        assert not history_storage.HISTORY_PATH.exists()
        at.run()
        assert len(attempts) == 1
        at.button(key='sim_start').click().run()
        assert at.session_state['run_id'] != run_id
        assert run_id in at.session_state['history_outbox']
    at.button(key='sim_history_retry').click().run()
    assert not at.session_state['history_outbox']
    assert run_id in at.session_state['history_saved_ids']
    assert not at.session_state['summary_saved']  # The new RUNNING session is not saved.
    at.button(key='sim_stop').click().run()
    assert at.session_state['summary_saved']
    import csv
    with history_storage.HISTORY_PATH.open() as f:
        assert len(list(csv.DictReader(f))) == 2
    with history_storage.CYCLES_PATH.open() as f:
        assert len(list(csv.DictReader(f))) == 1
    assert not at.exception


def test_dashboard_and_outbox_export_cycles_retained_before_reload(app):
    from dataclasses import asdict, fields, make_dataclass
    from src.core.statistics import CycleMetrics

    at = app
    create_config(at, cycles=2)
    at.button(key='sim_start').click().run()
    at.button(key='sim_pause').click().run()
    at.button(key='sim_cycle').click().run()
    engine = at.session_state['engine']
    old_type = make_dataclass(
        'CycleMetrics', [(field.name, object) for field in fields(CycleMetrics)],
        module=CycleMetrics.__module__,
        namespace={name: value for name, value in vars(CycleMetrics).items()
                   if isinstance(value, property)},
    )
    engine.stats._cycles[:] = [old_type(**asdict(metric)) for metric in engine.stats.cycles]
    assert not isinstance(engine.stats.cycles[0], CycleMetrics)
    at.button(key='sim_stop').click().run()
    assert not at.exception
    assert not at.error
    assert at.session_state['summary_saved']
    assert not at.session_state['history_outbox']
    assert not at.get('download_button')[0].disabled
    before = [path.read_bytes() for path in (history_storage.HISTORY_PATH, history_storage.CYCLES_PATH)]
    at.run()
    assert not at.exception
    assert not at.error
    assert [path.read_bytes() for path in (history_storage.HISTORY_PATH, history_storage.CYCLES_PATH)] == before


@pytest.mark.parametrize('error_type', [TypeError, ValueError])
def test_csv_export_error_is_shown_without_crashing_dashboard(app, monkeypatch, error_type):
    from src.ui import simulation_tab

    at = app
    create_config(at, cycles=1)
    at.button(key='sim_start').click().run()
    at.button(key='sim_pause').click().run()
    at.button(key='sim_cycle').click().run()
    assert not at.exception
    before = [path.read_bytes() for path in (history_storage.HISTORY_PATH, history_storage.CYCLES_PATH)]

    def fail_export(*args, **kwargs):
        raise error_type('Injected CSV export error')

    with monkeypatch.context() as patch:
        patch.setattr(simulation_tab, 'summary_csv_text', fail_export)
        at.run()
        assert not at.exception
        assert any('Không thể tạo CSV:' in error.value for error in at.error)
        assert at.get('download_button')[0].disabled
    at.run()
    assert not at.exception
    assert not at.error
    assert not at.get('download_button')[0].disabled
    assert [path.read_bytes() for path in (history_storage.HISTORY_PATH, history_storage.CYCLES_PATH)] == before
