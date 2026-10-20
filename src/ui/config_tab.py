"""Tab 1 · Quản lý cấu hình.

UI chỉ giữ bản nháp trong session_state và gọi ConfigManager; validation do
Config.from_dict (qua ConfigManager.validate) quyết định, UI không ghi file.
"""
from __future__ import annotations

from html import escape

import streamlit as st

from src.ui import form, state
from src.ui.form import DIRS, key
from src.ui.labels import edit_mode_text

S = st.session_state
RUN_LOCKED_STATES = ("RUNNING", "PAUSED")
SAMPLE = {
    "name": "Giao lộ mẫu - lệch hướng Đông Tây",
    "rates_per_min": {"N": 12, "S": 9, "E": 18, "W": 7},
    "initial_queue": {"N": 7, "S": 4, "E": 16, "W": 5},
    "seed": 2026,
}


# ----------------------------------------------------------------------
# Callbacks (chạy trước khi script rerun, được phép sửa session_state)
# ----------------------------------------------------------------------
def _select(config_id: str | None) -> None:
    on_delete_cancel()
    S.selected_config_id = S.sel_box = config_id
    S.editor_mode, S.pending_action = "EDIT", None
    cfg = state.get_config(config_id)
    form.load_form(cfg if cfg else form.default_payload(""))


def on_select() -> None:
    S.notice = None
    _select(S.sel_box)


def on_new() -> None:
    on_delete_cancel()
    S.editor_mode, S.pending_action, S.notice = "NEW", None, None
    form.load_form(form.default_payload(state.next_id()))


def on_save() -> None:
    payload = form.payload_from_form()
    payload["id"] = state.next_id()
    ok, message = S.manager.create(payload)
    S.notice = ("ok" if ok else "error", message)
    if ok:
        _select(payload["id"])


def on_update() -> None:
    payload = form.payload_from_form()
    ok, message = S.manager.update(S.selected_config_id, payload)
    S.notice = ("ok" if ok else "error", message)
    if ok:
        form.load_form(state.get_config(S.selected_config_id))


def on_use() -> None:
    S.use_config_id = S.selected_config_id
    S.notice = ("ok", f"Đã chọn '{S.use_config_id}' cho lần Start tiếp theo.")


def on_delete_ask() -> None:
    config_id = S.selected_config_id
    if config_id and S.manager is not None and S.editor_mode == "EDIT" and not _delete_locked(config_id):
        S.pending_action = None
        S["_delete_config_id"] = config_id


def on_delete_cancel() -> None:
    S.pop("_delete_config_id", None)


def on_cancel() -> None:
    S.pending_action = None


def on_delete_confirm(config_id: str) -> None:
    # Tiêu thụ yêu cầu trước khi gọi Manager: rerun/callback lặp không xóa lần hai.
    if S.pop("_delete_config_id", None) != config_id:
        return
    if S.selected_config_id != config_id or S.editor_mode != "EDIT":
        S.notice = ("error", "Lựa chọn đã thay đổi; vui lòng chọn lại cấu hình cần xóa.")
        return
    if S.manager is None or _delete_locked(config_id):
        S.notice = ("error", "Không thể xóa cấu hình; kiểm tra dữ liệu hoặc Stop/Reset phiên mô phỏng.")
        return
    ok, message = S.manager.delete(config_id)
    S.notice, S.pending_action = ("ok" if ok else "error", message), None
    if ok:
        if S.use_config_id == config_id:
            S.use_config_id = None
        S.selected_config_id = S.sel_box = None   # không tự chọn âm thầm bản khác
        S.editor_mode = "EDIT"
        form.load_form(form.default_payload(""))


def _delete_locked(config_id: str | None) -> bool:
    engine = S.get("engine")
    snapshot = S.get("run_config_snapshot")
    return bool(engine is not None and engine.has_started
                and engine.session_state in RUN_LOCKED_STATES
                and snapshot and snapshot.get("id") == config_id)


