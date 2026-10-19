"""Điều phối Core: chu kỳ hoặc horizon, replay arrivals, invariants và thống kê."""

import random

from src.core.algorithms import poisson_sample
from src.core.arrivals import ArrivalTape
from src.core.controller import TrafficLightController
from src.core.geometry import Geometry
from src.core.movement import MovementEngine
from src.core.statistics import SimulationStats
from src.core.reporting import DashboardData
from src.models.config import Config, integer
from src.models.lane import Lane
from src.models.vehicle import STOPPED_SPEED_MPS
from src.models.snapshot import DIRECTIONS, MetricsSnapshot, SessionState, SimulationSnapshot, VehicleSnapshot


class SimulationEngine:
    def __init__(self, config: Config, *, policy: str = 'adaptive',
                 arrival_tape: ArrivalTape | None = None, horizon_s: int | None = None) -> None:
        if not isinstance(config, Config):
            raise TypeError('config phải là Config.')
        config.validate()
        if horizon_s is not None:
            integer('horizon_s', horizon_s, 1)
        if arrival_tape is not None:
            if not isinstance(arrival_tape, ArrivalTape):
                raise TypeError('arrival_tape phải là ArrivalTape.')
            if horizon_s is None or len(arrival_tape.rows) < horizon_s:
                raise ValueError('Replay yêu cầu horizon_s và đủ hàng arrivals.')
        self._policy = policy
        self._arrival_tape = arrival_tape
        self._horizon_s = horizon_s
        self._error_message = None
        self._config = Config.from_dict(config.to_dict())
        self._sim_time = 0
        self._cycle_index = 1
        self._session_state: SessionState = 'PAUSED'
        self._started = False
        self._rng = random.Random(self._config.seed)
        self._geometry = Geometry.for_motion(self._config.motion_2d)
        self._lanes = {d: Lane(d) for d in DIRECTIONS}
        self._controller = TrafficLightController(self._config, policy=policy)
        self._movement = MovementEngine(self._config, self._lanes, self._geometry)
        for direction in DIRECTIONS:
            self._movement.initialize_queue(direction, self._config.initial_queue[direction])
        self._initial_total = sum(self._config.initial_queue.values())
        self._stats = SimulationStats(self._initial_total)
        self._activate_cycle(self._queue_lengths(), 1, conflict_clear=True)
        self._update_lane_green_clocks()

    @property
    def policy(self) -> str:
        return self._policy

    @property
    def error_message(self) -> str | None:
        return self._error_message

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
    def has_started(self) -> bool:
        return self._started

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
        self.__init__(self._config, policy=self._policy, arrival_tape=self._arrival_tape, horizon_s=self._horizon_s)

    def tick(self) -> SimulationSnapshot:
        """Tick tự động chỉ chạy khi RUNNING; Step sử dụng run_ticks khi PAUSED."""
        if self._session_state != 'RUNNING':
            raise RuntimeError('Chỉ tick khi RUNNING.')
        return self._advance_tick()

    def _advance_tick(self) -> SimulationSnapshot:
        try:
            return self._perform_tick()
        except (AssertionError, ValueError, RuntimeError) as error:
            self._error_message = str(error)
            self._controller.fail_safe()
            self._session_state = 'ERROR'
            raise

    def _perform_tick(self) -> SimulationSnapshot:
        t = self._sim_time
        dt = self._config.motion_2d.dt_s
        replay_row = self._arrival_tape.at(t) if self._arrival_tape is not None else None
        for index, direction in enumerate(DIRECTIONS):
            count = (replay_row[index] if replay_row is not None else
                     poisson_sample(self._config.rates_per_min[direction] / 60, self._rng))
            for _ in range(count):
                self._movement.spawn_and_enqueue(direction, arrival_t=t)
            self._stats.record_arrival(direction, count)
        for step in range(round(1 / dt)):
            crossed = self._movement.advance_substep(t=t + step * dt, dt=dt, controller=self._controller)
            for vehicle in crossed:
                self._stats.record_departure(vehicle)
            self._metrics_snapshot()  # Hai đẳng thức bảo toàn sau mỗi substep.
        conflict_clear = self._movement.is_conflict_clear()
        previous_segment = self._controller.current_segment_code
        self._controller.tick(conflict_clear=conflict_clear)
        self._sim_time += 1
        self._stats.capture_tick(self._sim_time, self._metrics_snapshot())
        if self._controller.in_error:
            self._session_state = 'ERROR'
            self._error_message = 'Clearance hold vượt giới hạn.'
        elif self._controller.cycle_complete:
            queues = self._queue_lengths()
            # Chốt chu kỳ cũ trước khi Controller tính lại lịch từ Queue mới.
            self._stats.close_cycle(self._sim_time, queues)
            if self._horizon_s is not None and self._sim_time >= self._horizon_s:
                self._session_state = 'STOPPED'
            elif self._horizon_s is None and self._cycle_index >= self._config.cycles_to_run:
                self._session_state = 'COMPLETED'
            else:
                try:
                    self._activate_cycle(queues, self._cycle_index + 1, conflict_clear=conflict_clear)
                except (RuntimeError, TypeError, ValueError) as error:
                    # Reporting may fail after Controller activation: retain the original error.
                    self._controller.fail_safe()
                    self._session_state = 'ERROR'
                    self._error_message = str(error)
        if (self._session_state != 'ERROR' and self._horizon_s is not None
                and self._sim_time >= self._horizon_s):
            self._session_state = 'STOPPED'
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

    def run_until_cycle_end(self) -> SimulationSnapshot:
        """Step a started PAUSED session to the real boundary, hold or ERROR included."""
        if not self._started or self._session_state != 'PAUSED':
            raise RuntimeError('Chạy hết chu kỳ yêu cầu phiên đã Start và đang PAUSED.')
        closed = len(self._stats.cycles)
        while self._session_state == 'PAUSED' and len(self._stats.cycles) == closed:
            self._advance_tick()
        return self.snapshot()

    def cycle_metrics(self):
        return self._stats.cycle_metrics(self._sim_time, self._queue_lengths())

    def dashboard_data(self) -> DashboardData:
        return DashboardData(
            snapshot=self.snapshot(), current_green=self._stats.current_green,
            previous_green=self._stats.previous_green,
            queue_series=tuple((tick.sim_time, sum(tick.metrics.queue_lengths.values()))
                               for tick in self._stats.ticks),
            cycle_metrics=self.cycle_metrics(),
            conflict_occupancy_count=self._movement.conflict_occupancy_count,
            min_gap_config_m=self._config.motion_2d.min_gap_m,
            observed_min_gap_m=self._movement.observed_min_gap_m,
            summary=self.summary() if self._session_state in ('STOPPED', 'COMPLETED', 'ERROR') else None,
        )

    def summary(self) -> dict:
        return dict(self._stats.summary(), policy=self._policy, config_id=self._config.id,
                    seed=self._config.seed, status=self._session_state,
                    min_gap_violations=self._movement.min_gap_violations,
                    error_message=self._error_message)

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
                vehicles.append(self._vehicle_snapshot(vehicle, 'STOPPED' if vehicle.speed_mps <= STOPPED_SPEED_MPS + 1e-9 else 'APPROACHING'))
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
