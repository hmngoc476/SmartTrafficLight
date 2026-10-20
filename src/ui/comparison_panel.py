"""Compare the finished browser session with Fixed-Time and export its report."""

import streamlit as st

from src.core.comparison import compare_finished_run, comparison_csv_text, comparison_rows
from src.models.config import Config


def _format(value, *, percent=False):
    if value is None:
        return '—'
    return f'{value:+.2f}%' if percent else f'{value:,.2f}'


def render_comparison_panel() -> None:
    session = st.session_state
    if session.comparison_run_id != session.run_id:
        session.comparison_run_id = session.run_id
        session.comparison_result = None
        session.comparison_error = None
    engine = session.engine
    ready = (engine is not None and engine.session_state == 'COMPLETED'
             and engine.sim_time > 0)
    if not ready:
        # Discard reports from early Stop, including sessions opened before this rule.
        session.comparison_result = None
        session.comparison_error = None
    with st.container(border=True):
        st.markdown('**So sánh phiên vừa chạy với Fixed-Time**')
        if st.button('So sánh với Fixed-Time', key='sim_compare_fixed',
                     disabled=not ready or session.comparison_result is not None) and ready:
            session.comparison_error = None
            try:
                with st.spinner('Đang chạy đối chứng cùng thời gian với phiên vừa kết thúc…'):
                    config = Config.from_dict(session.run_config_snapshot)
                    session.comparison_result = compare_finished_run(config, engine.summary())
            except Exception as error:  # noqa: BLE001 - keep the original session and allow retry.
                session.comparison_error = str(error)
        if session.comparison_error:
            st.error(f'Chưa tạo được báo cáo so sánh: {session.comparison_error}')
        result = session.comparison_result
        if result is None:
            return

        config = Config.from_dict(session.run_config_snapshot)
        green_ns = config.green_budget_s // 2
        st.write(f'Cấu hình: {config.id} · {config.name} · Seed: {result.seed} · '
                 f'Thời gian đối chứng: {result.horizon_s}s · '
                 f'Fixed-Time: NS {green_ns}s / EW {config.green_budget_s - green_ns}s')
        if not result.comparable:
            st.warning('Fixed-Time chưa chạy đủ thời gian hoặc gặp lỗi. '
                       'Các giá trị chỉ dùng chẩn đoán; không tính chênh lệch hay % cải thiện.')
            if result.fixed.summary['error_message']:
                st.error(result.fixed.summary['error_message'])
        rows = comparison_rows(result)
        st.table([{
            'Chỉ số': f"{row['label']} ({row['unit']})",
            'Adaptive': _format(row['adaptive']),
            'Fixed-Time': _format(row['fixed']),
            'Cải thiện của Adaptive': _format(row['improvement_pct'], percent=True),
        } for row in rows[:8]])
        st.caption('Cải thiện dương: Adaptive tốt hơn theo chỉ số đó; âm: kém hơn. '
                   '“—”: thiếu mẫu, mốc Fixed-Time bằng 0 hoặc chỉ số chỉ dùng giải thích. '
                   'Thời gian dừng chỉ tính trên xe đã vượt vạch. Đây là kết quả một kịch bản và một seed.')
        data = comparison_csv_text(result, config, run_id=session.run_id,
                                   started_at_iso=session.started_at_iso)
        st.download_button('Tải CSV so sánh', data.encode('utf-8-sig'),
                           file_name=f'{session.run_id}_comparison.csv', mime='text/csv',
                           key='btn_comparison_csv')
