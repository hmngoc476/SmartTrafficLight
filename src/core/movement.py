"""Movement theo substep; mỗi xe tiến một lần và crossing giữ đúng FIFO."""

from collections.abc import Mapping
from types import MappingProxyType
from typing import Any

from src.core.geometry import Geometry
from src.models.config import Config, direction as require_direction, integer
from src.models.lane import Lane
from src.models.snapshot import DIRECTIONS
from src.models.vehicle import Vehicle


class MovementEngine:
    def __init__(self, config: Config, lanes: Mapping[str, Lane], geometry: Geometry | None = None):
        self._config = config
        self._motion_cfg = config.motion_2d
        self._lanes = lanes
        self._geometry = geometry or Geometry(
            intersection_width_m=self._motion_cfg.intersection_width_m,
            approach_visible_m=self._motion_cfg.approach_visible_m,
            vehicle_length_m=self._motion_cfg.vehicle_length_m,
            min_gap_m=self._motion_cfg.min_gap_m,
            stop_margin_m=self._motion_cfg.stop_margin_m,
        )
        self._active_crossing: dict[str, Vehicle] = {}
        self._exited_vehicles: list[Vehicle] = []
        self._vehicle_counter = 0

    @property
    def active_crossing(self) -> Mapping[str, Vehicle]:
        """Dict theo ID theo thiết kế; chỉ Core được sửa ownership."""
        return MappingProxyType(self._active_crossing)

    @property
    def exited_vehicles(self) -> tuple[Vehicle, ...]:
        return tuple(self._exited_vehicles)

    def _enqueue(self, direction, arrival_t, position):
        self._vehicle_counter += 1
        vehicle = Vehicle(
            vehicle_id=f'V-{direction}-{self._vehicle_counter:04d}',
            origin=direction, arrival_t=arrival_t, s_front_m=position,
            speed_mps=0, length_m=self._motion_cfg.vehicle_length_m,
        )
        self._lanes[direction].enqueue(vehicle)
        return vehicle

    def initialize_queue(self, direction: str, count: int) -> None:
        """Xe tồn ban đầu đứng sát vạch; tách khỏi spawn xe mới từ Poisson."""
        require_direction(direction)
        integer('count', count, 0, 100)
        if self._lanes[direction].count():
            raise ValueError('Chỉ khởi tạo một Lane đang rỗng.')
        spacing = self._motion_cfg.vehicle_length_m + self._motion_cfg.min_gap_m
        for index in range(count):
            position = -self._motion_cfg.stop_margin_m - index * spacing
            self._enqueue(direction, 0, position)

    def spawn_and_enqueue(self, direction: str, arrival_t: float) -> Vehicle:
        require_direction(direction)
        position = -self._motion_cfg.approach_visible_m
        queued = self._lanes[direction].get_vehicles()
        if queued:
            tail = queued[-1]
            position = min(position, tail.s_front_m - tail.length_m - self._motion_cfg.min_gap_m)
        return self._enqueue(direction, arrival_t, position)

    def advance_substep(self, t: float, dt: float, controller: Any) -> None:
        for direction in DIRECTIONS:
            lane = self._lanes[direction]
            # Chụp danh sách đầu bước: xe mới crossing không xuất hiện ở vòng thứ hai.
            active = [v for v in self._active_crossing.values() if v.origin == direction]
            cars = active + list(lane.get_vehicles())
            leader = None
            for vehicle in cars:
                already_crossed = vehicle.crossed_stop_t is not None
                can_cross = already_crossed or (
                    vehicle is lane.peek()
                    and controller is not None
                    and controller.is_green_for(direction)
                    and lane.is_cross_eligible(t)
                )
                self._update_vehicle_motion(vehicle, dt, leader, can_cross)
                if not already_crossed and can_cross and vehicle.s_front_m >= 0:
                    vehicle.mark_crossed(t + dt)
                    lane.pop_crossed()
                    self._active_crossing[vehicle.vehicle_id] = vehicle
                leader = vehicle

        exit_limit = self._geometry.intersection_width_m / 2 + self._geometry.approach_visible_m
        for vehicle_id, vehicle in tuple(self._active_crossing.items()):
            if vehicle.s_front_m - vehicle.length_m > exit_limit:
                vehicle.mark_exited(t + dt)
                self._exited_vehicles.append(vehicle)
                del self._active_crossing[vehicle_id]

    def _update_vehicle_motion(self, vehicle, dt, leader, can_cross):
        limit = float('inf')
        if leader is not None:
            limit = leader.s_front_m - leader.length_m - self._motion_cfg.min_gap_m
        if not can_cross and vehicle.crossed_stop_t is None:
            limit = min(limit, -self._motion_cfg.stop_margin_m)
        old_position = vehicle.s_front_m
        desired_speed = min(self._motion_cfg.max_speed_mps,
                            vehicle.speed_mps + self._motion_cfg.accel_mps2 * dt)
        position = max(old_position, min(old_position + desired_speed * dt, limit))
        speed = max(0, (position - old_position) / dt)
        vehicle.update_motion(position, speed)
        if speed == 0 and vehicle.crossed_stop_t is None:
            vehicle.add_stopped_delay(dt)

    def is_conflict_clear(self) -> bool:
        """Giữ behavior occupancy hiện có; nghiệm thu vật lý thuộc task 18/10."""
        width = self._geometry.intersection_width_m
        return not any(
            v.s_front_m >= 0 and v.s_front_m - v.length_m <= width
            for v in self._active_crossing.values()
        )

    def check_gap_invariants(self) -> None:
        minimum = self._motion_cfg.min_gap_m - 1e-6
        for direction in DIRECTIONS:
            cars = [v for v in self._active_crossing.values() if v.origin == direction]
            cars += list(self._lanes[direction].get_vehicles())
            for leader, follower in zip(cars, cars[1:]):
                gap = leader.s_front_m - leader.length_m - follower.s_front_m
                if gap < minimum:
                    raise AssertionError(f'Vi phạm min_gap hướng {direction}: {gap} < {minimum}')
