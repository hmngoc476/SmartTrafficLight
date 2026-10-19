"""Tab 2 · Mô phỏng và phân tích.

UI chỉ gọi lệnh công khai của SimulationEngine (start/pause/resume/stop/reset/
run_ticks/run_until_cycle_end) và đọc snapshot()/dashboard_data(). Không tự sinh
xe, không tính Adaptive, không sửa Queue hoặc CSV.
"""
from __future__ import annotations

from html import escape
from datetime import datetime, timezone
from uuid import uuid4

import streamlit as st

from src.core.history_storage import HistoryStorage, summary_csv_text
from src.core.simulation import SimulationEngine
from src.models.config import Config
from src.models.snapshot import SimulationSnapshot
from src.ui import charts, state
from src.ui.labels import T
from src.ui.renderer_2d import VEHICLE_STYLE, build_map_figure
from src.ui.timer import timer_event

S = st.session_state
FINISHED = ("STOPPED", "COMPLETED", "ERROR")


# ----------------------------------------------------------------------
# Callbacks
# ----------------------------------------------------------------------
def _run(action, *args) -> bool:
    try:
        action(*args)
        S.sim_notice = None
        return True
    except Exception as error:  # noqa: BLE001 - hiển thị lý do cho người dùng
        S.sim_notice = str(error)
        return False


def _selected_saved_config() -> dict | None:
    """Bản cấu hình đã LƯU để tạo phiên mới (không lấy form chưa lưu)."""
    return state.get_config(S.use_config_id or S.selected_config_id)


def _activate_run(engine: SimulationEngine, data: dict, *, new_run: bool) -> None:
    """Chốt cấu hình và bắt đầu. Chỉ tạo run_id mới khi tạo Engine mới."""
    engine.start()
    S.engine, S.run_config_snapshot = engine, data
    if new_run:
        S.run_id = uuid4().hex
    S.summary_saved, S.pending_sim_reset, S.pending_new_config = False, False, False
    S.started_at_iso = datetime.now(timezone.utc).isoformat()
    S.timer_epoch, S.timer_sequence = uuid4().hex, 0


def on_start() -> None:
    def go() -> None:
        if S.engine is not None and not S.engine.has_started:
            # Sau Reset, Start phát lại ĐÚNG bản chốt cũ (contract về seed/replay).
            # Muốn dùng cấu hình vừa sửa phải chọn 'Áp dụng cấu hình mới'.
            engine, data = S.engine, S.run_config_snapshot
            _activate_run(engine, data, new_run=False)
        else:
            data = _selected_saved_config()
            if data is None:
                raise RuntimeError("Chưa có cấu hình hợp lệ để chạy; chọn hoặc tạo ở Tab 1.")
            _activate_run(SimulationEngine(Config.from_dict(data)), data, new_run=True)
    _run(go)


def on_apply_new_config_ask() -> None:
    S.pending_new_config = True


def on_apply_new_config_cancel() -> None:
    S.pending_new_config = False


def on_apply_new_config_confirm() -> None:
    """Tạo phiên mới theo cấu hình đã lưu; không đổi thông số của phiên cũ."""
    def go() -> None:
        data = _selected_saved_config()
        if data is None:
            raise RuntimeError("Cấu hình được chọn không còn tồn tại. Vui lòng chọn lại ở Tab 1.")
        old_engine = S.engine
        if old_engine is not None and old_engine.session_state == 'RUNNING':
            raise RuntimeError("Hãy Pause hoặc Stop trước khi áp dụng cấu hình mới.")
        # Validate và khởi tạo Engine mới TRƯỚC khi chốt phiên cũ.
        new_engine = SimulationEngine(Config.from_dict(data))
        if old_engine is not None and old_engine.has_started:
            if old_engine.session_state == 'PAUSED':
                old_engine.stop()
            # Đưa summary cũ vào lịch sử/outbox trước khi thay S.engine.
            if old_engine.session_state in ('STOPPED', 'COMPLETED'):
                _persist_history()
        _activate_run(new_engine, data, new_run=True)
    _run(go)


def on_pause() -> None:
    if _run(S.engine.pause):
        S.timer_epoch = None


def on_resume() -> None:
    if _run(S.engine.resume):
        S.timer_epoch, S.timer_sequence = uuid4().hex, 0


def on_stop() -> None:
    if _run(S.engine.stop):
        S.timer_epoch = None


def on_step() -> None:
    _run(S.engine.run_ticks, 1)


def on_cycle() -> None:
    _run(S.engine.run_until_cycle_end)


