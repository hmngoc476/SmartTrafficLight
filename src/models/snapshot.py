"""Nguồn định nghĩa snapshot chỉ đọc Task 4; không phải engine mô phỏng.

Các tên trường cụ thể và schema_version=1 là ĐỀ XUẤT THIẾT KẾ API.
Frozen dataclasses kết hợp tuple và bản sao MappingProxyType ngăn lộ
collection mutable của Core. to_dict tạo dữ liệu JSON tách biệt mới.
"""

from collections.abc import Mapping
from dataclasses import asdict, dataclass
from math import isfinite
from types import MappingProxyType
from typing import Any, Literal

Direction = Literal["N", "S", "E", "W"]
SignalColor = Literal["GREEN", "YELLOW", "RED"]
Phase = Literal["NS", "EW"]
MotionState = Literal["APPROACHING", "STOPPED", "CROSSING"]
SessionState = Literal["RUNNING", "PAUSED", "STOPPED", "COMPLETED", "ERROR"]
DIRECTIONS: tuple[Direction, ...] = ("N", "S", "E", "W")


def _count(name: str, value: int, minimum: int = 0) -> None:
    if type(value) is not int:
        raise TypeError(f"{name} phải là int, không nhận bool.")
    if value < minimum:
        raise ValueError(f"{name} phải >= {minimum}.")


def _number(name: str, value: float, minimum: float | None = None) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise TypeError(f"{name} phải là số thực.")
    if not isfinite(value) or (minimum is not None and value < minimum):
        raise ValueError(f"{name} không hữu hạn hoặc ngoài miền hợp lệ.")
    return float(value)


def _directions_copy(values: Mapping) -> dict:
    if not isinstance(values, Mapping):
        raise TypeError("Dữ liệu theo hướng phải là mapping.")
    if set(values) != set(DIRECTIONS):
        raise ValueError("Mapping phải có đúng bốn khóa N/S/E/W.")
    return {direction: values[direction] for direction in DIRECTIONS}


@dataclass(frozen=True, slots=True)
class GeometrySnapshot:
    """Metadata chỉ đọc để UI dựng đường; các giá trị do Geometry cung cấp."""

    intersection_width_m: float
    approach_visible_m: float
    lane_offset_m: float
    vehicle_width_m: float | None = None

    def __post_init__(self) -> None:
        for name in ("intersection_width_m", "approach_visible_m", "lane_offset_m", "vehicle_width_m"):
            value = getattr(self, name)
            if name == "vehicle_width_m" and value is None:
                continue
            value = _number(name, value, 0)
            if value == 0:
                raise ValueError(f"{name} phải > 0.")
            object.__setattr__(self, name, value)
        if self.lane_offset_m >= self.intersection_width_m / 2:
            raise ValueError("lane_offset_m phải nằm trong bề rộng giao lộ.")


@dataclass(frozen=True, slots=True)
class VehicleSnapshot:
    """Giá trị của một xe trong thế giới; không chứa đối tượng Vehicle thật.

    APPROACHING/STOPPED thuộc Queue; CROSSING thuộc active_crossing.
    EXITED không được đưa vào snapshot vehicles. x/y là đầu xe, không phải tâm.
    """

    vehicle_id: str
    origin: Direction
    x: float
    y: float
    speed_mps: float
    motion_state: MotionState
    s_front_m: float
    length_m: float

    def __post_init__(self) -> None:
        if not isinstance(self.vehicle_id, str) or not self.vehicle_id.strip():
            raise ValueError("vehicle_id phải là chuỗi không rỗng.")
        if self.origin not in DIRECTIONS:
            raise ValueError("origin không hợp lệ.")
        if self.motion_state not in ("APPROACHING", "STOPPED", "CROSSING"):
            raise ValueError("motion_state không hợp lệ; snapshot không chứa EXITED.")
        for name in ("x", "y", "speed_mps", "s_front_m", "length_m"):
            minimum = 0 if name in ("speed_mps", "length_m") else None
            object.__setattr__(self, name, _number(name, getattr(self, name), minimum))
        if self.length_m == 0:
            raise ValueError("length_m phải > 0.")
        if self.motion_state == "CROSSING" and self.s_front_m < 0:
            raise ValueError("Xe CROSSING không thể ở trước vạch.")
        if self.motion_state != "CROSSING" and self.s_front_m > 0:
            raise ValueError("Xe chưa crossing không thể ở sau vạch.")


