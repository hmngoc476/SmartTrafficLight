"""Hình học tĩnh V2.3; không chứa thuật toán tín hiệu hoặc chuyển động.

Tâm làn ±2m và vạch dừng ở biên giao lộ là ĐỀ XUẤT THIẾT KẾ Task 4,
không phải các tọa độ cố định do V2.3 quy định.
"""

from dataclasses import dataclass
from math import isfinite
from types import MappingProxyType

from src.models.snapshot import DIRECTIONS, Direction, GeometrySnapshot
from src.models.config import PHYSICAL_VEHICLE_WIDTH_M, Motion2DConfig

DIRECTION_VECTORS = MappingProxyType({
    "N": (0.0, 1.0),
    "S": (0.0, -1.0),
    "E": (-1.0, 0.0),
    "W": (1.0, 0.0),
})


@dataclass(frozen=True, slots=True)
class Geometry:
    """Tham số hình học bằng mét, bất biến và không tham chiếu Lane/Vehicle.

    Geometry() giữ metadata lịch sử width=None; Core dùng for_motion() để
    truyền rõ bề rộng vật lý 1.8m đã chốt. lane_to_xy không tự clamp vị trí.
    """

    intersection_width_m: float = 16.0
    approach_visible_m: float = 60.0
    vehicle_length_m: float = 4.5
    min_gap_m: float = 2.0
    stop_margin_m: float = 0.5
    lane_offset_m: float = 2.0
    vehicle_width_m: float | None = None

    def __post_init__(self) -> None:
        for name in (
            "intersection_width_m", "approach_visible_m", "vehicle_length_m",
            "min_gap_m", "stop_margin_m", "lane_offset_m", "vehicle_width_m",
        ):
            value = getattr(self, name)
            if name == "vehicle_width_m" and value is None:
                continue
            if isinstance(value, bool) or not isinstance(value, (int, float)):
                raise TypeError(f"{name} phải là số thực.")
            if not isfinite(value):
                raise ValueError(f"{name} phải hữu hạn.")
            minimum_inclusive = name in {"min_gap_m", "stop_margin_m"}
            if value < 0 or (not minimum_inclusive and value == 0):
                raise ValueError(f"{name} nằm ngoài miền hợp lệ.")
            object.__setattr__(self, name, float(value))
        if self.lane_offset_m >= self.intersection_width_m / 2:
            raise ValueError("lane_offset_m phải nhỏ hơn nửa bề rộng giao lộ.")
        if self.vehicle_width_m is not None:
            half_car = self.vehicle_width_m / 2
            if (self.lane_offset_m < half_car
                    or self.lane_offset_m + half_car > self.intersection_width_m / 2 + 1e-9):
                raise ValueError('Hai làn phải chứa đủ bề rộng vật lý của xe.')

    @classmethod
    def for_motion(cls, motion: Motion2DConfig) -> 'Geometry':
        """Tâm làn thích nghi với bề rộng đường; 16m vẫn dùng offset 2m."""
        return cls(intersection_width_m=motion.intersection_width_m,
                   approach_visible_m=motion.approach_visible_m,
                   vehicle_length_m=motion.vehicle_length_m, min_gap_m=motion.min_gap_m,
                   stop_margin_m=motion.stop_margin_m,
                   lane_offset_m=min(2.0, motion.intersection_width_m / 4),
                   vehicle_width_m=PHYSICAL_VEHICLE_WIDTH_M)

    @property
    def world_bounds(self) -> tuple[float, float, float, float]:
        edge = self.intersection_width_m / 2 + self.approach_visible_m
        return (-edge, -edge, edge, edge)

    def vehicle_bounds(self, origin: str, s_front_m: float, length_m: float) -> tuple[float, float, float, float]:
        """AABB đầy đủ của thân xe, không chỉ vị trí đầu xe."""
        if self.vehicle_width_m is None:
            raise ValueError('Thiếu bề rộng vật lý; không thể kiểm tra occupancy.')
        if isinstance(length_m, bool) or not isinstance(length_m, (int, float)):
            raise TypeError('length_m phải là số.')
        if not isfinite(length_m) or length_m <= 0:
            raise ValueError('length_m phải dương và hữu hạn.')
        x, y = self.lane_to_xy(origin, s_front_m)
        dx, dy = DIRECTION_VECTORS[origin]
        rear_x, rear_y = x - length_m * dx, y - length_m * dy
        half = self.vehicle_width_m / 2
        return (min(x, rear_x) - abs(dy) * half, min(y, rear_y) - abs(dx) * half,
                max(x, rear_x) + abs(dy) * half, max(y, rear_y) + abs(dx) * half)

    def occupies_conflict(self, origin: str, s_front_m: float, length_m: float) -> bool:
        x0, y0, x1, y1 = self.vehicle_bounds(origin, s_front_m, length_m)
        a, b, c, d = self.conflict_bounds
        return x0 <= c and x1 >= a and y0 <= d and y1 >= b

    def outside_world(self, origin: str, s_front_m: float, length_m: float) -> bool:
        x0, y0, x1, y1 = self.vehicle_bounds(origin, s_front_m, length_m)
        a, b, c, d = self.world_bounds
        return {'N': y0 > d, 'S': y1 < b, 'E': x1 < a, 'W': x0 > c}[origin]

    @property
    def conflict_bounds(self) -> tuple[float, float, float, float]:
        """(x_min, y_min, x_max, y_max) của vùng xung đột đóng."""
        half_width = self.intersection_width_m / 2
        return (-half_width, -half_width, half_width, half_width)

    def stop_point(self, direction: Direction) -> tuple[float, float]:
        """Tọa độ vạch dừng trên tâm làn; không gồm stop_margin_m."""
        if direction not in DIRECTIONS:
            raise ValueError("direction phải là N, S, E hoặc W.")
        half_width = self.intersection_width_m / 2
        offset = self.lane_offset_m
        return {
            "N": (-offset, -half_width),
            "S": (offset, half_width),
            "E": (half_width, -offset),
            "W": (-half_width, offset),
        }[direction]

    def lane_to_xy(self, origin: str, s_front_m: float) -> tuple[float, float]:
        """Đổi tọa độ đầu xe: stop_point(origin) + s_front_m * vector.

        Đây là API tính tọa độ duy nhất. Core truyền origin và s_front_m của
        Vehicle vào trực tiếp; Geometry không import hoặc giữ Vehicle.
        Tâm (0,0), +x Đông, +y Nam; s âm trước vạch, s dương sau vạch.
        """
        x_stop, y_stop = self.stop_point(origin)
        if isinstance(s_front_m, bool) or not isinstance(s_front_m, (int, float)):
            raise TypeError("s_front_m phải là số thực.")
        if not isfinite(s_front_m):
            raise ValueError("s_front_m phải hữu hạn.")
        dx, dy = DIRECTION_VECTORS[origin]
        s = float(s_front_m)
        return (x_stop + s * dx, y_stop + s * dy)

    def to_snapshot(self) -> GeometrySnapshot:
        """Chép metadata hình học vào DTO cho UI, không lộ dữ liệu Core."""
        return GeometrySnapshot(
            intersection_width_m=self.intersection_width_m,
            approach_visible_m=self.approach_visible_m,
            lane_offset_m=self.lane_offset_m,
            vehicle_width_m=self.vehicle_width_m,
        )
