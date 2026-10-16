"""SimulationEngine điều phối toàn bộ mô phỏng ngã tư thông minh.

Nhiệm vụ:
- Quản lý vòng đời phiên: start, tick, pause, resume, stop, reset, snapshot.
- Sở hữu sim_time và cycle_index.
- Tuân thủ quy tắc R3 (Clearance timeout) và R4 (Tick và chu kỳ):
  - Trong [t, t+1), xe di chuyển theo tín hiệu tại t.
  - Cuối khoảng, lấy occupancy (conflict_clear), gọi Controller.tick(conflict_clear=...),
    cập nhật sim_time=t+1, chốt snapshot tại ranh giới mới.
  - Ghi nhận sự kiện vượt/ra thế giới theo chuyển động đã xảy ra; không gán cho tín hiệu mới.
  - Khi ALL_RED_2 kết thúc an toàn, chốt metrics chu kỳ cũ, kiểm tra cycles_to_run.
    Nếu còn, truyền cycle_index + 1 và Queue mới cho Controller; chỉ cập nhật index sau khi thành công.
  - Nếu hết chu kỳ, giữ ALL_RED_2, remaining_s=0, chuyển sang COMPLETED.
  - Nếu timeout/in_error, Controller giữ ALL_RED và in_error=True; Engine chuyển session sang ERROR và dừng tick.
"""

import random
from collections.abc import Mapping
from typing import Literal

from src.core.algorithms import poisson_sample
from src.core.controller import TrafficLightController
from src.core.geometry import Geometry
from src.core.movement import MovementEngine
from src.models.config import Config
from src.models.lane import Lane
from src.models.snapshot import (
    DIRECTIONS,
    Direction,
    MetricsSnapshot,
    SessionState,
    SimulationSnapshot,
    VehicleSnapshot,
)


