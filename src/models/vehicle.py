"""Phương tiện và các sự kiện do Core xác nhận."""
from dataclasses import asdict, dataclass, field
from enum import StrEnum
from typing import Protocol
from src.models.config import direction, number, text


class MotionState(StrEnum):
    APPROACHING = 'APPROACHING'
    STOPPED = 'STOPPED'
    CROSSING = 'CROSSING'
    EXITED = 'EXITED'


class GeometryProtocol(Protocol):
    """Geometry cần cung cấp phép đổi tọa độ này để tích hợp Models."""
    def lane_to_xy(self, origin: str, s_front_m: float) -> tuple[float, float]: ...


@dataclass(frozen=True, eq=False)
class Vehicle:
    """Các trường chỉ đọc; Core cập nhật qua public methods đã kiểm tra."""
    vehicle_id: str
    origin: str
    arrival_t: float = 0.0
    s_front_m: float = -100.0
    speed_mps: float = 0.0
    length_m: float = 4.5
    crossed_stop_t: float | None = field(default=None, init=False)
    exited_world_t: float | None = field(default=None, init=False)
    stopped_delay_s: float = field(default=0.0, init=False)
    motion_state: MotionState = field(default=MotionState.APPROACHING, init=False)

    def __post_init__(self) -> None:
        text('vehicle_id', self.vehicle_id)
        direction(self.origin)
        number('arrival_t', self.arrival_t, low=0)
        number('s_front_m', self.s_front_m)
        number('speed_mps', self.speed_mps, low=0)
        number('length_m', self.length_m, positive=True)
        if self.s_front_m > 0:
            raise ValueError('Xe mới phải ở trước hoặc tại vạch; Core ghi nhận crossing sau.')
        if self.speed_mps == 0:
            object.__setattr__(self, 'motion_state', MotionState.STOPPED)

    @property
    def status(self) -> str:
        """WAITING bao gồm cả xe đang tiến đến vạch; PASSED sau crossing."""
        return 'WAITING' if self.crossed_stop_t is None else 'PASSED'

    def update_motion(self, s_front_m: float, speed_mps: float) -> None:
        """Cập nhật chuyển động tiến; không tự xác nhận vượt vạch hoặc tín hiệu."""
        number('s_front_m', s_front_m)
        number('speed_mps', speed_mps, low=0)
        if self.exited_world_t is not None:
            raise ValueError('Xe đã rời khung không thể cập nhật chuyển động.')
        if s_front_m < self.s_front_m:
            raise ValueError('Vị trí xe không được di chuyển lùi.')
        state = (MotionState.CROSSING if self.crossed_stop_t is not None else
                 MotionState.STOPPED if speed_mps == 0 else MotionState.APPROACHING)
        object.__setattr__(self, 's_front_m', s_front_m)
        object.__setattr__(self, 'speed_mps', speed_mps)
        object.__setattr__(self, 'motion_state', state)

    def mark_crossed(self, t: float) -> None:
        """Core gọi đúng một lần khi đã kiểm tra tín hiệu và xe tới vạch."""
        number('Thời điểm vượt vạch', t, low=self.arrival_t)
        if self.crossed_stop_t is not None:
            raise ValueError('Xe đã được ghi nhận vượt vạch.')
        if self.s_front_m < 0:
            raise ValueError('Xe chưa tới vạch dừng.')
        object.__setattr__(self, 'crossed_stop_t', t)
        object.__setattr__(self, 'motion_state', MotionState.CROSSING)

    def mark_exited(self, t: float) -> None:
        """Ghi nhận rời khung sau crossing; không suy đoán hình học."""
        number('Thời điểm rời khung', t, low=0)
        if self.crossed_stop_t is None:
            raise ValueError('Xe chỉ được rời khung sau crossing.')
        if self.exited_world_t is not None:
            raise ValueError('Xe đã được ghi nhận rời khung.')
        if t < self.crossed_stop_t:
            raise ValueError('Thời điểm rời khung không được trước crossing.')
        object.__setattr__(self, 'exited_world_t', t)
        object.__setattr__(self, 'speed_mps', 0.0)
        object.__setattr__(self, 'motion_state', MotionState.EXITED)

    def add_stopped_delay(self, dt_s: float) -> None:
        """Core cộng khoảng đứng yên trước vạch, không tự chạy đồng hồ."""
        number('dt_s', dt_s, low=0)
        if self.crossed_stop_t is not None or self.speed_mps != 0:
            raise ValueError('Chỉ cộng delay khi xe đứng yên và chưa crossing.')
        total = self.stopped_delay_s + dt_s
        number('stopped_delay_s', total, low=0)
        object.__setattr__(self, 'stopped_delay_s', total)

    def elapsed_to_stopline(self) -> float | None:
        """Trả None nếu chưa crossing; nếu có, trả thời gian từ arrival."""
        if self.crossed_stop_t is None:
            return None
        return self.crossed_stop_t - self.arrival_t

    def to_xy(self, geometry: GeometryProtocol) -> tuple[float, float]:
        """Ủy quyền đổi tọa độ cho Geometry, không xây dựng hình học tại đây."""
        return geometry.lane_to_xy(self.origin, self.s_front_m)

    def snapshot(self) -> dict[str, str | float | None]:
        """Bản chụp độc lập, chỉ chứa giá trị thuần Python phục vụ UI/thống kê."""
        data = asdict(self)
        data['motion_state'] = self.motion_state.value
        data['status'] = self.status
        return data
