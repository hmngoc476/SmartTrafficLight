"""Streamlit skeleton; chỉ hiển thị giao diện, không chứa nghiệp vụ."""

import streamlit as st

st.set_page_config(page_title="Smart Traffic Light Simulator", layout="wide")
st.title("Smart Traffic Light Simulator")
configuration_tab, simulation_tab = st.tabs(["Quản lý cấu hình", "Mô phỏng 2D"])
with configuration_tab:
    st.info("Chức năng quản lý cấu hình đang phát triển.")
with simulation_tab:
    st.info("Chức năng mô phỏng xe 2D đang phát triển.")
