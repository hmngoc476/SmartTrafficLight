"""MovementEngine mô phỏng chuyển động 2D với substep dt_s (mặc định 0.2s).

Quy tắc:
- Xe trong Queue (APPROACHING / STOPPED): di chuyển về phía vạch dừng (s <= -stop_margin_m).
- Khi có GREEN, đủ startup_delay và headway (lane.is_cross_eligible(t)), xe đầu Queue được phép crossing.
- CrossingEvent: xe đạt vạch dừng (s=0), được mark_crossed(t) và pop_crossed() khỏi Lane chuyển vào active_crossing.
- Xe trong active_crossing (CROSSING): tiếp tục di chuyển qua giao lộ kể cả khi đèn chuyển VÀNG hoặc ĐỎ.
- Giữ khoảng cách tối thiểu min_gap giữa các xe cùng làn (tính cả xe phía trước đang ở active_crossing).
- ExitedEvent: khi xe đi qua khỏi viewport (s_front_m - length_m > exit_threshold), xe được mark_exited(t)
  và chuyển khỏi active_crossing.
- is_conflict_clear(): kiểm tra xem còn xe nào chiếm vùng xung đột (intersection) hay không.
"""

from collections.abc import Mapping
from typing import Any

from src.core.geometry import Geometry
from src.models.config import Config, Motion2DConfig
from src.models.lane import Lane
from src.models.snapshot import DIRECTIONS, Direction
from src.models.vehicle import MotionState, Vehicle


