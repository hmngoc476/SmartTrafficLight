"""Điều phối phiên, tick 1s, Movement substep và thống kê đến task 17/10."""

import random

from src.core.algorithms import poisson_sample
from src.core.controller import TrafficLightController
from src.core.geometry import Geometry
from src.core.movement import MovementEngine
from src.core.statistics import SimulationStats
from src.models.config import Config, integer
from src.models.lane import Lane
from src.models.snapshot import DIRECTIONS, MetricsSnapshot, SessionState, SimulationSnapshot, VehicleSnapshot


class SimulationEngine:
    def __init__(self, config: Config) -> None:
        if not isinstance(config, Config):
            raise TypeError('config phải là Config.')
        config.validate()
        self._config = Config.from_dict(config.to_dict())
        self._sim_time = 0
        self._cycle_index = 1
        self._session_state: SessionState = 'PAUSED'
        self._started = False
        self._rng = random.Random(self._config.seed)
        self._geometry = Geometry(
            intersection_width_m=self._config.motion_2d.intersection_width_m,
            approach_visible_m=self._config.motion_2d.approach_visible_m,
            vehicle_length_m=self._config.motion_2d.vehicle_length_m,
            min_gap_m=self._config.motion_2d.min_gap_m,
            stop_margin_m=self._config.motion_2d.stop_margin_m,
        )
        self._lanes = {d: Lane(d) for d in DIRECTIONS}
        self._controller = TrafficLightController(self._config)
        self._movement = MovementEngine(self._config, self._lanes, self._geometry)
        for direction in DIRECTIONS:
            self._movement.initialize_queue(direction, self._config.initial_queue[direction])
        self._initial_total = sum(self._config.initial_queue.values())
        self._stats = SimulationStats(self._initial_total)
        self._activate_cycle(self._queue_lengths(), 1, conflict_clear=True)
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

    @property
    def stats(self) -> SimulationStats:
        return self._stats

    def _queue_lengths(self) -> dict[str, int]:
        return {d: self._lanes[d].count() for d in DIRECTIONS}

    def _activate_cycle(self, queues, cycle_index: int, *, conflict_clear: bool) -> None:
        self._controller.start_next_cycle(
            queues, cycle_no=cycle_index, started_at=self._sim_time, conflict_clear=conflict_clear,
        )
        self._cycle_index = cycle_index
        # Ngay sau activation đang ở đầu NS_GREEN; không gọi lại Adaptive để đọc plan.
        green_ns = self._controller.remaining_s
        self._stats.begin_cycle(cycle_index, self._sim_time, queues,
                                green_ns, self._config.green_budget_s - green_ns)

    def _update_lane_green_clocks(self) -> None:
        for direction, lane in self._lanes.items():
            if self._controller.is_green_for(direction):
                if lane.green_started_at is None:
                    lane.reset_green_clock(self._sim_time, self._config.startup_delay_s,
                                           self._config.headway_s)
            elif lane.green_started_at is not None:
                lane.reset_green_clock()

    def start(self) -> None:
        """Start chỉ kích hoạt phiên mới; phiên đã dừng cần Reset hoặc Engine mới."""
        if self._started or self._session_state != 'PAUSED':
            raise RuntimeError('Start yêu cầu phiên mới; dùng Resume hoặc Reset đúng trạng thái.')
        self._started = True
        self._session_state = 'RUNNING'

    def pause(self) -> None:
        if self._session_state != 'RUNNING':
            raise RuntimeError('Chỉ Pause khi RUNNING.')
        self._session_state = 'PAUSED'

    def resume(self) -> None:
        if not self._started or self._session_state != 'PAUSED':
            raise RuntimeError('Chỉ Resume một phiên đã Start và đang PAUSED.')
        self._session_state = 'RUNNING'

    def stop(self) -> None:
        if not self._started or self._session_state not in ('RUNNING', 'PAUSED'):
            raise RuntimeError('Chỉ Stop một phiên đang chạy hoặc tạm dừng.')
        self._session_state = 'STOPPED'

    def reset(self) -> None:
        self.__init__(self._config)

    def tick(self) -> SimulationSnapshot:
        """Tick tự động chỉ chạy khi RUNNING; Step sử dụng run_ticks khi PAUSED."""
        if self._session_state != 'RUNNING':
            raise RuntimeError('Chỉ tick khi RUNNING.')
        return self._advance_tick()

    def _advance_tick(self) -> SimulationSnapshot:
        t = self._sim_time
        dt = self._config.motion_2d.dt_s
        for direction in DIRECTIONS:
            count = poisson_sample(self._config.rates_per_min[direction] / 60, self._rng)
            for _ in range(count):
                self._movement.spawn_and_enqueue(direction, arrival_t=t)
            self._stats.record_arrival(direction, count)
        for step in range(round(1 / dt)):
            self._movement.advance_substep(t=t + step * dt, dt=dt, controller=self._controller)
        for vehicle in (*self._movement.active_crossing.values(), *self._movement.exited_vehicles):
            self._stats.record_departure(vehicle)
        conflict_clear = self._movement.is_conflict_clear()
        previous_segment = self._controller.current_segment_code
        self._controller.tick(conflict_clear=conflict_clear)
        self._sim_time += 1
        self._stats.capture_tick(self._sim_time, self._metrics_snapshot())
        if self._controller.in_error:
            self._session_state = 'ERROR'
        elif self._controller.cycle_complete:
            queues = self._queue_lengths()
            # Chốt chu kỳ cũ trước khi Controller tính lại lịch từ Queue mới.
            self._stats.close_cycle(self._sim_time, queues)
            if self._cycle_index >= self._config.cycles_to_run:
                self._session_state = 'COMPLETED'
            else:
                try:
                    self._activate_cycle(queues, self._cycle_index + 1, conflict_clear=conflict_clear)
                except (RuntimeError, TypeError, ValueError):
                    # Controller activation atomic; lỗi giữ terminal ALL_RED của chu kỳ cũ.
                    self._session_state = 'ERROR'
        if self._controller.current_segment_code != previous_segment:
            self._update_lane_green_clocks()
        return self.snapshot()

    def run_ticks(self, n: int) -> SimulationSnapshot:
        """RUNNING: chạy nhiều tick; PAUSED: Step rồi giữ PAUSED nếu chưa kết thúc."""
        integer('n', n, 1)
        if not self._started or self._session_state not in ('RUNNING', 'PAUSED'):
            raise RuntimeError('run_ticks yêu cầu phiên đã Start ở RUNNING hoặc PAUSED.')
        for _ in range(n):
            if self._session_state not in ('RUNNING', 'PAUSED'):
                break
            self._advance_tick()
        return self.snapshot()

    def _metrics_snapshot(self) -> MetricsSnapshot:
        return MetricsSnapshot(
            queue_lengths=self._queue_lengths(), initial_total=self._initial_total,
            total_arrivals=self._stats.arrivals_total,
            crossed_stop_total=self._stats.crossed_stop_total,
            exited_world_total=len(self._movement.exited_vehicles),
            active_crossing_count=len(self._movement.active_crossing),
            clearance_hold_s=self._controller.clearance_hold_s,
        )

    def snapshot(self) -> SimulationSnapshot:
        vehicles = []
        for direction in DIRECTIONS:
            for vehicle in self._lanes[direction].get_vehicles():
                vehicles.append(self._vehicle_snapshot(vehicle, 'STOPPED' if vehicle.speed_mps == 0 else 'APPROACHING'))
        for vehicle in self._movement.active_crossing.values():
            vehicles.append(self._vehicle_snapshot(vehicle, 'CROSSING'))
        return SimulationSnapshot(
            sim_time=self._sim_time, cycle_index=self._cycle_index,
            session_state=self._session_state, geometry=self._geometry.to_snapshot(),
            signals=self._controller.to_signal_snapshot(), metrics=self._metrics_snapshot(),
            vehicles=tuple(vehicles),
        )

    def _vehicle_snapshot(self, vehicle, state) -> VehicleSnapshot:
        x, y = self._geometry.lane_to_xy(vehicle.origin, vehicle.s_front_m)
        return VehicleSnapshot(
            vehicle_id=vehicle.vehicle_id, origin=vehicle.origin, x=x, y=y,
            speed_mps=vehicle.speed_mps, motion_state=state,
            s_front_m=vehicle.s_front_m, length_m=vehicle.length_m,
        )
