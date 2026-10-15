"""Streamlit skeleton; chỉ hiển thị giao diện, không chứa nghiệp vụ."""

import streamlit as st
import pandas as pd

from src.core.storage import FileStorage
from src.core.manager import ConfigManager
from src.models.config import Config, Motion2DConfig

from src.ui.tab1_config import render_tab1
from src.ui.tab2_sim import render_tab2
#Config the Streamlit page
st.set_page_config(page_title="Smart Traffic Light Simulator", layout="wide")
st.title("Smart Traffic Light Simulator")

#Initialize ConfigManager
manager = ConfigManager()

#Create 2 tabs
configuration_tab, simulation_tab = st.tabs(["Quản lý cấu hình", "Mô phỏng 2D"])

#========================================================================================
#TAB 1: CRUD
with configuration_tab:
    st.info("Chức năng quản lý cấu hình đang phát triển.")
with simulation_tab:
    st.info("Chức năng mô phỏng xe 2D đang phát triển.")
