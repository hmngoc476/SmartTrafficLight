import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import pytest
from src.core.controller import TrafficLightController
from src.core.movement import MovementEngine
from src.core.simulation import SimulationEngine
from src.models.config import Config
from src.models.lane import Lane
from src.models.snapshot import DIRECTIONS


def get_default_config() -> Config:
    return Config(
        id="test_cfg",
        name="Test Junction",
        green_budget_s=60,
        min_green_s=10,
        yellow_s=3,
        all_red_s=1,
        startup_delay_s=2,
        headway_s=2,
        cycles_to_run=2,
        rates_per_min={"N": 0.0, "S": 0.0, "E": 0.0, "W": 0.0},
        initial_queue={"N": 0, "S": 0, "E": 0, "W": 0},
    )


# ==========================================
# TEST CONTROLLER & R3 CLEARANCE
# ==========================================
def test_controller_initial_and_segments():
    config = get_default_config()
    controller = TrafficLightController(config)
    queues = {"N": 5, "S": 5, "E": 5, "W": 5}
    controller.start_next_cycle(queues, cycle_no=1, started_at=0, conflict_clear=True)

    assert controller.current_segment_code == "NS_GREEN"
    assert controller.remaining_s == 30  # 60 chia đều 30/30
    assert controller.is_green_for("N") is True
    assert controller.is_green_for("E") is False


def test_controller_r3_clearance_hold_and_timeout():
    config = get_default_config()
    config.motion_2d.clearance_limit_s = 2.0  # Ngưỡng timeout 2s
    controller = TrafficLightController(config)
    queues = {"N": 5, "S": 5, "E": 5, "W": 5}
    controller.start_next_cycle(queues, cycle_no=1, started_at=0, conflict_clear=True)

    # Chạy hết NS_GREEN (30s) + NS_YELLOW (3s) -> 33s
    for _ in range(33):
        controller.tick(conflict_clear=True)

    # Hiện tại là ALL_RED_1, remaining_s = 1
    assert controller.current_segment_code == "ALL_RED_1"
    assert controller.remaining_s == 1

    # Tick 34: hết nominal duration (về 0) nhưng vùng CHƯA CLEAR (conflict_clear=False)
    controller.tick(conflict_clear=False)
    assert controller.current_segment_code == "ALL_RED_1"
    assert controller.remaining_s == 0
    assert controller.clearance_hold_s == 0  # boundary chạm 0 chưa tính hold
    assert controller.in_error is False

    # Tick 35: hold_elapsed = 1s <= 2.0s
    controller.tick(conflict_clear=False)
    assert controller.clearance_hold_s == 1
    assert controller.in_error is False

    # Tick 36: hold_elapsed = 2s <= 2.0s
    controller.tick(conflict_clear=False)
    assert controller.clearance_hold_s == 2
    assert controller.in_error is False

    # Tick 37: hold_elapsed = 3s > 2.0s -> TIMEOUT -> in_error = True
    # Kể cả nếu lúc này occupancy báo clear, đã vượt ngưỡng thì vẫn chuyển ERROR
    controller.tick(conflict_clear=True)
    assert controller.in_error is True
    assert controller.current_segment_code == "ALL_RED_1"


# ==========================================
# TEST MOVEMENT ENGINE & XE QUA VẠCH
# ==========================================
def test_movement_spawn_and_crossing():
    config = get_default_config()
    lanes = {d: Lane(d) for d in DIRECTIONS}
    movement = MovementEngine(config, lanes)
    controller = TrafficLightController(config)
    controller.start_next_cycle({"N": 1, "S": 0, "E": 0, "W": 0}, cycle_no=1, started_at=0, conflict_clear=True)

    # Spawn 1 xe tại hướng N
    v = movement.spawn_and_enqueue("N", arrival_t=0.0)
    assert v.status == "WAITING"
    assert lanes["N"].count() == 1
    assert len(movement.active_crossing) == 0

    # Đặt xe gần vạch dừng: s = -0.5 (ngay trước stop margin)
    v.update_motion(-0.5, speed_mps=0.0)

    # Kích hoạt green clock cho Lane N (t=0, startup=0, headway=1 để test nhanh)
    lanes["N"].reset_green_clock(started_at=0.0, startup_delay_s=0.0, headway_s=1.0)
    assert lanes["N"].is_cross_eligible(0.0) is True

    # Cho xe chạy các substep dt = 0.2 cho đến khi qua vạch
    for step in range(10):
        t = step * 0.2
        movement.advance_substep(t=t, dt=0.2, controller=controller)
        if v.status == "PASSED":
            break

    # Xe phải vượt qua vạch dừng: s >= 0, status PASSED, đã vào active_crossing
    assert v.status == "PASSED"
    assert v.crossed_stop_t is not None
    assert lanes["N"].count() == 0  # Đã pop khỏi Queue
    assert len(movement.active_crossing) == 1
    assert movement.active_crossing[0] is v
    assert movement.is_conflict_clear() is False  # Xe đang trong vùng giao lộ


# ==========================================
# TEST SIMULATION ENGINE (START, TICK, PAUSE, RESET)
# ==========================================
def test_simulation_engine_lifecycle():
    config = get_default_config()
    config.initial_queue["N"] = 1
    engine = SimulationEngine(config)

    assert engine.session_state == "PAUSED"
    assert engine.sim_time == 0
    assert engine.cycle_index == 1

    # Trước khi start, tick phải raise
    with pytest.raises(RuntimeError):
        engine.tick()

    # Start
    engine.start()
    assert engine.session_state == "RUNNING"

    # Chạy 1 tick (1 giây = 5 substeps 0.2s)
    snap = engine.tick()
    assert engine.sim_time == 1
    assert snap.sim_time == 1
    assert snap.session_state == "RUNNING"

    # Pause
    engine.pause()
    assert engine.session_state == "PAUSED"
    with pytest.raises(RuntimeError):
        engine.tick()

    # Resume
    engine.resume()
    assert engine.session_state == "RUNNING"

    # Chạy tiếp n ticks
    engine.run_ticks(3)
    assert engine.sim_time == 4

    # Reset
    engine.reset()
    assert engine.sim_time == 0
    assert engine.session_state == "PAUSED"