@st.dialog("Xác nhận xóa cấu hình", position="center", on_dismiss=on_delete_cancel)
def _delete_dialog(config_id: str) -> None:
    st.write(f"Bạn có chắc chắn muốn xóa cấu hình {config_id} không?")
    st.write("Thao tác này không thể hoàn tác.")
    cancel, confirm = st.columns(2)
    if cancel.button("Hủy", key="btn_cancel", on_click=on_delete_cancel):
        st.rerun()
    if confirm.button("Xác nhận xóa", key="btn_confirm", on_click=on_delete_confirm,
                      args=(config_id,), type="primary", disabled=_delete_locked(config_id)):
        st.rerun()


def _restore_form() -> None:
    if S.editor_mode == "NEW":
        on_new()
    else:
        cfg = state.get_config(S.selected_config_id)
        if cfg:
            form.load_form(cfg)


def on_reset() -> None:
    on_delete_cancel()
    S.pending_action = "reset" if S.get("_dirty") else None
    if S.pending_action is None:
        _restore_form()


def on_reset_confirm() -> None:
    S.pending_action = None
    _restore_form()


def on_seed_sample() -> None:
    payload = form.default_payload(state.next_id())
    payload.update({k: v for k, v in SAMPLE.items()})
    payload["motion_2d"]["clearance_limit_s"] = 30.0
    ok, message = S.manager.create(payload)
    S.notice = ("ok" if ok else "error", message)
    if ok:
        _select(payload["id"])


def on_reload() -> None:
    on_delete_cancel()
    S.notice = None
    state.reload_data()


# ----------------------------------------------------------------------
# Helpers hiển thị
# ----------------------------------------------------------------------
def _card(title: str):
    container = st.container(border=True)
    container.markdown(f'<div class="card-title">{title}</div>', unsafe_allow_html=True)
    return container


def _hint(text: str) -> None:
    st.markdown(f'<div class="hint">{text}</div>', unsafe_allow_html=True)


def _field_error(flat: str, errors: form.ValidationErrors) -> None:
    for message in errors.for_field(flat):
        st.markdown(f'<div class="field-err">{escape(message)}</div>', unsafe_allow_html=True)


def _validate(payload: dict) -> form.ValidationErrors:
    errors = form.collect_errors(payload)
    if errors.valid and S.manager is not None:
        try:
            is_update = S.editor_mode == "EDIT"
            valid, message = S.manager.validate(payload, is_update=is_update,
                                               config_id=S.selected_config_id if is_update else None)
            if not valid:
                errors.add(message)
        except (OSError, RuntimeError) as error:
            errors.general.append(f"Không thể kiểm tra cấu hình: {error}")
    return errors


def _status(config_id: str) -> str:
    chosen, used = config_id == S.selected_config_id, config_id == S.use_config_id
    return "Đang chọn · đang dùng" if chosen and used else "Đang chọn" if chosen else "Đang dùng" if used else "—"


def _table(configs: list[dict]) -> str:
    head = (
        "<tr><th>Configuration ID</th><th>Tên cấu hình</th>"
        + "".join(f"<th>Lưu lượng {d}<small>xe/phút</small></th>" for d in DIRS)
        + "<th>Ngân sách xanh</th><th>Số chu kỳ</th><th>Trạng thái lựa chọn</th></tr>"
    )
    widths = [10.5, 25, 7.8, 7.8, 7.8, 7.8, 10.5, 7.2, 15.5]
    cols = "".join(f'<col style="width:{w}%">' for w in widths)
    if not configs:
        rows = '<tr><td colspan="9" class="empty-row">Chưa có cấu hình nào trong data/junctions.json.</td></tr>'
    else:
        rows = ""
        for cfg in configs:
            cls = ' class="sel"' if cfg["id"] == S.selected_config_id else ""
            rates = cfg["rates_per_min"]
            rows += (
                f"<tr{cls}><td>{escape(cfg['id'])}</td><td>{escape(cfg['name'])}</td>"
                + "".join(f"<td>{rates[d]:g}</td>" for d in DIRS)
                + f"<td>{cfg['green_budget_s']} giây</td><td>{cfg['cycles_to_run']}</td>"
                f"<td>{_status(cfg['id'])}</td></tr>"
            )
    return f'<table class="cfg-table"><colgroup>{cols}</colgroup>{head}{rows}</table>'