def on_reset_ask() -> None:
    S.pending_sim_reset = True


def on_reset_cancel() -> None:
    S.pending_sim_reset = False


def on_reset_confirm() -> None:
    if _run(S.engine.reset):
        S.pending_sim_reset, S.summary_saved = False, False
        S.run_id, S.started_at_iso = uuid4().hex, None
        S.timer_epoch, S.timer_sequence = None, 0


def _persist_history(force: bool = False) -> None:
    """Retain terminal reports until storage confirms both files; reruns do not retry blindly."""
    engine = S.engine
    if (engine is not None and engine.session_state in ('STOPPED', 'COMPLETED')
            and S.run_id not in S.history_saved_ids and S.run_id not in S.history_outbox):
        S.history_outbox[S.run_id] = dict(summary=engine.summary(), cycles=engine.stats.cycles,
                                        run_id=S.run_id, started_at_iso=S.started_at_iso)
    for run_id, payload in list(S.history_outbox.items()):
        if not force and run_id in S.history_attempted:
            continue
        S.history_attempted.add(run_id)
        try:
            HistoryStorage.append_run(**payload)
        except Exception as error:  # noqa: BLE001
            S.sim_notice = f"Chưa ghi được lịch sử CSV: {error}"
        else:
            S.history_saved_ids.add(run_id)
            del S.history_outbox[run_id]
    S.summary_saved = S.run_id in S.history_saved_ids
    if force and not S.history_outbox:
        S.sim_notice = None


def on_retry_history() -> None:
    _persist_history(force=True)


def apply_timer_event(event) -> None:
    """Only a new event from the armed browser clock may advance an automatic tick."""
    if (not isinstance(event, dict) or event.get('epoch') != S.timer_epoch
            or not S.timer_epoch or type(event.get('sequence')) is not int
            or event['sequence'] <= S.timer_sequence):
        return
    S.timer_sequence = event['sequence']
    if S.engine is not None and S.engine.session_state == 'RUNNING':
        _run(S.engine.tick)


# ----------------------------------------------------------------------
# Helpers hiển thị
# ----------------------------------------------------------------------
def _card(title: str):
    container = st.container(border=True)
    container.markdown(f'<div class="card-title">{title}</div>', unsafe_allow_html=True)
    return container


def _metric(label: str, value: str, sub: str = "", big: bool = False) -> str:
    sub_html = f'<div class="m-sub">{sub}</div>' if sub else ""
    cls = "m-value lg" if big else "m-value"
    return f'<div><div class="m-label">{label}</div><div class="{cls}">{value}</div>{sub_html}</div>'


def _grid(*cells: str) -> str:
    return '<div class="m-grid">' + "".join(cells) + "</div>"


def _legend(snapshot: SimulationSnapshot | None, motion_on: bool) -> str:
    rows = "".join(
        f'<div class="lg-row"><span class="sw" style="background:{fill};border-color:{line}"></span>{name}</div>'
        for name, (fill, line) in VEHICLE_STYLE.items())
    colors = snapshot.signals.signal_colors if snapshot else None
    ns, ew = (colors["N"], colors["E"]) if colors else ("—", "—")
    note = "" if motion_on else '<div class="lg-note">Motion 2D đang tắt: không vẽ xe.</div>'
    return (f'<div class="legend"><div class="lg-title">Chú giải</div>{rows}'
            f'<div class="lg-phase">N/S: {ns}<br>E/W: {ew}</div>'
            '<div class="lg-note">Ô nét đứt: vùng xung đột<br>Điểm trên xe: tọa độ đầu xe</div>'
            '<div class="lg-note">Zoom ngã tư / một phần xe<br>Xe ngoài hình vẫn thuộc Core</div>'
            f'{note}</div>')


def _plot(fig) -> None:
    config = {"staticPlot": True, "displayModeBar": False}
    try:
        st.plotly_chart(fig, width="content", config=config, theme=None)
    except TypeError:   # Streamlit cũ chưa có tham số width
        st.plotly_chart(fig, use_container_width=False, config=config, theme=None)


def _dash(value) -> str:
    return "—" if value is None else str(value)


