"""Hàng đợi FIFO của các xe chưa được lấy ra sau crossing."""
from src.models.deque import Deque
from src.models.config import direction as require_direction, number
from src.models.vehicle import Vehicle


class Lane:
    """Không điều khiển pha đèn; Controller chịu trách nhiệm xác nhận crossing."""
    def __init__(self, direction: str) -> None:
        require_direction(direction)
        self._direction = direction
        self._queue: Deque[Vehicle] = Deque()
        self._seen_ids: set[str] = set()
        self._green_started_at: float | None = None
        self._next_cross_eligible_at: float | None = None
        self._headway_s: float = 1.0
        self._last_arrival_t: float | None = None
        self._last_crossed_at: float | None = None

    @property
    def direction(self) -> str:
        return self._direction

    @property
    def green_started_at(self) -> float | None:
        return self._green_started_at

    @property
    def next_cross_eligible_at(self) -> float | None:
        return self._next_cross_eligible_at

    def enqueue(self, vehicle: Vehicle) -> None:
        """Thêm cuối bằng append; yêu cầu Core gửi xe theo thứ tự arrival_t."""
        if not isinstance(vehicle, Vehicle):
            raise TypeError('Lane chỉ nhận Vehicle.')
        if vehicle.origin != self.direction:
            raise ValueError('Hướng xe khác hướng Lane.')
        if vehicle.vehicle_id in self._seen_ids:
            raise ValueError('vehicle_id đã được sử dụng trong Lane này.')
        if vehicle.crossed_stop_t is not None:
            raise ValueError('Không thêm xe đã crossing vào Queue.')
        if self._last_arrival_t is not None and vehicle.arrival_t < self._last_arrival_t:
            raise ValueError('Xe phải được enqueue theo thứ tự thời gian xuất hiện.')
        self._queue.append(vehicle)
        self._seen_ids.add(vehicle.vehicle_id)
        self._last_arrival_t = vehicle.arrival_t

    def peek(self) -> Vehicle | None:
        """Xem đầu Queue không xóa; trả None khi rỗng."""
        return self._queue[0] if self._queue else None

    def pop_crossed(self) -> Vehicle | None:
        """Chỉ popleft xe đầu đã crossing; rỗng trả None, chưa crossing raise."""
        vehicle = self.peek()
        if vehicle is None:
            return None
        if vehicle.crossed_stop_t is None:
            raise ValueError('Xe đầu chưa crossing, không được lấy khỏi Queue.')
        next_time = None
        if self._next_cross_eligible_at is not None:
            next_time = max(self._next_cross_eligible_at,
                            vehicle.crossed_stop_t + self._headway_s)
            number('Thời điểm headway tiếp theo', next_time, low=0)
        self._queue.popleft()
        self._last_crossed_at = vehicle.crossed_stop_t
        self._next_cross_eligible_at = next_time
        return vehicle

    def count(self) -> int:
        """Số xe còn trong Queue, bao gồm xe đang tiến đến vạch."""
        return len(self._queue)

    def get_vehicles(self) -> tuple[Vehicle, ...]:
        """Bản sao tuple; caller không thể thêm/xóa phần tử Queue."""
        return tuple(self._queue)

    def reset_green_clock(self, started_at: float | None = None,
                          startup_delay_s: float = 0.0, headway_s: float = 1.0) -> None:
        """Xanh mới phải đủ startup và headway; None tắt clock, giữ lịch sử crossing."""
        number('startup_delay_s', startup_delay_s, low=0)
        number('headway_s', headway_s, low=1)
        eligible = None
        if started_at is not None:
            number('started_at', started_at, low=0)
            eligible = started_at + startup_delay_s
            if self._last_crossed_at is not None:
                eligible = max(eligible, self._last_crossed_at + headway_s)
            number('Thời điểm đủ startup delay/headway', eligible, low=0)
        self._green_started_at = started_at
        self._next_cross_eligible_at = eligible
        self._headway_s = headway_s

    def is_cross_eligible(self, t: float) -> bool:
        """Chỉ kiểm tra đồng hồ và Queue; không xác nhận quyền vượt tín hiệu."""
        number('Thời điểm xét crossing', t, low=0)
        return (self.peek() is not None and self._next_cross_eligible_at is not None
                and t >= self._next_cross_eligible_at)
