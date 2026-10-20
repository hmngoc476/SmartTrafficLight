"""Multi-field validation and delete dialog; real Core and isolated JSON storage."""
from copy import deepcopy
import json

import pytest

from src.models.config import Config
from src.ui import form
from test_ui_runtime import app, create_config  # Reuse the existing isolated AppTest fixture.


def test_independent_errors_survive_fix_without_mutating_payload():
    payload = Config().to_dict()
    payload['rates_per_min']['N'] = 35
    payload['yellow_s'] = 0
    payload['cycles_to_run'] = 0
    payload['motion_2d']['dt_s'] = .3
    before = deepcopy(payload)
    errors = form.collect_errors(payload)
    assert set(errors.fields) == {'f_rate_N', 'f_yellow_s', 'f_cycles_to_run', 'f_m_dt_s'}
    assert not errors.related and not errors.general
    assert payload == before
    payload['yellow_s'] = 3
    fixed = form.collect_errors(payload)
    assert fixed.fields == {k: v for k, v in errors.fields.items() if k != 'f_yellow_s'}


@pytest.mark.parametrize('green,minimum,valid', [(10, 10, False), (4, 2, True), (200, 100, True)])
def test_green_relation_uses_actual_pair_and_renders_once(green, minimum, valid):
    payload = Config().to_dict()
    payload.update(green_budget_s=green, min_green_s=minimum, yellow_s=0)
    errors = form.collect_errors(payload)
    assert bool(errors.related) is not valid
    assert not errors.for_field('min_green_s')
    assert bool(errors.for_field('green_budget_s')) is not valid
    assert 'f_yellow_s' in errors.fields


def test_invalid_green_types_and_minimum_are_independent():
    payload = Config().to_dict()
    payload.update(green_budget_s=1.5, min_green_s=0)
    errors = form.collect_errors(payload)
    assert set(errors.fields) == {'f_green_budget_s', 'f_min_green_s'}
    assert not errors.related


@pytest.mark.parametrize('name,value', [
    ('enabled', 1), ('dt_s', 0), ('dt_s', .3), ('dt_s', float('inf')),
    ('vehicle_length_m', 0), ('min_gap_m', -1), ('max_speed_mps', 0),
    ('accel_mps2', 0), ('approach_visible_m', 0), ('intersection_width_m', 3.5),
    ('stop_margin_m', -1), ('clearance_limit_s', 0),
])
def test_motion_errors_use_widget_keys_even_when_disabled(name, value):
    payload = Config().to_dict()
    payload['motion_2d'].update(enabled=False)
    payload['motion_2d'][name] = value
    errors = form.collect_errors(payload)
    assert set(errors.fields) == {f'f_m_{name}'}
    assert not errors.valid
    with pytest.raises((ValueError, TypeError)):
        Config.from_dict(payload)


def test_valid_boundaries_and_schema_fallback():
    payload = Config().to_dict()
    payload.update(green_budget_s=2, min_green_s=1, startup_delay_s=0, seed=-10)
    payload['motion_2d'].update(dt_s=1, min_gap_m=0, stop_margin_m=0)
    assert form.collect_errors(payload).valid
    payload['unexpected'] = True
    assert form.collect_errors(payload).general


def inline_messages(at):
    return [m.value for m in at.markdown if '<div class="field-err">' in m.value]


@pytest.mark.parametrize('editing', [False, True])
def test_ui_all_errors_persist_and_invalid_form_never_writes(app, editing):
    at = app
    if editing:
        create_config(at)
    else:
        at.button(key='btn_new').click().run()
        at.text_input(key='f_name').set_value('Multi-field')
    manager = at.session_state['manager']
    path = manager.filepath
    before = path.read_bytes() if path.exists() else None
    for key, value in [('f_rate_N', 35.), ('f_yellow_s', 0), ('f_cycles_to_run', 0), ('f_m_dt_s', .3)]:
        at.number_input(key=key).set_value(value)
    at.run()
    assert len(inline_messages(at)) == 4
    assert at.button(key='btn_save').disabled and at.button(key='btn_update').disabled
    assert not any('Vị trí lỗi validation' in m.value for m in at.markdown)
    assert not at.error
    at.number_input(key='f_yellow_s').set_value(3).run()
    assert len(inline_messages(at)) == 3
    assert not any('Yellow' in message for message in inline_messages(at))
    assert (path.read_bytes() if path.exists() else None) == before
    # Even a stale/direct callback must still be rejected by the real Manager.
    invalid = Config().to_dict()
    invalid.update(id=at.session_state['f_id'], name='Invalid', yellow_s=0)
    ok, _ = manager.update(invalid['id'], invalid) if editing else manager.create(invalid)
    assert not ok
    assert (path.read_bytes() if path.exists() else None) == before
    at.number_input(key='f_rate_N').set_value(10.)
    at.number_input(key='f_cycles_to_run').set_value(10)
    at.number_input(key='f_m_dt_s').set_value(.2).run()
    assert not inline_messages(at)
    action = 'btn_update' if editing else 'btn_save'
    assert not at.button(key=action).disabled
    at.button(key=action).click().run()
    assert not at.exception