# ----------------------------------------------------------------------
# Dashboard chỉ đọc; timer phát sự kiện riêng khi RUNNING.
# ----------------------------------------------------------------------
def _dashboard() -> None:
    engine = S.engine
    dd = engine.dashboard_data() if engine is not None else None
    snap = dd.snapshot if dd else None
    run_cfg = S.run_config_snapshot if engine is not None else None
    motion_on = bool(run_cfg["motion_2d"]["enabled"]) if run_cfg else True
    preview = run_cfg or state.get_config(S.use_config_id or S.selected_config_id)
    min_gap = f'{preview["motion_2d"]["min_gap_m"]:.1f}' if preview else "—"

    col_l, col_r = st.columns([1000, 816], gap="small")

    with col_l:
        with _card("Bản đồ 2D · x dương Đông, y dương Nam · đơn vị mét"):
            map_col, legend_col = st.columns([660, 304], gap="small")
            with map_col:
                _plot(build_map_figure(snap, show_vehicles=motion_on))
            with legend_col:
                st.markdown(_legend(snap, motion_on), unsafe_allow_html=True)
        with st.container(border=True):
            if dd:
                hold = snap.metrics.clearance_hold_s
                gap = f"{dd.observed_min_gap_m:.2f}m" if dd.observed_min_gap_m is not None else "—"
                main = (f"Trong vùng: {dd.conflict_occupancy_count} xe · Min Gap cấu hình: "
                        f"{dd.min_gap_config_m:.1f}m · Clearance Hold: {hold:g}s")
                err = engine.error_message
                sub = (f"Gap thực đo nhỏ nhất: {gap} · " +
                       (f"ERROR: {escape(err)}" if err else "Không có ERROR; ERROR sẽ giữ bốn đèn đỏ."))
            else:
                main = f"Trong vùng: — · Min Gap cấu hình: {min_gap}m · Clearance Hold: —"
                sub = "Chưa có phiên mô phỏng · bấm Start để bắt đầu"
            st.markdown(f'<div class="zone-main">{main}</div><div class="zone-sub">{sub}</div>',
                        unsafe_allow_html=True)

    with col_r:
        cycles_total = run_cfg["cycles_to_run"] if run_cfg else (preview["cycles_to_run"] if preview else None)
        with _card("Tín hiệu và thời gian"):
            if snap:
                cells = (_metric("Pha hiện tại", snap.signals.current_segment),
                         _metric("Còn lại", f"{snap.signals.remaining_s} giây"),
                         _metric("Chu kỳ", f"{snap.cycle_index} / {cycles_total}"),
                         _metric("Thời gian", f"{snap.sim_time} giây"))
            else:
                cells = (_metric("Pha hiện tại", "—"), _metric("Còn lại", "—"),
                         _metric("Chu kỳ", f"— / {_dash(cycles_total)}"), _metric("Thời gian", "—"))
            st.markdown(_grid(*cells), unsafe_allow_html=True)

        with _card("Queue hiện tại · xe chưa vượt vạch"):
            q = snap.metrics.queue_lengths if snap else None
            sub = f"NS {q['N'] + q['S']} xe / EW {q['E'] + q['W']} xe" if q else ""
            st.markdown(_grid(*[
                _metric(f"Queue {d}", f"{q[d]} xe" if q else "—", sub if d == "E" else "", big=True)
                for d in "NSEW"]), unsafe_allow_html=True)

        with _card(T["counters_title"]):
            if snap:
                m = snap.metrics
                queue_total = sum(m.queue_lengths.values())
                cells = (f'<div class="ctr-cell">Xe mới đến: {m.total_arrivals}</div>',
                         f'<div class="ctr-cell">Vượt vạch: {m.crossed_stop_total}</div>',
                         f'<div class="ctr-cell">Ra khỏi khung: {m.exited_world_total}</div>',
                         f'<div class="ctr-cell">Còn chờ: {queue_total}</div>')
                note = (f"Initial {m.initial_total} + Arrivals {m.total_arrivals} = Queue {queue_total} + "
                        f"Crossed {m.crossed_stop_total} · Crossed {m.crossed_stop_total} = "
                        f"Active {m.active_crossing_count} + Exited {m.exited_world_total}")
            else:
                cells = tuple('<div class="ctr-cell">—</div>' for _ in range(4))
                note = "Chưa có dữ liệu"
            st.markdown(_grid(*cells) + f'<div class="ctr-note">{note}</div>', unsafe_allow_html=True)

        with st.container(border=True):
            if dd:
                ns, ew = dd.current_green
                prev = f"{dd.previous_green[0]}s / {dd.previous_green[1]}s" if dd.previous_green else "— / —"
                title = f"Xanh đã chốt: NS {ns}s / EW {ew}s · Chu kỳ trước: {prev}"
            else:
                title = "Xanh đã chốt: — · Chu kỳ trước: — / —"
            st.markdown(f'<div class="lock-title">{title}</div>'
                        '<div class="lock-sub">Chỉ tính lại ở đầu chu kỳ; không thay đổi tùy tiện trong từng giây.</div>',
                        unsafe_allow_html=True)

        with st.container(border=True):
            summary = dd.summary if dd else None
            s1, s2 = st.columns([5, 1.3])
            with s1:
                if summary:
                    wait = f"{summary['avg_wait_departed_s']:.1f}s" if summary['avg_wait_departed_s'] is not None else "—"
                    stopped = f"{summary['avg_stopped_delay_s']:.1f}s" if summary['avg_stopped_delay_s'] is not None else "—"
                    sub = (f"{summary['status']} · {summary['departed_vehicles']} xe đã qua vạch · còn chờ "
                           f"{summary['remaining_vehicles']} · thời gian từ xuất hiện tới vượt vạch TB {wait}"
                           f" · thời gian dừng TB {stopped}")
                else:
                    sub = "Mở khi STOPPED/COMPLETED · không đồng nghĩa hết xe chờ"
                st.markdown(f'<div class="sum-title">Summary cuối phiên: {"có" if summary else "chưa có"}</div>'
                            f'<div class="sum-sub">{sub}</div>', unsafe_allow_html=True)
            with s2:
                exportable = summary is not None and summary['status'] in ('STOPPED', 'COMPLETED')
                data = summary_csv_text(summary, dd.cycle_metrics, run_id=S.run_id,
                                        started_at_iso=S.started_at_iso) if exportable else ""
                st.download_button("Xuất CSV", data, file_name=f"{S.run_id}.csv" if exportable else "summary.csv",
                                   mime="text/csv", key="btn_csv", disabled=not exportable)

    # ---- Ba biểu đồ ----
    c1, c2, c3 = st.columns(3, gap="small")
    with c1:
        with _card("Queue Length theo thời gian"):
            charts.render(charts.queue_chart(dd.queue_series) if dd else charts.empty_chart())
    with c2:
        with _card("Green NS/EW theo chu kỳ"):
            charts.render(charts.green_chart(dd.cycle_metrics) if dd else charts.empty_chart())
    with c3:
        with _card("Arrivals / Departures theo chu kỳ"):
            charts.render(charts.flow_chart(dd.cycle_metrics) if dd else charts.empty_chart())