@dataclass(frozen=True, slots=True)
class SignalSnapshot:
    """Pha gắn với đoạn tín hiệu; active_phase không tự cấp quyền crossing."""

    current_segment: str
    active_phase: Phase | None
    remaining_s: int
    signal_colors: Mapping[Direction, SignalColor]

    def __post_init__(self) -> None:
        _count("remaining_s", self.remaining_s)
        red = ("RED", "RED", "RED", "RED")
        expected = {
            "NS_GREEN": ("NS", ("GREEN", "GREEN", "RED", "RED")),
            "NS_YELLOW": ("NS", ("YELLOW", "YELLOW", "RED", "RED")),
            "ALL_RED_1": (None, red),
            "EW_GREEN": ("EW", ("RED", "RED", "GREEN", "GREEN")),
            "EW_YELLOW": ("EW", ("RED", "RED", "YELLOW", "YELLOW")),
            "ALL_RED_2": (None, red),
        }
        if self.current_segment not in expected:
            raise ValueError("current_segment không thuộc sáu đoạn V2.3.")
        colors = _directions_copy(self.signal_colors)
        phase, required_colors = expected[self.current_segment]
        if self.active_phase != phase or tuple(colors.values()) != required_colors:
            raise ValueError("Pha/màu đèn không khớp đoạn tín hiệu hoặc có xung đột.")
        object.__setattr__(self, "signal_colors", MappingProxyType(colors))


@dataclass(frozen=True, slots=True)
class MetricsSnapshot:
    """Counters lũy kế phiên; Queue và active là số lượng hiện tại."""

    queue_lengths: Mapping[Direction, int]
    initial_total: int
    total_arrivals: int
    crossed_stop_total: int
    exited_world_total: int
    active_crossing_count: int
    clearance_hold_s: float

    def __post_init__(self) -> None:
        queues = _directions_copy(self.queue_lengths)
        for direction, value in queues.items():
            _count(f"queue_lengths[{direction}]", value)
        for name in (
            "initial_total", "total_arrivals", "crossed_stop_total",
            "exited_world_total", "active_crossing_count",
        ):
            _count(name, getattr(self, name))
        object.__setattr__(self, "queue_lengths", MappingProxyType(queues))
        object.__setattr__(self, "clearance_hold_s", _number("clearance_hold_s", self.clearance_hold_s, 0))
        if self.crossed_stop_total != self.active_crossing_count + self.exited_world_total:
            raise ValueError("Bảo toàn crossed = active + exited bị vi phạm.")
        if self.initial_total + self.total_arrivals != sum(queues.values()) + self.crossed_stop_total:
            raise ValueError("Bảo toàn initial + arrivals = queue + crossed bị vi phạm.")


