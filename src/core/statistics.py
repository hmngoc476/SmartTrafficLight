"""Counters và thống kê tick/chu kỳ/phiên ngày 19; không chứa UI hoặc ghi file."""

from dataclasses import dataclass

from src.models.config import direction, integer
from src.models.snapshot import MetricsSnapshot
from src.models.vehicle import Vehicle


@dataclass(frozen=True, slots=True)
class CycleMetrics:
    cycle_index: int
    started_at_s: int
    ended_at_s: int
    q_ns_start: int
    q_ew_start: int
    green_ns_s: int
    green_ew_s: int
    arrivals_ns: int
    arrivals_ew: int
    departed_ns: int
    departed_ew: int
    q_ns_end: int
    q_ew_end: int

    avg_queue_cycle: float = 0.0
    clearance_hold_s: float = 0.0

    @property
    def actual_cycle_s(self) -> int:
        return self.ended_at_s - self.started_at_s


@dataclass(frozen=True, slots=True)
class TickMetrics:
    sim_time: int
    cycle_index: int
    metrics: MetricsSnapshot


class SimulationStats:
    def __init__(self, initial_total: int):
        integer('initial_total', initial_total, 0)
        self._initial_total = initial_total
        self._arrivals = dict.fromkeys('NSEW', 0)
        self._departures = dict.fromkeys('NSEW', 0)
        self._crossed_ids: set[str] = set()
        self._ticks: list[TickMetrics] = []
        self._cycles: list[CycleMetrics] = []
        self._open_cycle = None
        self._queue_sum = 0
        self._max_queue = initial_total
        self._wait_sum = 0.0
        self._stopped_sum = 0.0
        self._closed_hold = 0.0
        self._current_hold = 0.0

    @property
    def initial_total(self) -> int:
        return self._initial_total

    @property
    def arrivals_total(self) -> int:
        return sum(self._arrivals.values())

    @property
    def crossed_stop_total(self) -> int:
        return len(self._crossed_ids)

    @property
    def ticks(self) -> tuple[TickMetrics, ...]:
        return tuple(self._ticks)

    @property
    def cycles(self) -> tuple[CycleMetrics, ...]:
        return tuple(self._cycles)

    def record_arrival(self, origin: str, count: int = 1) -> None:
        direction(origin)
        integer('count', count, 0)
        self._arrivals[origin] += count

    def record_departure(self, vehicle: Vehicle) -> None:
        if vehicle.crossed_stop_t is None:
            raise ValueError('Chỉ ghi departure sau crossing.')
        if vehicle.vehicle_id not in self._crossed_ids:
            self._crossed_ids.add(vehicle.vehicle_id)
            self._departures[vehicle.origin] += 1
            self._wait_sum += vehicle.elapsed_to_stopline()
            self._stopped_sum += vehicle.stopped_delay_s

    def begin_cycle(self, cycle_index, started_at, queues, green_ns_s, green_ew_s) -> None:
        if self._open_cycle is not None:
            raise RuntimeError('Phải chốt chu kỳ trước khi bắt đầu chu kỳ mới.')
        self._open_cycle = dict(
            cycle_index=cycle_index, started_at_s=started_at,
            q_ns_start=queues['N'] + queues['S'], q_ew_start=queues['E'] + queues['W'],
            green_ns_s=green_ns_s, green_ew_s=green_ew_s,
            arrivals=self._arrivals.copy(), departures=self._departures.copy(),
            queue_sum=0, tick_count=0,
        )

    def capture_tick(self, sim_time: int, metrics: MetricsSnapshot) -> None:
        if self._open_cycle is None:
            raise RuntimeError('Chưa có chu kỳ để ghi tick.')
        if sim_time != (self._ticks[-1].sim_time if self._ticks else 0) + 1:
            raise ValueError('Mỗi giây mô phỏng phải được ghi đúng một tick.')
        if (metrics.initial_total != self.initial_total
                or metrics.total_arrivals != self.arrivals_total
                or metrics.crossed_stop_total != self.crossed_stop_total):
            raise ValueError('Counters của Engine và Statistics không khớp.')
        queue_total = sum(metrics.queue_lengths.values())
        self._queue_sum += queue_total
        self._max_queue = max(self._max_queue, queue_total)
        self._open_cycle['queue_sum'] += queue_total
        self._open_cycle['tick_count'] += 1
        self._current_hold = metrics.clearance_hold_s
        self._ticks.append(TickMetrics(sim_time, self._open_cycle['cycle_index'], metrics))

    def close_cycle(self, ended_at, queues) -> CycleMetrics:
        if self._open_cycle is None:
            raise RuntimeError('Chu kỳ đã chốt hoặc chưa bắt đầu.')
        opened = self._open_cycle
        # Các baseline thuộc chu kỳ vừa chạy, trước khi Controller nhận Queue mới.
        values = {key: value for key, value in opened.items() if key not in ('arrivals', 'departures', 'queue_sum', 'tick_count')}
        for axis, origins in [('ns', 'NS'), ('ew', 'EW')]:
            values['arrivals_' + axis] = sum(self._arrivals[d] - opened['arrivals'][d] for d in origins)
            values['departed_' + axis] = sum(self._departures[d] - opened['departures'][d] for d in origins)
            values['q_' + axis + '_end'] = sum(queues[d] for d in origins)
        record = CycleMetrics(**values, ended_at_s=ended_at,
                              avg_queue_cycle=opened['queue_sum'] / opened['tick_count'] if opened['tick_count'] else 0.0,
                              clearance_hold_s=self._current_hold)
        self._closed_hold += self._current_hold
        self._current_hold = 0.0
        self._cycles.append(record)
        self._open_cycle = None
        return record

    def summary(self) -> dict:
        latest = self._ticks[-1] if self._ticks else None
        crossed = self.crossed_stop_total
        seconds = latest.sim_time if latest else 0
        return dict(
            remaining_vehicles=sum(latest.metrics.queue_lengths.values()) if latest else self.initial_total,
            active_crossing_count=latest.metrics.active_crossing_count if latest else 0,
            departed_vehicles=crossed,
            avg_queue=self._queue_sum / seconds if seconds else None,
            max_queue=self._max_queue,
            avg_wait_departed_s=self._wait_sum / crossed if crossed else None,
            avg_stopped_delay_s=self._stopped_sum / crossed if crossed else None,
            avg_green_ns_s=sum(c.green_ns_s for c in self._cycles) / len(self._cycles) if self._cycles else None,
            avg_green_ew_s=sum(c.green_ew_s for c in self._cycles) / len(self._cycles) if self._cycles else None,
            throughput_per_min=crossed * 60 / seconds if seconds else None,
            clearance_hold_s=self._closed_hold + self._current_hold,
            initial_total=self.initial_total,
            total_arrivals=self.arrivals_total,
            crossed_stop_total=self.crossed_stop_total,
            exited_world_total=latest.metrics.exited_world_total if latest else 0,
            simulation_seconds=latest.sim_time if latest else 0,
            cycles_completed=len(self._cycles),
        )