# ----------------------------------------------------------------------
# Render
# ----------------------------------------------------------------------
def render_simulation_tab() -> None:
    engine = S.engine
    event = timer_event(S.timer_epoch, bool(engine is not None and engine.session_state == 'RUNNING'),
                        key=f"clock_{S.run_id or 'idle'}")
    apply_timer_event(event)
    _persist_history()
    engine = S.engine
    name = engine.session_state if engine is not None else "IDLE"
    unstarted = engine is not None and not engine.has_started
    ready = S.manager is not None and state.get_config(S.use_config_id or S.selected_config_id) is not None

    # ---- Cấu hình đã chốt ----
    saved_cfg = _selected_saved_config()
    cfg = S.run_config_snapshot if engine is not None else saved_cfg
    has_new_config = (engine is not None and saved_cfg is not None
                      and S.run_config_snapshot is not None and saved_cfg != S.run_config_snapshot)
    with st.container(border=True):
        if cfg:
            r, q = cfg["rates_per_min"], cfg
            tail = "bản cấu hình đã chốt khi Start" if engine is not None else "bản cấu hình sẽ chốt khi Start"
            st.markdown(
                f'<div class="run-title">{escape(cfg["id"])} · {escape(cfg["name"])} · {tail}</div>'
                f'<div class="run-sub">N {r["N"]:g} / S {r["S"]:g} / E {r["E"]:g} / W {r["W"]:g} xe/phút | '
                f'Tổng xanh {q["green_budget_s"]} giây | {q["cycles_to_run"]} chu kỳ | Seed {q["seed"]}</div>',
                unsafe_allow_html=True)
        else:
            st.markdown('<div class="run-title">Chưa có cấu hình để chạy</div>'
                        '<div class="run-sub">Tạo hoặc chọn một cấu hình ở tab Quản lý cấu hình.</div>',
                        unsafe_allow_html=True)

    # ---- Cảnh báo khi cấu hình đã lưu khác bản chốt của Engine ----
    if has_new_config:
        old_cfg = S.run_config_snapshot
        if old_cfg["id"] == saved_cfg["id"]:
            st.warning(
                f"Cấu hình '{saved_cfg['id']}' đã được lưu với {saved_cfg['cycles_to_run']} chu kỳ, "
                f"nhưng phiên hiện tại vẫn dùng {old_cfg['cycles_to_run']} chu kỳ. "
                "Thông số phiên đang chạy không tự thay đổi; Reset sẽ phát lại bản cũ."
            )
        else:
            st.warning(
                f"Phiên hiện tại đang dùng '{old_cfg['id']}' "
                f"({old_cfg['cycles_to_run']} chu kỳ); cấu hình được chọn cho phiên tiếp theo "
                f"là '{saved_cfg['id']}' ({saved_cfg['cycles_to_run']} chu kỳ)."
            )
        if name == 'RUNNING':
            st.caption("Hãy Pause hoặc Stop rồi áp dụng cấu hình mới để tạo phiên khác.")
        else:
            st.button(
                f"Áp dụng cấu hình đã lưu ({saved_cfg['cycles_to_run']} chu kỳ) và chạy phiên mới",
                key="sim_apply_new_config", on_click=on_apply_new_config_ask,
            )
            if S.pending_new_config:
                with st.container(border=True):
                    st.markdown(
                        f"**Xác nhận tạo phiên mới với {saved_cfg['cycles_to_run']} chu kỳ?** "
                        "Phiên cũ sẽ dừng và được lưu lịch sử khi có thể; "
                        "tiến độ hiện tại không được chuyển sang phiên mới."
                    )
                    a, b, _ = st.columns([1, 2, 5])
                    a.button("Hủy", key="sim_apply_new_config_cancel",
                             on_click=on_apply_new_config_cancel)
                    b.button("Xác nhận dùng cấu hình mới", key="sim_apply_new_config_confirm",
                             on_click=on_apply_new_config_confirm)
    elif S.pending_new_config:
        S.pending_new_config = False

    # ---- Thanh điều khiển ----
    ctl = st.columns([113, 113, 129, 111, 113, 149, 213, 244, 590], gap="small")
    start_label = "Start (phát lại bản cũ)" if has_new_config and unstarted else "Start"
    ctl[0].button(start_label, key="sim_start", on_click=on_start,
                  disabled=not (unstarted or ready and (engine is None or name in FINISHED)))
    ctl[1].button("Pause", key="sim_pause", on_click=on_pause, disabled=name != "RUNNING")
    ctl[2].button("Resume", key="sim_resume", on_click=on_resume, disabled=name != "PAUSED" or unstarted)
    ctl[3].button("Stop", key="sim_stop", on_click=on_stop, disabled=name not in ("RUNNING", "PAUSED") or unstarted)
    ctl[4].button("Reset", key="sim_reset", on_click=on_reset_ask,
                  disabled=engine is None or name == "RUNNING")
    ctl[5].button("Step +1s", key="sim_step", on_click=on_step, disabled=name != "PAUSED" or unstarted)
    ctl[6].button("Chạy hết chu kỳ", key="sim_cycle", on_click=on_cycle, disabled=name != "PAUSED" or unstarted)
    ctl[8].markdown(
        f'<div class="status-box">{name}{T["status_suffix"]} · Step / Chạy chu kỳ chỉ bật khi PAUSED</div>',
        unsafe_allow_html=True)

    if S.pending_sim_reset:
        with st.container(border=True):
            st.markdown('<p class="banner" style="font-size:16px">Bỏ tiến độ hiện tại và chạy lại từ đầu '
                        "(cùng bản chốt, cùng seed)?</p>", unsafe_allow_html=True)
            a, b, _ = st.columns([1, 1.4, 6])
            a.button("Hủy", key="sim_reset_cancel", on_click=on_reset_cancel)
            b.button("Xác nhận Reset", key="sim_reset_confirm", on_click=on_reset_confirm)
    if S.sim_notice:
        st.markdown(f'<div class="field-err">{escape(S.sim_notice)}</div>', unsafe_allow_html=True)
    if S.history_outbox:
        st.warning(f"Còn {len(S.history_outbox)} phiên chưa lưu đủ lịch sử; báo cáo được giữ để thử lại.")
        st.button("Thử lại ghi lịch sử", key="sim_history_retry", on_click=on_retry_history)

    _dashboard()

    st.markdown('<p class="foot">Core → Snapshot / báo cáo chỉ đọc → Renderer · '
                "UI không tự sinh xe, tính Adaptive, sửa Queue hoặc CSV</p>", unsafe_allow_html=True)
