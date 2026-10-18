"""Hình học tĩnh V2.3; không chứa thuật toán tín hiệu hoặc chuyển động.

Tâm làn ±2m và vạch dừng ở biên giao lộ là ĐỀ XUẤT THIẾT KẾ Task 4,
không phải các tọa độ cố định do V2.3 quy định.
"""

from dataclasses import dataclass
from math import isfinite
from types import MappingProxyType

from src.models.snapshot import DIRECTIONS, Direction, GeometrySnapshot

DIRECTION_VECTORS = MappingProxyType({
    "N": (0.0, 1.0),
    "S": (0.0, -1.0),
    "E": (-1.0, 0.0),
    "W": (1.0, 0.0),
})


@dataclass(frozen=True, slots=True)
class Geometry:
    """Tham số hình học bằng mét, bất biến và không tham chiếu Lane/Vehicle.

    vehicle_width_m=None: V2.3 chưa chốt bề rộng xe. Hình bao và kiểm tra
    occupancy chưa được hiện thực; xem phương án trong simulation_contracts.md.
    min_gap_m và stop_margin_m chỉ được cung cấp cho engine tương lai;
    lane_to_xy không dùng chúng để tự sửa vị trí đầu xe.
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
