import streamlit as st
import pandas as pd

def render_tab1():
    st.markdown("### Quản lý cấu hình")

    manager = st.session_state.manager
    configs = manager.list()
    config_ids = [c["id"] for c in configs] if configs else []

    # Box 1: Bảng dữ liệu cấu hình
    with st.container(border=True):
        st.markdown("**Danh sách cấu hình · Xem, chọn và quản lý các giao lộ**")
        if configs:
            df = pd.DataFrame(configs)
            st.dataframe(df, use_container_width=True)
        else:
            st.info("Chưa có cấu hình nào trong bảng dữ liệu.")

        selected_id = st.selectbox("Chọn theo ID:", options=config_ids if config_ids else ["Tạo mới"])
        current_cfg = manager.get(selected_id) if selected_id in config_ids else {}

        # Box 2: Trạng thái đang chọn
        with st.container(border=True):
            st.markdown(
                f"**Đang chọn: {selected_id} | {current_cfg.get('name', 'Giao lộ mẫu - lệch hướng Đông Tây')} | Chế độ: chỉnh sửa bản mẫu**")

        # Bố cục 3 cột bám sát Wireframe
        col1, col2, col3 = st.columns(3)

        with col1:
            # Box 3: Thông tin chung
            with st.container(border=True):
                st.markdown("##### Thông tin chung")
                st.text_input("Tên cấu hình", value=current_cfg.get("name", "Giao lộ mẫu - lệch hướng Đông Tây"))
                st.text_input("Configuration ID · hệ thống quản lý / chỉ đọc", value=selected_id, disabled=True)

            # Box 4: Lưu lượng bốn hướng
            with st.container(border=True):
                st.markdown("##### Lưu lượng bốn hướng")
                r_cols = st.columns(4)
                rates = current_cfg.get("rates_per_min", {})
                r_cols[0].number_input("N · xe/phút", min_value=0, max_value=30, value=rates.get("N", 12))
                r_cols[1].number_input("S · xe/phút", min_value=0, max_value=30, value=rates.get("S", 9))
                r_cols[2].number_input("E · xe/phút", min_value=0, max_value=30, value=rates.get("E", 18))
                r_cols[3].number_input("W · xe/phút", min_value=0, max_value=30, value=rates.get("W", 7))

            # Box 5: Hàng chờ ban đầu
            with st.container(border=True):
                st.markdown("##### Hàng chờ ban đầu · Initial Queue")
                q_cols = st.columns(4)
                inits = current_cfg.get("initial_queue", {})
                q_cols[0].number_input("Initial N · xe", min_value=0, max_value=100, value=inits.get("N", 7))
                q_cols[1].number_input("Initial S · xe", min_value=0, max_value=100, value=inits.get("S", 4))
                q_cols[2].number_input("Initial E · xe", min_value=0, max_value=100, value=inits.get("E", 16))
                q_cols[3].number_input("Initial W · xe", min_value=0, max_value=100, value=inits.get("W", 5))


        with col2:
            # Box 6: Thông số tín hiệu
            with st.container(border=True):
                st.markdown("##### Thông số tín hiệu")
                sig_c1, sig_c2 = st.columns(2)
                gb = sig_c1.number_input("Green Budget · giây", min_value=10,
                                         value=current_cfg.get("green_budget_s", 60))
                mg = sig_c2.number_input("Min Green · giây", min_value=1, value=current_cfg.get("min_green_s", 10))
                sig_c1.number_input("Yellow · giây", min_value=1, value=current_cfg.get("yellow_s", 3))
                sig_c2.number_input("All Red · giây", min_value=1, value=current_cfg.get("all_red_s", 1))
                sig_c1.number_input("Startup Delay · giây", min_value=0, value=current_cfg.get("startup_delay_s", 2))
                sig_c2.number_input("Headway · giây", min_value=1, value=current_cfg.get("headway_s", 2))
                st.caption("Ràng buộc: Green Budget ≥ 2 × Min Green")

            # Box 7: Thông số mô phỏng
            with st.container(border=True):
                st.markdown("##### Thông số mô phỏng")
                sim_c1, sim_c2 = st.columns(2)
                sim_c1.number_input("Số chu kỳ · 1-100", min_value=1, max_value=100,
                                    value=current_cfg.get("cycles_to_run", 10))
                sim_c2.number_input("Random seed · số nguyên", value=current_cfg.get("seed", 2026))

            # Box 8: Lỗi Validation
            with st.container(border=True):
                st.markdown("##### Vị trí lỗi validation · trạng thái minh họa")
                st.caption("Thiếu tên / ID trùng · Sai lưu lượng / thiếu hướng · Sai xanh / motion")


        with col3:
            # Box 9: Chuyển động 2D
            with st.container(border=True):
                st.markdown("##### Thông số chuyển động 2D")
                motion = current_cfg.get("motion_2d", {})
                st.toggle("Bật motion 2D · enabled = true", value=motion.get("enabled", True))

                m_c1, m_c2 = st.columns(2)
                m_c1.number_input("dt · giây / substep", value=motion.get("dt_s", 0.2), disabled=True)
                m_c2.number_input("Vehicle Length · mét", value=motion.get("vehicle_length_m", 4.5))
                m_c1.number_input("Min Gap · mét", value=motion.get("min_gap_m", 2.0))
                m_c2.number_input("Max Speed · m/s", value=motion.get("max_speed_mps", 9.0))
                m_c1.number_input("Acceleration · m/s²", value=motion.get("accel_mps2", 2.0))
                m_c2.number_input("Approach Visible · mét", value=motion.get("approach_visible_m", 60.0))
                m_c1.number_input("Intersection Width · mét", value=motion.get("intersection_width_m", 16.0))
                m_c2.number_input("Stop Margin · mét", value=motion.get("stop_margin_m", 0.5))
                m_c1.number_input("Clearance Limit · giây", value=motion.get("clearance_limit_s", 30))

            # Box 10: Các nút thao tác
            with st.container(border=True):
                b1, b2, b3, b4, b5, b6 = st.columns(6)
                b1.button("Tạo mới", use_container_width=True)
                if b2.button("Lưu cấu hình", use_container_width=True):
                    st.success("Đã lưu cấu hình thành công!")
                b3.button("Cập nhật", use_container_width=True)
                b4.button("Xóa · cần xác nhận", use_container_width=True)
                if b5.button("Dùng cấu hình này", type="primary", use_container_width=True):
                    st.session_state.selected_config_id = selected_id
                    st.success("Đã chọn cấu hình để đưa sang Tab Mô phỏng!")
                b6.button("Làm mới biểu mẫu", use_container_width=True)