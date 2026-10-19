"""Browser timer events, separate from ordinary Streamlit widget reruns."""
from pathlib import Path
from streamlit.components.v1 import declare_component

_clock = declare_component('simulation_clock', path=str(Path(__file__).with_name('clock')))


def timer_event(epoch: str | None, running: bool, *, key: str):
    return _clock(epoch=epoch or '', running=running, key=key, default=None)
