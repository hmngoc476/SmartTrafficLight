import streamlit as st
from src.ui.renderer_2d import render_traffic_2d


def render_tab2():
    config_id = st.session_state.selected_config_id

    # Box: Cấu hình đang chạy
    with st.container(border=True):
        st.markdown(f"**{config_id} · Giao lộ mẫu - lệch hướng Đông Tây · bản cấu hình đã chốt khi Start**")
        st.caption("N 12 / S 9 / E 18 / W 7 xe/phút | Tổng xanh 60 giây | 10 chu kỳ | Seed 2026")

    # Toolbar Điều khiển
    btn_col1, btn_col2, btn_col3, btn_col4, btn_col5, btn_col6, btn_col7 = st.columns(7)
    btn_col1.button("Start", type="primary", use_container_width=True)
    btn_col2.button("Pause", use_container_width=True)
    btn_col3.button("Resume", use_container_width=True)
    btn_col4.button("Stop", use_container_width=True)
    btn_col5.button("Reset", use_container_width=True)
    btn_col6.button("Step +1s", use_container_width=True)
    btn_col7.button("Chạy hết chu kỳ", use_container_width=True)

    st.divider()

    # Bố cục 2 phần: Trái là Bản đồ, Phải là HUD
    sim_left_col, sim_right_col = st.columns([3, 2])

    with sim_left_col:
        # Box: Bản đồ 2D
        with st.container(border=True):
            snapshot_data = getattr(st.session_state.engine, "snapshot", lambda: None)()
            fig = render_traffic_2d(snapshot_data)
            st.plotly_chart(fig, use_container_width=True)
            st.caption("Trong vùng: 2 xe · Min Gap cấu hình: 2.0m · Clearance Hold: 0s")

    with sim_right_col:
        # Box: Tín hiệu và thời gian
        with st.container(border=True):
            st.markdown("##### Tín hiệu và thời gian")
            m1, m2, m3, m4 = st.columns(4)
            m1.metric("Pha hiện tại", "NS_GREEN")
            m2.metric("Còn lại", "9 giây")
            m3.metric("Chu kỳ", "1 / 10")
            m4.metric("Thời gian", "12 giây")

        # Box: Queue hiện tại
        with st.container(border=True):
            st.markdown("##### Queue hiện tại · xe chưa vượt vạch")
            q1, q2, q3, q4 = st.columns(4)
            q1.metric("Queue N", "6 xe")
            q2.metric("Queue S", "4 xe")
            q3.metric("Queue E", "17 xe")
            q4.metric("Queue W", "6 xe")

        # Box: Counters lũy kế
        with st.container(border=True):
            st.markdown("##### Counters lũy kế phiên · dữ liệu minh họa")
            st.write(
                "• **Xe mới đến:** 4 &nbsp;&nbsp; • **Vượt vạch:** 3 &nbsp;&nbsp; • **Ra khỏi khung:** 0 &nbsp;&nbsp; • **Còn chờ:** 33")

        # Box: Xanh đã chốt
        with st.container(border=True):
            st.info("Xanh đã chốt: NS 21s / EW 39s · Chu kỳ trước: — / —")

        # Box: Xuất CSV
        with st.container(border=True):
            c_sum, c_btn = st.columns([3, 1])
            c_sum.write("Summary cuối phiên: chưa có")
            c_btn.button("Xuất CSV", use_container_width=True)

    # Dãy Box Biểu đồ (3 cột)
    c1, c2, c3 = st.columns(3)
    with c1:
        with st.container(border=True):
            st.caption("Queue Length theo thời gian")
            st.line_chart([7, 10, 15, 12, 8, 5])
    with c2:
        with st.container(border=True):
            st.caption("Green NS/EW theo chu kỳ")
            st.bar_chart({"NS": 21, "EW": 39})
    with c3:
        with st.container(border=True):
            st.caption("Arrivals / Departures theo chu kỳ")
            st.bar_chart({"Arrivals": 4, "Departures": 3})