@dataclass(frozen=True, slots=True)
class SimulationSnapshot:
    """Snapshot cuối tick, gồm toàn bộ Queue và active; UI tự clip viewport.

    Không có snapshot trước khởi tạo phiên. cycle_index bắt đầu từ 1.
    Schema snapshot v1 độc lập với schema_version=2 của junctions.json.
    """

    sim_time: int
    cycle_index: int
    session_state: SessionState
    geometry: GeometrySnapshot
    signals: SignalSnapshot
    metrics: MetricsSnapshot
    vehicles: tuple[VehicleSnapshot, ...]
    schema_version: int = 1

    def __post_init__(self) -> None:
        _count("sim_time", self.sim_time)
        _count("cycle_index", self.cycle_index, 1)
        _count("schema_version", self.schema_version, 1)
        if self.schema_version != 1:
            raise ValueError("Chỉ hỗ trợ snapshot schema_version=1.")
        if self.session_state not in ("RUNNING", "PAUSED", "STOPPED", "COMPLETED", "ERROR"):
            raise ValueError("session_state không hợp lệ.")
        if type(self.geometry) is not GeometrySnapshot:
            raise TypeError("geometry phải là GeometrySnapshot.")
        if type(self.signals) is not SignalSnapshot or type(self.metrics) is not MetricsSnapshot:
            raise TypeError("signals/metrics phải là các snapshot dữ liệu đã định nghĩa.")
        if not isinstance(self.vehicles, (list, tuple)):
            raise TypeError("vehicles phải là list hoặc tuple các VehicleSnapshot.")
        vehicles = tuple(self.vehicles)
        if any(type(vehicle) is not VehicleSnapshot for vehicle in vehicles):
            raise TypeError("vehicles không được chứa Vehicle thật hoặc dict mutable.")
        if len({vehicle.vehicle_id for vehicle in vehicles}) != len(vehicles):
            raise ValueError("Snapshot chứa vehicle_id trùng.")
        queues = {direction: 0 for direction in DIRECTIONS}
        active = 0
        for vehicle in vehicles:
            if vehicle.motion_state == "CROSSING":
                active += 1
            else:
                queues[vehicle.origin] += 1
        if queues != dict(self.metrics.queue_lengths) or active != self.metrics.active_crossing_count:
            raise ValueError("Danh sách xe không khớp Queue/active counters.")
        if self.session_state == "ERROR" and any(color != "RED" for color in self.signals.signal_colors.values()):
            raise ValueError("ERROR phải giữ tất cả đèn đỏ.")
        object.__setattr__(self, "vehicles", vehicles)

    def to_dict(self) -> dict[str, Any]:
        """Tạo cây dict/list JSON mới, không chia sẻ collection với snapshot."""
        return {
            "schema_version": self.schema_version,
            "sim_time": self.sim_time,
            "cycle_index": self.cycle_index,
            "session_state": self.session_state,
            "geometry": asdict(self.geometry),
            "signals": {
                "current_segment": self.signals.current_segment,
                "active_phase": self.signals.active_phase,
                "remaining_s": self.signals.remaining_s,
                "signal_colors": dict(self.signals.signal_colors),
            },
            "metrics": {
                "queue_lengths": dict(self.metrics.queue_lengths),
                "initial_total": self.metrics.initial_total,
                "total_arrivals": self.metrics.total_arrivals,
                "crossed_stop_total": self.metrics.crossed_stop_total,
                "exited_world_total": self.metrics.exited_world_total,
                "active_crossing_count": self.metrics.active_crossing_count,
                "clearance_hold_s": self.metrics.clearance_hold_s,
            },
            "vehicles": [asdict(vehicle) for vehicle in self.vehicles],
        }

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "SimulationSnapshot":
        """Đọc cấu trúc JSON v1 thành các bản sao chỉ đọc; không chạy engine."""
        if not isinstance(data, Mapping):
            raise TypeError("Snapshot JSON phải là mapping.")
        required = {"schema_version", "sim_time", "cycle_index", "session_state", "geometry", "signals", "metrics", "vehicles"}
        if set(data) != required:
            raise ValueError("Snapshot JSON thiếu trường hoặc có trường ngoài schema v1.")
        if not isinstance(data["vehicles"], list):
            raise TypeError("vehicles trong JSON phải là array.")
        return cls(
            schema_version=data["schema_version"],
            sim_time=data["sim_time"],
            cycle_index=data["cycle_index"],
            session_state=data["session_state"],
            geometry=GeometrySnapshot(**data["geometry"]),
            signals=SignalSnapshot(**data["signals"]),
            metrics=MetricsSnapshot(**data["metrics"]),
            vehicles=tuple(VehicleSnapshot(**vehicle) for vehicle in data["vehicles"]),
        )