class SimulationEngine:
    """SimulationEngine vận hành độc lập UI, điều phối Controller, Movement và sinh xe Poisson."""

    def __init__(self, config: Config) -> None:
        if not isinstance(config, Config):
            raise TypeError("config phải là instance của Config.")
        config.validate()
        self._config = Config.from_dict(config.to_dict())

        self._sim_time: int = 0
        self._cycle_index: int = 1
        self._session_state: SessionState = "PAUSED"  # Sẵn sàng start() -> RUNNING
        self._rng = random.Random(self._config.seed)

        self._geometry = Geometry(
            intersection_width_m=self._config.motion_2d.intersection_width_m,
            approach_visible_m=self._config.motion_2d.approach_visible_m,
            vehicle_length_m=self._config.motion_2d.vehicle_length_m,
            min_gap_m=self._config.motion_2d.min_gap_m,
            stop_margin_m=self._config.motion_2d.stop_margin_m,
        )

        self._lanes: dict[str, Lane] = {d: Lane(d) for d in DIRECTIONS}
        self._controller = TrafficLightController(self._config)
        self._movement = MovementEngine(self._config, self._lanes, self._geometry)

        # Counters theo dõi toàn phiên
        self._initial_total: int = 0
        self._total_arrivals: int = 0
        self._crossed_stop_total: int = 0
        self._exited_world_total: int = 0

        # Khởi tạo ban đầu (initial queue)
        self._initialize_queues()

        # Bắt đầu chu kỳ 1 trên Controller
        queue_lengths = {d: self._lanes[d].count() for d in DIRECTIONS}
        self._controller.start_next_cycle(
            queue_lengths,
            cycle_no=self._cycle_index,
            started_at=self._sim_time,
            conflict_clear=True,
        )
        self._update_lane_green_clocks()

    @property
    def sim_time(self) -> int:
        return self._sim_time

    @property
    def cycle_index(self) -> int:
        return self._cycle_index

    @property
    def session_state(self) -> SessionState:
        return self._session_state

    @property
    def controller(self) -> TrafficLightController:
        return self._controller

    @property
    def movement(self) -> MovementEngine:
        return self._movement

    def _initialize_queues(self) -> None:
        """Tạo các xe ban đầu theo initial_queue trong config."""
        for direction in DIRECTIONS:
            count = self._config.initial_queue.get(direction, 0)
            for _ in range(count):
                self._movement.spawn_and_enqueue(direction, arrival_t=0.0)
                self._initial_total += 1

    def _update_lane_green_clocks(self) -> None:
        """Thông báo reset_green_clock cho các Lane khi tín hiệu chuyển GREEN."""
        seg_code = self._controller.current_segment_code
        if seg_code == "NS_GREEN":
            self._lanes["N"].reset_green_clock(
                started_at=float(self._sim_time),
                startup_delay_s=float(self._config.startup_delay_s),
                headway_s=float(self._config.headway_s),
            )
            self._lanes["S"].reset_green_clock(
                started_at=float(self._sim_time),
                startup_delay_s=float(self._config.startup_delay_s),
                headway_s=float(self._config.headway_s),
            )
            self._lanes["E"].reset_green_clock(None)
            self._lanes["W"].reset_green_clock(None)
        elif seg_code == "EW_GREEN":
            self._lanes["E"].reset_green_clock(
                started_at=float(self._sim_time),
                startup_delay_s=float(self._config.startup_delay_s),
                headway_s=float(self._config.headway_s),
            )
            self._lanes["W"].reset_green_clock(
                started_at=float(self._sim_time),
                startup_delay_s=float(self._config.startup_delay_s),
                headway_s=float(self._config.headway_s),
            )
            self._lanes["N"].reset_green_clock(None)
            self._lanes["S"].reset_green_clock(None)
        else:
            for d in DIRECTIONS:
                self._lanes[d].reset_green_clock(None)

    def start(self) -> None:
        """Bắt đầu chạy mô phỏng."""
        if self._session_state in ("COMPLETED", "ERROR"):
            raise RuntimeError(f"Không thể start từ trạng thái {self._session_state}.")
        self._session_state = "RUNNING"

    def pause(self) -> None:
        """Tạm dừng mô phỏng."""
        if self._session_state == "RUNNING":
            self._session_state = "PAUSED"

    def resume(self) -> None:
        """Tiếp tục mô phỏng khi đang pause."""
        if self._session_state == "PAUSED":
            self._session_state = "RUNNING"

    def stop(self) -> None:
        """Dừng hẳn phiên mô phỏng."""
        self._session_state = "STOPPED"

    def reset(self) -> None:
        """Tái thiết lập toàn bộ mô phỏng về trạng thái ban đầu."""
        self.__init__(self._config)

    def tick(self) -> SimulationSnapshot:
        """Thực hiện một bước tick 1 giây logic theo đúng hợp đồng R3, R4."""
        if self._session_state != "RUNNING":
            raise RuntimeError(f"Chỉ có thể tick khi session ở trạng thái RUNNING (hiện tại: {self._session_state}).")

        t_current = float(self._sim_time)
        dt = self._config.motion_2d.dt_s
        substeps = int(round(1.0 / dt))

        # 1. Sinh xe mới theo Poisson (1 lần mỗi giây cho mỗi hướng N -> S -> E -> W)
        for direction in DIRECTIONS:
            rate_per_min = self._config.rates_per_min[direction]
            lam = rate_per_min / 60.0
            arrivals = poisson_sample(lam, self._rng)
            for _ in range(arrivals):
                self._movement.spawn_and_enqueue(direction, arrival_t=t_current)
                self._total_arrivals += 1

        # 2. Xe di chuyển trong khoảng [t, t+1) với tín hiệu đang áp dụng
        for step in range(substeps):
            sub_t = t_current + step * dt
            self._movement.advance_substep(t=sub_t, dt=dt, controller=self._controller)

        # Cập nhật số xe đã crossing và exited sau chuyển động
        # Tổng số xe đã crossing = số xe đang active_crossing + số xe đã exited
        self._crossed_stop_total = len(self._movement.active_crossing) + len(self._movement.exited_vehicles)
        self._exited_world_total = len(self._movement.exited_vehicles)

        # 3. Cuối khoảng: Engine lấy kết quả occupancy (conflict_clear)
        conflict_clear = self._movement.is_conflict_clear()

        # Lưu lại trạng thái đoạn tín hiệu trước tick để kiểm tra chuyển đoạn
        prev_segment = self._controller.current_segment_code

        # Gọi Controller.tick(conflict_clear=...)
        self._controller.tick(conflict_clear=conflict_clear)

        # Cập nhật sim_time = t + 1
        self._sim_time += 1

        # Kiểm tra nếu controller báo ERROR (do clearance timeout)
        if self._controller.in_error:
            self._session_state = "ERROR"
            return self.snapshot()

        # Kiểm tra chu kỳ hoàn tất an toàn tại ALL_RED_2
        if self._controller.cycle_complete:
            # Chu kỳ hiện tại đã xong
            if self._cycle_index >= self._config.cycles_to_run:
                # Đã đạt giới hạn chu kỳ: hoàn thành phiên mô phỏng
                self._session_state = "COMPLETED"
            else:
                # Vẫn còn chu kỳ tiếp theo: chuyển sang cycle_index + 1
                next_cycle_index = self._cycle_index + 1
                queue_lengths = {d: self._lanes[d].count() for d in DIRECTIONS}
                # Khởi động chu kỳ mới trên controller
                self._controller.start_next_cycle(
                    queue_lengths,
                    cycle_no=next_cycle_index,
                    started_at=self._sim_time,
                    conflict_clear=conflict_clear,
                )
                self._cycle_index = next_cycle_index

        # Cập nhật đồng hồ xanh cho các làn nếu vừa chuyển đoạn
        if self._controller.current_segment_code != prev_segment:
            self._update_lane_green_clocks()

        return self.snapshot()

    def run_ticks(self, n: int) -> SimulationSnapshot:
        """Chạy liên tiếp n ticks."""
        if n <= 0:
            raise ValueError("n phải > 0.")
        last_snap = self.snapshot()
        for _ in range(n):
            if self._session_state != "RUNNING":
                break
            last_snap = self.tick()
        return last_snap

    def snapshot(self) -> SimulationSnapshot:
        """Tạo SimulationSnapshot chỉ đọc tại trạng thái hiện tại."""
        geometry_snap = self._geometry.to_snapshot()
        signal_snap = self._controller.to_signal_snapshot()

        queue_lengths = {d: self._lanes[d].count() for d in DIRECTIONS}
        active_count = len(self._movement.active_crossing)

        metrics_snap = MetricsSnapshot(
            queue_lengths=queue_lengths,
            initial_total=self._initial_total,
            total_arrivals=self._total_arrivals,
            crossed_stop_total=self._crossed_stop_total,
            exited_world_total=self._exited_world_total,
            active_crossing_count=active_count,
            clearance_hold_s=float(self._controller.clearance_hold_s),
        )

        # Chuyển đổi danh sách xe thành VehicleSnapshot (không chứa xe EXITED)
        vehicle_snaps: list[VehicleSnapshot] = []

        # Các xe trong Queue (N, S, E, W)
        for direction in DIRECTIONS:
            for v in self._lanes[direction].get_vehicles():
                x, y = self._geometry.lane_to_xy(v.origin, v.s_front_m)
                state = "STOPPED" if v.speed_mps == 0 else "APPROACHING"
                vehicle_snaps.append(
                    VehicleSnapshot(
                        vehicle_id=v.vehicle_id,
                        origin=v.origin,
                        x=x,
                        y=y,
                        speed_mps=v.speed_mps,
                        motion_state=state,
                        s_front_m=v.s_front_m,
                        length_m=v.length_m,
                    )
                )

        # Các xe trong active_crossing
        for v in self._movement.active_crossing:
            x, y = self._geometry.lane_to_xy(v.origin, v.s_front_m)
            vehicle_snaps.append(
                VehicleSnapshot(
                    vehicle_id=v.vehicle_id,
                    origin=v.origin,
                    x=x,
                    y=y,
                    speed_mps=v.speed_mps,
                    motion_state="CROSSING",
                    s_front_m=v.s_front_m,
                    length_m=v.length_m,
                )
            )

        return SimulationSnapshot(
            sim_time=self._sim_time,
            cycle_index=self._cycle_index,
            session_state=self._session_state,
            geometry=geometry_snap,
            signals=signal_snap,
            metrics=metrics_snap,
            vehicles=tuple(vehicle_snaps),
        )
