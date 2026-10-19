"""Movement theo substep; mỗi xe tiến một lần và crossing giữ đúng FIFO."""

from collections.abc import Mapping
from types import MappingProxyType
from typing import Any

from src.core.geometry import Geometry
from src.models.config import Config, direction as require_direction, integer
from src.models.lane import Lane
from src.models.snapshot import DIRECTIONS
from src.models.vehicle import Vehicle, STOPPED_SPEED_MPS


class MovementEngine:
    def __init__(self, config: Config, lanes: Mapping[str, Lane], geometry: Geometry | None = None):
        self._config = config
        self._motion_cfg = config.motion_2d
        self._lanes = lanes
        self._geometry = geometry or Geometry.for_motion(self._motion_cfg)
        if self._geometry.vehicle_width_m is None:
            raise ValueError('Movement yêu cầu Geometry có bề rộng vật lý của xe.')
        self._active_crossing: dict[str, Vehicle] = {}
        self._exited_vehicles: list[Vehicle] = []
        self._vehicle_counter = 0
        self._known_ids = {v.vehicle_id for lane in lanes.values() for v in lane.get_vehicles()}
        self._initial_ids = self._known_ids.copy()
        self._exited_ids: set[str] = set()
        self._min_gap_violations = 0
        self.assert_physical_invariants()

    @property
    def active_crossing(self) -> Mapping[str, Vehicle]:
        """Dict theo ID theo thiết kế; chỉ Core được sửa ownership."""
        return MappingProxyType(self._active_crossing)

    @property
    def exited_vehicles(self) -> tuple[Vehicle, ...]:
        return tuple(self._exited_vehicles)

    @property
    def min_gap_violations(self) -> int:
        return self._min_gap_violations

    @property
    def observed_min_gap_m(self) -> float | None:
        """Smallest current same-lane gap; None when there is no pair to measure."""
        gaps = []
        for direction in DIRECTIONS:
            cars = self._cars(direction)
            gaps.extend(a.s_front_m - a.length_m - b.s_front_m
                        for a, b in zip(cars, cars[1:]))
        return min(gaps) if gaps else None

    def _cars(self, direction):
        active = sorted((v for v in self._active_crossing.values() if v.origin == direction),
                        key=lambda v: v.s_front_m, reverse=True)
        return active + list(self._lanes[direction].get_vehicles())

    def _enqueue(self, direction, arrival_t, position, *, initial=False):
        self._vehicle_counter += 1
        vehicle = Vehicle(
            vehicle_id=f'V-{direction}-{self._vehicle_counter:04d}',
            origin=direction, arrival_t=arrival_t, s_front_m=position,
            speed_mps=0, length_m=self._motion_cfg.vehicle_length_m,
        )
        if vehicle.vehicle_id in self._known_ids:
            raise ValueError('vehicle_id đã tồn tại trong phiên.')
        self._lanes[direction].enqueue(vehicle)
        self._known_ids.add(vehicle.vehicle_id)
        if initial:
            self._initial_ids.add(vehicle.vehicle_id)
        self.assert_physical_invariants()
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
            self._enqueue(direction, 0, position, initial=True)

    def spawn_and_enqueue(self, direction: str, arrival_t: float) -> Vehicle:
        require_direction(direction)
        position = min(-self._motion_cfg.approach_visible_m, -self._motion_cfg.stop_margin_m)
        cars = self._cars(direction)
        if cars:
            tail = cars[-1]
            position = min(position, tail.s_front_m - tail.length_m - self._motion_cfg.min_gap_m)
        return self._enqueue(direction, arrival_t, position)

    def advance_substep(self, t: float, dt: float, controller: Any) -> tuple[Vehicle, ...]:
        self.assert_physical_invariants()
        crossed = []
        for direction in DIRECTIONS:
            lane = self._lanes[direction]
            # Chụp danh sách đầu bước: xe mới crossing không xuất hiện ở vòng thứ hai.
            cars = self._cars(direction)
            leader = None
            for vehicle in cars:
                already_crossed = vehicle.crossed_stop_t is not None
                age_ready = (vehicle.vehicle_id in self._initial_ids
                             or t + dt >= vehicle.arrival_t + 1 - 1e-9)
                can_cross = already_crossed or (
                    vehicle is lane.peek() and age_ready
                    and controller is not None
                    and controller.is_green_for(direction)
                    and lane.is_cross_eligible(t)
                )
                self._update_vehicle_motion(vehicle, dt, leader, can_cross)
                if not already_crossed and can_cross and vehicle.s_front_m >= 0:
                    vehicle.mark_crossed(t + dt)
                    lane.pop_crossed()
                    self._active_crossing[vehicle.vehicle_id] = vehicle
                    crossed.append(vehicle)
                leader = vehicle

        for vehicle_id, vehicle in tuple(self._active_crossing.items()):
            if self._geometry.outside_world(vehicle.origin, vehicle.s_front_m, vehicle.length_m):
                vehicle.mark_exited(t + dt)
                self._exited_vehicles.append(vehicle)
                self._exited_ids.add(vehicle_id)
                del self._active_crossing[vehicle_id]
        self.assert_physical_invariants()
        return tuple(crossed)

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
        if speed <= STOPPED_SPEED_MPS + 1e-9 and vehicle.crossed_stop_t is None:
            vehicle.add_stopped_delay(dt)

    @property
    def conflict_occupancy_count(self) -> int:
        return sum(self._geometry.occupies_conflict(v.origin, v.s_front_m, v.length_m)
                   for v in self._active_crossing.values())

    def is_conflict_clear(self) -> bool:
        return self.conflict_occupancy_count == 0

    def check_gap_invariants(self) -> None:
        minimum = self._motion_cfg.min_gap_m - 1e-6
        for direction in DIRECTIONS:
            cars = self._cars(direction)
            for leader, follower in zip(cars, cars[1:]):
                gap = leader.s_front_m - leader.length_m - follower.s_front_m
                if gap < minimum:
                    self._min_gap_violations += 1
                    raise AssertionError(f'Vi phạm min_gap hướng {direction}: {gap} < {minimum}')

    def assert_physical_invariants(self) -> None:
        exited_ids = [v.vehicle_id for v in self._exited_vehicles]
        if (len(exited_ids) != len(set(exited_ids)) or set(exited_ids) != self._exited_ids
                or any(v.crossed_stop_t is None or v.exited_world_t is None for v in self._exited_vehicles)):
            raise AssertionError('Ownership exited không hợp lệ.')
        queued = [v for lane in self._lanes.values() for v in lane.get_vehicles()]
        ids = [v.vehicle_id for v in queued] + list(self._active_crossing)
        if (len(ids) != len(set(ids)) or set(ids) & self._exited_ids
                or set(ids) | self._exited_ids != self._known_ids):
            raise AssertionError('Vehicle phải thuộc đúng một kho Queue/active/exited; không mất hoặc trùng ID.')
        for lane in self._lanes.values():
            if any(v.origin != lane.direction or v.crossed_stop_t is not None for v in lane.get_vehicles()):
                raise AssertionError('Queue chứa xe sai hướng hoặc đã crossing.')
        if any(key != v.vehicle_id or v.crossed_stop_t is None or v.exited_world_t is not None
               for key, v in self._active_crossing.items()):
            raise AssertionError('Ownership active_crossing không hợp lệ.')
        self.check_gap_invariants()