# ----------------------------------------------------------------------
# Render
# ----------------------------------------------------------------------
def render_config_tab() -> None:
    configs = state.configs()
    ids = [c["id"] for c in configs]
    manager_ok = S.manager is not None
    is_new = S.editor_mode == "NEW"
    selected = S.selected_config_id
    no_selection = (not is_new) and selected is None
    locked = no_selection or not manager_ok and not is_new

    payload = form.payload_from_form()
    errors = form.ValidationErrors() if no_selection else _validate(payload)
    valid = not no_selection and errors.valid
    if no_selection:
        dirty = False
    elif is_new:
        dirty = payload != form.default_payload(S[key("id")])
    else:
        saved = state.get_config(selected)
        dirty = saved is None or payload != saved
    S["_dirty"] = dirty

    run_locked = _delete_locked(selected)

    # ---- Danh sách cấu hình ----
    with _card("Danh sách cấu hình · Xem, chọn và quản lý các giao lộ"):
        st.markdown(_table(configs), unsafe_allow_html=True)
        col_sel, col_note, col_seed = st.columns([1.3, 4, 1.7])
        with col_sel:
            st.selectbox("Chọn theo ID", ids, key="sel_box", index=None,
                         placeholder="Chọn cấu hình", on_change=on_select, disabled=not ids)
        if manager_ok and not ids:
            with col_seed:
                st.button("Tạo cấu hình mẫu", key="btn_seed", on_click=on_seed_sample)

    # ---- Banner trạng thái ----
    with st.container(border=True):
        if is_new:
            banner = f"Đang tạo: {escape(S[key('id')])} | Cấu hình mới | Chế độ: tạo mới"
        elif selected:
            cfg_now = state.get_config(selected) or {"name": ""}
            banner = (f"Đang chọn: {escape(selected)} | {escape(cfg_now['name'])} | "
                      f"Chế độ: {edit_mode_text(selected)}")
        else:
            banner = "Chưa chọn cấu hình · chọn theo ID hoặc bấm Tạo mới"
        st.markdown(f'<p class="banner">{banner}</p>', unsafe_allow_html=True)
        if S.load_error:
            st.error(S.load_error)
        for message in errors.general:
            st.error(message)
        if run_locked:
            st.markdown('<ul class="err-list"><li>Cấu hình đang chạy trong phiên mô phỏng; '
                        'Stop hoặc Reset trước khi xóa.</li></ul>', unsafe_allow_html=True)
        if S.notice:
            kind, text = S.notice
            if kind == "error":
                st.error(text)
            else:
                st.markdown(f'<div class="ok-line">{escape(text)}</div>', unsafe_allow_html=True)
        if S.load_error:
            st.button("Tải lại dữ liệu", key="btn_reload", on_click=on_reload)

    # ---- Lưới 3 cột ----
    left, mid, right = st.columns([26, 31.5, 32.5], gap="small")

    def num(flat: str, label: str, **kw) -> None:
        st.number_input(label, key=key(flat), disabled=locked, **kw)
        _field_error(flat, errors)

    with left:
        with _card("Thông tin chung"):
            st.text_input("Tên cấu hình", key=key("name"), disabled=locked)
            _field_error("name", errors)
            st.text_input("Configuration ID · hệ thống quản lý / chỉ đọc", key=key("id"), disabled=True)
            _field_error("id", errors)
        with _card("Lưu lượng bốn hướng"):
            for col, d in zip(st.columns(4), DIRS):
                with col:
                    num(f"rate_{d}", f"{d} · xe/phút", step=1.0, format="%g")
        with _card("Hàng chờ ban đầu"):
            for col, d in zip(st.columns(4), DIRS):
                with col:
                    num(f"queue_{d}", f"Initial {d} · xe", step=1)

    with mid:
        with _card("Thông số tín hiệu"):
            for pair in (("green_budget_s", "Green Total · giây", "min_green_s", "Min Green · giây"),
                         ("yellow_s", "Yellow · giây", "all_red_s", "All Red · giây"),
                         ("startup_delay_s", "Startup Delay · giây", "headway_s", "Headway · giây")):
                a, b = st.columns(2)
                with a:
                    num(pair[0], pair[1], step=1)
                with b:
                    num(pair[2], pair[3], step=1)
            _hint("Ràng buộc: Green Total ≥ 2 × Min Green")
        with _card("Thông số mô phỏng"):
            a, b = st.columns(2)
            with a:
                num("cycles_to_run", "Số chu kỳ · 1–100", step=1)
            with b:
                num("seed", "Mã tái lập mô phỏng", step=1)

    with right:
        with _card("Thông số chuyển động 2D"):
            st.toggle("Bật motion 2D · enabled = true", key=key("m_enabled"), disabled=locked)
            _field_error("m_enabled", errors)
            rows = (
                (("m_dt_s", "Bước thời gian (s)", "%g"), ("m_vehicle_length_m", "Vehicle Length · mét", "%.1f")),
                (("m_min_gap_m", "Khoảng cách xe tối thiểu (m)", "%.1f"), ("m_max_speed_mps", "Tốc độ tối đa (m/s)", "%.1f")),
                (("m_accel_mps2", "Gia tốc (m/s²)", "%.1f"), ("m_approach_visible_m", "Đoạn đường tiếp cận (m)", "%.1f")),
                (("m_intersection_width_m", "Bề rộng giao lộ (m)", "%.1f"), ("m_stop_margin_m", "Khoảng cách dừng (m)", "%.1f")),
            )
            for left_f, right_f in rows:
                a, b = st.columns(2)
                with a:
                    num(left_f[0], left_f[1], step=0.1, format=left_f[2])
                with b:
                    num(right_f[0], right_f[1], step=0.1, format=right_f[2])
            a, b = st.columns(2)
            with a:
                num("m_clearance_limit_s", "Giới hạn chờ an toàn (s)", step=1.0, format="%g")
            with b:
                dt = S[key("m_dt_s")]
                dt_valid = not errors.for_field("m_dt_s") and isinstance(dt, (int, float)) and dt > 0
                steps = f"{round(1 / dt)}" if dt_valid else "—"
                _hint(f"dt = {dt:g} → {steps} substep/tick<br>"
                      if dt_valid else "Thông số mô phỏng học thuật")

    # ---- Thanh nút hành động ----
    can_edit = manager_ok and not no_selection
    bar = st.columns([145, 185, 157, 226, 238, 229], gap="small")
    bar[0].button("Tạo mới", key="btn_new", on_click=on_new, disabled=is_new)
    bar[1].button("Lưu cấu hình", key="btn_save", on_click=on_save,
                  disabled=not (manager_ok and is_new and valid))
    bar[2].button("Cập nhật", key="btn_update", on_click=on_update,
                  disabled=not (can_edit and not is_new and valid and dirty))
    bar[3].button("Xóa · cần xác nhận", key="btn_delete", on_click=on_delete_ask,
                  disabled=not (can_edit and not is_new) or run_locked)
    bar[4].button("Dùng cấu hình này", key="btn_use", on_click=on_use,
                  disabled=not (can_edit and not is_new) or dirty)
    bar[5].button("Làm mới biểu mẫu", key="btn_reset", on_click=on_reset, disabled=no_selection)
    if S.pending_action == "reset":
        with st.container(border=True):
            st.markdown('<p class="banner" style="font-size:16px">Bỏ thay đổi chưa lưu? '
                        "[Hủy] [Bỏ thay đổi]</p>", unsafe_allow_html=True)
            c1, c2 = st.columns(2)
            c1.button("Hủy", key="btn_cancel", on_click=on_cancel)
            c2.button("Bỏ thay đổi", key="btn_confirm", on_click=on_reset_confirm)
    if config_id := S.get("_delete_config_id"):
        _delete_dialog(config_id)