class MovementEngine:
    """Xử lý vật lý di chuyển, spawn xe, crossing, active crossing và kiểm tra clearance."""

    def __init__(self, config: Config, lanes: Mapping[str, Lane], geometry: Geometry | None = None) -> None:
        self._config = config
        self._motion_cfg: Motion2DConfig = config.motion_2d
        self._lanes = lanes
        self._geometry = geometry or Geometry(
            intersection_width_m=self._motion_cfg.intersection_width_m,
            approach_visible_m=self._motion_cfg.approach_visible_m,
            vehicle_length_m=self._motion_cfg.vehicle_length_m,
            min_gap_m=self._motion_cfg.min_gap_m,
            stop_margin_m=self._motion_cfg.stop_margin_m,
        )

        # active_crossing: danh sách các xe đã crossing nhưng chưa exited khỏi thế giới
        self._active_crossing: list[Vehicle] = []
        # xe đã exited
        self._exited_vehicles: list[Vehicle] = []
        self._vehicle_counter: int = 0

    @property
    def active_crossing(self) -> list[Vehicle]:
        return self._active_crossing

    @property
    def exited_vehicles(self) -> list[Vehicle]:
        return self._exited_vehicles

    def spawn_and_enqueue(self, direction: str, arrival_t: float) -> Vehicle:
        """Tạo xe mới và thêm vào cuối hàng đợi Lane tương ứng."""
        self._vehicle_counter += 1
        vehicle_id = f"V-{direction}-{self._vehicle_counter:04d}"
        lane = self._lanes[direction]

        # Xác định vị trí spawn ban đầu cho xe mới
        # Nếu lane có xe, xe mới phải ở phía sau đuôi xe cuối cùng ít nhất min_gap
        # Nếu lane rỗng, spawn ở vị trí nhìn thấy (ví dụ -approach_visible_m hoặc -stop_margin_m nếu có xe ban đầu)
        min_gap = self._motion_cfg.min_gap_m
        length = self._motion_cfg.vehicle_length_m
        default_spawn_s = -(self._motion_cfg.approach_visible_m)

        vehicles_in_lane = lane.get_vehicles()
        if vehicles_in_lane:
            last_vehicle = vehicles_in_lane[-1]
            last_rear = last_vehicle.s_front_m - last_vehicle.length_m
            spawn_s = min(default_spawn_s, last_rear - min_gap)
        else:
            spawn_s = default_spawn_s

        vehicle = Vehicle(
            vehicle_id=vehicle_id,
            origin=direction,
            arrival_t=arrival_t,
            s_front_m=spawn_s,
            speed_mps=0.0,
            length_m=length,
        )
        lane.enqueue(vehicle)
        return vehicle

    def advance_substep(self, t: float, dt: float, controller: Any) -> None:
        """Cập nhật chuyển động 1 substep dt (ví dụ dt = 0.2s)."""
        # Cập nhật chuyển động cho từng làn (N, S, E, W)
        for direction in DIRECTIONS:
            lane = self._lanes[direction]
            is_green = controller.is_green_for(direction) if controller else False
            is_eligible = lane.is_cross_eligible(t)

            # Lấy xe active_crossing của hướng này (để làm leader cho xe đầu Queue)
            active_leaders = [v for v in self._active_crossing if v.origin == direction]
            active_leader = active_leaders[-1] if active_leaders else None

            # 1. Cập nhật các xe trong Queue
            queue_vehicles = list(lane.get_vehicles())
            leader = active_leader

            for idx, vehicle in enumerate(queue_vehicles):
                is_front = (idx == 0)
                # Xe đầu tiên có được phép vượt qua vạch dừng không?
                can_cross = is_front and is_green and is_eligible

                self._update_vehicle_motion(
                    vehicle=vehicle,
                    dt=dt,
                    leader=leader,
                    can_cross=can_cross,
                )
                leader = vehicle

                # Nếu xe đầu tiên đã chạm vạch dừng (s_front_m >= 0) và được phép crossing
                if is_front and can_cross and vehicle.s_front_m >= 0.0:
                    # Đảm bảo vị trí đúng tại hoặc qua vạch
                    if vehicle.crossed_stop_t is None:
                        vehicle.mark_crossed(t)
                        lane.pop_crossed()
                        self._active_crossing.append(vehicle)

        # 2. Cập nhật các xe đang trong active_crossing
        # Xe active_crossing không bị chặn bởi đèn đỏ nữa, chỉ bị chặn bởi leader phía trước
        for direction in DIRECTIONS:
            active_dir = [v for v in self._active_crossing if v.origin == direction]
            leader = None
            for vehicle in active_dir:
                self._update_vehicle_motion(
                    vehicle=vehicle,
                    dt=dt,
                    leader=leader,
                    can_cross=True,
                )
                leader = vehicle

        # 3. Kiểm tra xe exited khỏi thế giới
        # Viewport giới hạn: intersection_width / 2 + approach_visible_m
        exit_limit = self._geometry.intersection_width_m / 2.0 + self._geometry.approach_visible_m
        remaining_active = []
        for vehicle in self._active_crossing:
            # Đuôi xe: s_front_m - vehicle.length_m
            # Xe thoát khỏi thế giới khi đuôi xe vượt quá exit_limit
            if vehicle.s_front_m - vehicle.length_m > exit_limit:
                vehicle.mark_exited(t)
                self._exited_vehicles.append(vehicle)
            else:
                remaining_active.append(vehicle)
        self._active_crossing = remaining_active

    def _update_vehicle_motion(
        self,
        vehicle: Vehicle,
        dt: float,
        leader: Vehicle | None,
        can_cross: bool,
    ) -> None:
        """Tính toán gia tốc/vận tốc và cập nhật vị trí s_front_m của xe."""
        max_speed = self._motion_cfg.max_speed_mps
        accel = self._motion_cfg.accel_mps2
        min_gap = self._motion_cfg.min_gap_m
        stop_margin = self._motion_cfg.stop_margin_m

        current_s = vehicle.s_front_m
        current_v = vehicle.speed_mps

        # Giới hạn vị trí tối đa xe có thể đi tới trong substep này
        # 1. Giới hạn bởi xe đi trước (leader)
        limit_s = float("inf")
        if leader is not None:
            leader_rear = leader.s_front_m - leader.length_m
            limit_s = min(limit_s, leader_rear - min_gap)

        # 2. Giới hạn bởi vạch dừng nếu chưa được phép crossing
        if not can_cross and vehicle.crossed_stop_t is None:
            # Dừng trước vạch dừng một khoảng stop_margin
            limit_s = min(limit_s, -stop_margin)

        # Tăng tốc tối đa nếu có khoảng trống
        target_v = max_speed
        # Khoảng cách còn lại tới chướng ngại vật
        dist_to_limit = limit_s - current_s

        if dist_to_limit <= 1e-4:
            # Đã chạm ngưỡng chặn
            new_v = 0.0
            new_s = current_s
            if current_v == 0.0 and vehicle.crossed_stop_t is None:
                vehicle.add_stopped_delay(dt)
        else:
            # Có thể tăng tốc hoặc cần giảm tốc để không vượt quá limit_s
            # Giản lược động học: v_desired = min(max_speed, current_v + accel * dt)
            # Không vượt quá khoảng cách dist_to_limit / dt
            max_v_by_dist = dist_to_limit / dt
            new_v = min(target_v, current_v + accel * dt, max_v_by_dist)
            new_v = max(0.0, new_v)
            new_s = current_s + new_v * dt

            # Đảm bảo không vượt limit_s do sai số floating point
            new_s = min(new_s, limit_s)

            if new_s < current_s:
                new_s = current_s

            if new_v == 0.0 and vehicle.crossed_stop_t is None:
                vehicle.add_stopped_delay(dt)

        vehicle.update_motion(new_s, new_v)

    def is_conflict_clear(self) -> bool:
        """Kiểm tra vùng xung đột (intersection) có trống xe hay không.

        Vùng xung đột là [-half_width, half_width] dọc theo cả trục X và Y.
        Xe chiếm vùng xung đột nếu đuôi xe chưa ra khỏi vùng và đầu xe đã vào vùng:
        - Vùng giao lộ: s bắt đầu từ 0 (vạch dừng tại -half_width đối với hướng vào) đến intersection_width_m.
        Cụ thể, đầu xe s_front_m >= 0 và đuôi xe s_front_m - length_m <= intersection_width_m.
        """
        inter_width = self._geometry.intersection_width_m

        for vehicle in self._active_crossing:
            # Đầu xe s_front_m, đuôi xe s_front_m - length_m
            s_front = vehicle.s_front_m
            s_rear = vehicle.s_front_m - vehicle.length_m
            # Nếu xe có phần thân nằm trong khoảng [0, inter_width]
            if s_front >= 0.0 and s_rear <= inter_width:
                return False

        return True

    def check_gap_invariants(self) -> None:
        """Kiểm tra bất biến khoảng cách an toàn min_gap_m giữa các xe cùng làn."""
        min_gap = self._motion_cfg.min_gap_m - 1e-6
        for direction in DIRECTIONS:
            lane = self._lanes[direction]
            active_vehicles = [v for v in self._active_crossing if v.origin == direction]
            all_vehicles = active_vehicles + list(lane.get_vehicles())

            for i in range(len(all_vehicles) - 1):
                leader = all_vehicles[i]
                follower = all_vehicles[i + 1]
                gap = (leader.s_front_m - leader.length_m) - follower.s_front_m
                if gap < min_gap:
                    raise AssertionError(
                        f"Vi phạm min_gap tại hướng {direction}: gap={gap:.3f} < {min_gap:.3f} giữa {leader.vehicle_id} và {follower.vehicle_id}"
                    )