def test_ui_green_and_multiple_motion_errors(app):
    at = app
    create_config(at)
    for key, value in [('f_green_budget_s', 10), ('f_min_green_s', 10),
                       ('f_m_vehicle_length_m', 0.), ('f_m_min_gap_m', -1.),
                       ('f_m_intersection_width_m', 3.5)]:
        at.number_input(key=key).set_value(value)
    at.run()
    assert len(inline_messages(at)) == 4
    assert sum('Green Budget' in m for m in inline_messages(at)) == 1
    at.number_input(key='f_min_green_s').set_value(0).run()
    assert any('Min Green phải' in m for m in inline_messages(at))
    assert not any('Green Budget' in m for m in inline_messages(at))
    assert at.button(key='btn_update').disabled
    assert not at.exception


def test_dialog_cancel_confirm_target_and_single_write(app, monkeypatch):
    at = app
    create_config(at)
    first_id = at.session_state['selected_config_id']
    create_config(at)
    second_id = at.session_state['selected_config_id']
    manager = at.session_state['manager']
    before = manager.filepath.read_bytes()
    assert not at.get('dialog')
    at.button(key='btn_delete').click().run()
    assert at.get('dialog')
    assert at.get('dialog')[0].proto.dialog.position == 0  # Streamlit CENTER enum.
    assert any(f'cấu hình {second_id} không?' in m.value for m in at.markdown)
    at.button(key='btn_cancel').click().run()
    assert '_delete_config_id' not in at.session_state
    assert manager.filepath.read_bytes() == before
    assert not at.get('dialog')
    at.run()
    assert not at.get('dialog')
    calls = []
    original = manager.delete

    def delete(config_id):
        calls.append(config_id)
        return original(config_id)

    monkeypatch.setattr(manager, 'delete', delete)
    at.button(key='btn_use').click().run()
    at.button(key='btn_delete').click().run()
    at.button(key='btn_confirm').click().run()
    at.run()
    assert calls == [second_id]
    assert [c['id'] for c in manager.list()] == [first_id]
    assert [c['id'] for c in json.loads(manager.filepath.read_text())['configs']] == [first_id]
    assert at.session_state['selected_config_id'] is None
    assert at.session_state['use_config_id'] is None
    assert not at.get('dialog') and not at.exception


@pytest.mark.parametrize('status', ['RUNNING', 'PAUSED'])
def test_delete_rechecks_lock_at_confirmation(app, status):
    at = app
    create_config(at)
    at.button(key='sim_start').click().run()
    assert at.button(key='btn_delete').disabled
    at.button(key='sim_pause').click().run()
    assert at.button(key='btn_delete').disabled
    at.button(key='sim_reset').click().run()
    at.button(key='sim_reset_confirm').click().run()
    at.button(key='btn_delete').click().run()
    manager = at.session_state['manager']
    before = manager.filepath.read_bytes()
    # Start the real engine between rendering the enabled button and its callback.
    engine = at.session_state['engine']
    engine.start()
    if status == 'PAUSED':
        engine.pause()
    at.button(key='btn_confirm').click().run()
    assert manager.filepath.read_bytes() == before
    assert '_delete_config_id' not in at.session_state
    assert at.session_state['notice'][0] == 'error'
    assert at.button(key='btn_delete').disabled
    assert not at.exception


def test_dialog_dismiss_and_selection_change_cannot_delete(app):
    at = app
    create_config(at)
    first_id = at.session_state['selected_config_id']
    create_config(at)
    manager = at.session_state['manager']
    before = manager.filepath.read_bytes()
    at.button(key='btn_delete').click().run()
    # AppTest has no public dismiss API; send the real X/Esc trigger protobuf.
    widget_states = at._tree.get_widget_states()
    widget_states.widgets.add(id=at.get('dialog')[0].proto.dialog.id, trigger_value=True)
    at._run(widget_states)
    assert not at.get('dialog')
    assert '_delete_config_id' not in at.session_state
    at.button(key='btn_delete').click().run()
    at.selectbox(key='sel_box').select(first_id).run()
    assert not at.get('dialog')
    assert manager.filepath.read_bytes() == before
    assert at.session_state['selected_config_id'] == first_id
    assert not at.exception


def test_delete_failure_closes_dialog_and_preserves_selection(app, monkeypatch):
    at = app
    create_config(at)
    config_id = at.session_state['selected_config_id']
    manager = at.session_state['manager']
    before = manager.filepath.read_bytes()
    monkeypatch.setattr(manager, 'delete', lambda _: (False, 'Lỗi ghi JSON thử nghiệm'))
    at.button(key='btn_delete').click().run()
    at.button(key='btn_confirm').click().run()
    assert not at.get('dialog') and not at.exception
    assert at.session_state['selected_config_id'] == config_id
    assert manager.filepath.read_bytes() == before
    assert any('Lỗi ghi JSON' in error.value for error in at.error)


def test_system_validation_error_uses_st_error(app, monkeypatch):
    at = app
    create_config(at)

    def fail(*args, **kwargs):
        raise OSError('Không thể truy cập dữ liệu')

    monkeypatch.setattr(at.session_state['manager'], 'validate', fail)
    at.run()
    assert len(at.error) == 1 and not inline_messages(at)
    assert at.button(key='btn_update').disabled
    assert not at.exception
