"""Six-segment adaptive traffic-light controller theo hợp đồng V2.3.

Chức năng:
- Lịch 68s danh định không xung đột: NS_GREEN (21s), NS_YELLOW (3s), ALL_RED_1 (1s),
  EW_GREEN (39s), EW_YELLOW (3s), ALL_RED_2 (1s).
- Không xung đột tín hiệu: chỉ một trục (NS hoặc EW) được xanh tại một thời điểm.
- Không crossing sai pha: is_green_for chỉ cấp quyền khi đúng pha xanh; vàng và đỏ luôn từ chối (False).
- Phối hợp Startup delay & Headway: startup_delay nằm trong pha xanh (không kéo dài ngân sách),
  Controller cung cấp trạng thái chuyển pha và thông số để Engine điều phối Lane clocks.
- Giao diện public controller chuẩn theo hợp đồng và hỗ trợ linh hoạt tham số conflict_clear.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from src.core import algorithms
from src.models.config import Config, integer
from src.models.signal import SignalPlan, SignalSegment
from src.models.snapshot import Direction, Phase, SignalColor, SignalSnapshot

DIRECTIONS: tuple[str, ...] = ("N", "S", "E", "W")


class TrafficLightController:
    """Điều khiển chu kỳ tín hiệu sáu đoạn chuẩn xác và an toàn."""

    def __init__(self, config: Config, *, policy: str = 'adaptive') -> None:
        """Khởi tạo Controller ở trạng thái UNSTARTED với bản sao tách biệt của Config."""
        if not isinstance(config, Config):
            raise TypeError("config phải là Config.")
        config.validate()
        if policy not in ('adaptive', 'fixed'):
            raise ValueError('policy phải là adaptive hoặc fixed.')
        self._policy = policy
        self._config = Config.from_dict(config.to_dict())

        # Trạng thái vòng đời và lịch tín hiệu
        self._plan: SignalPlan | None = None
        self._current_segment: SignalSegment | None = None
        self._last_segment_code: str | None = None
        self._remaining_s: int = 0
        self._cycle_no: int | None = None
        self._cycle_complete: bool = False
        self._in_error: bool = False

        # Các bộ đếm thời gian và an toàn
        self._clearance_hold_s: int = 0
        self._contiguous_hold_s: int = 0
        self._completed_sim_time: int = 0
        self._last_completed_green: tuple[int, int] | None = None
        self._last_utilization: dict[str, float] | None = None

    @property
    def config(self) -> Config:
        """Bản sao cấu hình detached cho Engine/UI."""
        return Config.from_dict(self._config.to_dict())

    @property
    def current_segment_code(self) -> str | None:
        """Mã đoạn tín hiệu hiện tại; None khi chưa kích hoạt; giữ mã khi kết thúc hoặc ERROR."""
        if self._plan is None:
            return None
        if self._current_segment is not None:
            return self._current_segment.code
        return self._last_segment_code

    @property
    def remaining_s(self) -> int:
        """Số giây danh định còn lại của đoạn hiện tại; 0 khi hold, hoàn thành hoặc ERROR."""
        return self._remaining_s

    @property
    def cycle_complete(self) -> bool:
        """True chỉ khi chu kỳ hiện tại đã hoàn tất an toàn qua ALL_RED_2."""
        return self._cycle_complete

    @property
    def in_error(self) -> bool:
        """True khi xảy ra lỗi clearance timeout quá giới hạn an toàn."""
        return self._in_error

    @property
    def clearance_hold_s(self) -> int:
        """Tổng số giây kéo dài ALL_RED (clearance hold) trong chu kỳ hiện tại."""
        return self._clearance_hold_s

    @property
    def cycle_no(self) -> int | None:
        """Số thứ tự chu kỳ hiện tại của Controller."""
        return self._cycle_no

    @property
    def elapsed_s(self) -> int:
        """Tổng số giây logic đã hoàn thành qua các tick của Controller."""
        return self._completed_sim_time

    @property
    def last_utilization(self) -> dict[str, float] | None:
        """Báo cáo hệ số sử dụng của chu kỳ gần nhất phục vụ thống kê."""
        return None if self._last_utilization is None else dict(self._last_utilization)

    def compute_phase_demand(self, queue_lengths: Mapping[str, int]) -> tuple[int, int]:
        """Tổng hợp số lượng xe chờ theo hai trục NS (N+S) và EW (E+W)."""
        counts = self._validate_queue_lengths(queue_lengths)
        return counts["N"] + counts["S"], counts["E"] + counts["W"]

    def compute_utilization(
        self, q_ns: int, q_ew: int, prev_green: tuple[int, int]
    ) -> dict[str, float]:
        """Tính hệ số sử dụng theo giây xanh chu kỳ trước (chuẩn hóa xe/giây)."""
        integer("q_ns", q_ns, 0)
        integer("q_ew", q_ew, 0)
        if not isinstance(prev_green, tuple) or len(prev_green) != 2:
            raise TypeError("prev_green phải là tuple (green_ns_s, green_ew_s).")

        green_ns, green_ew = prev_green
        integer("prev_green[0]", green_ns, self._config.min_green_s)
        integer("prev_green[1]", green_ew, self._config.min_green_s)

        if green_ns + green_ew != self._config.green_budget_s:
            raise ValueError(
                f"prev_green ({green_ns + green_ew}) phải bằng green_budget_s ({self._config.green_budget_s})."
            )

        return {
            "eta_ns": float(q_ns / green_ns),
            "eta_ew": float(q_ew / green_ew),
            "eta_bar": float((q_ns + q_ew) / self._config.green_budget_s),
        }

    def build_cycle_plan(
        self, queue_lengths: Mapping[str, int], *, cycle_no: int
    ) -> SignalPlan:
        """Tạo kế hoạch tín hiệu 6 đoạn danh định từ phân bổ Adaptive mà không kích hoạt."""
        if self._in_error:
            raise RuntimeError("Controller đang ở trạng thái ERROR, không thể tạo plan.")
        if self._plan is not None and not self._cycle_complete:
            raise RuntimeError("Chu kỳ hiện tại chưa hoàn thành, không thể tạo plan mới.")

        integer("cycle_no", cycle_no, 1)
        if self._plan is None:
            if cycle_no != 1:
                raise ValueError("Chu kỳ đầu tiên phải có cycle_no=1.")
        else:
            if cycle_no != self._cycle_no + 1:  # type: ignore[operator]
                raise ValueError(f"cycle_no mới ({cycle_no}) phải bằng cycle_no cũ + 1 ({self._cycle_no + 1}).")

        q_ns, q_ew = self.compute_phase_demand(queue_lengths)
        if self._policy == 'fixed':
            g_ns, g_ew = algorithms.allocate_green_fixed(self._config.green_budget_s, self._config.min_green_s)
        else:
            g_ns, g_ew = algorithms.allocate_green_adaptive(
                q_ns, q_ew, self._config.green_budget_s, self._config.min_green_s)
        return SignalPlan.from_config(self._config, g_ns, g_ew, cycle_no=cycle_no)

    def start_next_cycle(
        self,
        queue_lengths: Mapping[str, int],
        *,
        cycle_no: int,
        started_at: int,
        conflict_clear: bool = True,
    ) -> None:
        """Bắt đầu chu kỳ mới một cách nguyên tử (atomic) tại ranh giới chu kỳ."""
        if self._in_error:
            raise RuntimeError("Controller đang ở trạng thái ERROR, không thể bắt đầu chu kỳ mới.")
        if self._plan is not None and not self._cycle_complete:
            raise RuntimeError("Chỉ được bắt đầu chu kỳ mới sau khi chu kỳ cũ hoàn tất.")

        if not isinstance(conflict_clear, bool):
            raise TypeError("conflict_clear phải là boolean.")
        if conflict_clear is not True:
            raise ValueError("conflict_clear phải là True khi bắt đầu chu kỳ mới.")

        integer("cycle_no", cycle_no, 1)
        integer("started_at", started_at, 0)

        if self._plan is None:
            if cycle_no != 1:
                raise ValueError("Chu kỳ đầu tiên phải có cycle_no=1.")
            if started_at != 0:
                raise RuntimeError("Chu kỳ đầu tiên phải bắt đầu tại started_at=0.")
        else:
            if cycle_no != self._cycle_no + 1:  # type: ignore[operator]
                raise ValueError("cycle_no mới phải tăng đúng một so với chu kỳ trước.")
            if started_at != self._completed_sim_time:
                raise RuntimeError(
                    f"started_at ({started_at}) không khớp với mốc thời gian hoàn thành ({self._completed_sim_time})."
                )

        # Tính toán demand & utilization
        counts = self._validate_queue_lengths(queue_lengths)
        q_ns, q_ew = self.compute_phase_demand(counts)
        if self._last_completed_green is None:
            budget = self._config.green_budget_s
            previous_green = (budget // 2, budget - budget // 2)
        else:
            previous_green = self._last_completed_green
        utilization = self.compute_utilization(q_ns, q_ew, previous_green)

        # Xây dựng plan và kích hoạt nguyên tử
        plan = self.build_cycle_plan(counts, cycle_no=cycle_no)
        first_segment = plan.current()
        if first_segment is None or first_segment.code != "NS_GREEN":
            raise RuntimeError("SignalPlan không bắt đầu bằng NS_GREEN.")

        self._plan = plan
        self._current_segment = first_segment
        self._last_segment_code = first_segment.code
        self._remaining_s = first_segment.duration_s
        self._cycle_no = cycle_no
        self._cycle_complete = False
        self._clearance_hold_s = 0
        self._contiguous_hold_s = 0
        self._last_utilization = utilization

    def tick(self, *, conflict_clear: bool = True) -> None:
        """Xử lý một giây logic mô phỏng đã hoàn tất; bảo vệ an toàn clearance.

        Args:
            conflict_clear: True nếu vùng giao lộ đã giải phóng, False nếu còn xe.
        """
        if not isinstance(conflict_clear, bool):
            raise TypeError("conflict_clear phải là boolean.")
        if self._plan is None or self._current_segment is None:
            raise RuntimeError("Controller chưa được khởi động.")
        if self._in_error:
            raise RuntimeError("Controller đang ở trạng thái ERROR, không thể tick.")
        if self._cycle_complete:
            raise RuntimeError("Chu kỳ đã hoàn tất; không được tick thêm.")

        self._completed_sim_time += 1
        current_code = self._current_segment.code

        if current_code in ("NS_GREEN", "NS_YELLOW", "EW_GREEN", "EW_YELLOW"):
            self._remaining_s -= 1
            if self._remaining_s == 0:
                next_seg = self._plan.move_next()
                if next_seg is None:
                    raise RuntimeError("Kế hoạch kết thúc bất thường trước ALL_RED.")
                self._current_segment = next_seg
                self._last_segment_code = next_seg.code
                self._remaining_s = next_seg.duration_s
                self._contiguous_hold_s = 0
        else:
            # Đoạn ALL_RED_1 hoặc ALL_RED_2
            if self._remaining_s > 0:
                self._remaining_s -= 1
                if self._remaining_s == 0:
                    if conflict_clear:
                        self._handle_all_red_exit(current_code)
                    else:
                        pass
            else:
                # Đang trong clearance hold (remaining_s == 0)
                self._clearance_hold_s += 1
                self._contiguous_hold_s += 1
                limit = self._config.motion_2d.clearance_limit_s

                # R3: Timeout có độ ưu tiên cao hơn conflict_clear nếu vượt ngưỡng
                if self._contiguous_hold_s > limit:
                    self._in_error = True
                    self._cycle_complete = False
                    self._remaining_s = 0
                    return
                elif conflict_clear:
                    self._handle_all_red_exit(current_code)
                else:
                    pass

    def _handle_all_red_exit(self, current_code: str) -> None:
        """Chuyển pha an toàn khi rời ALL_RED."""
        self._contiguous_hold_s = 0
        if current_code == "ALL_RED_1":
            next_seg = self._plan.move_next()
            if next_seg is None:
                raise RuntimeError("Thiếu đoạn EW_GREEN sau ALL_RED_1.")
            self._current_segment = next_seg
            self._last_segment_code = next_seg.code
            self._remaining_s = next_seg.duration_s
        elif current_code == "ALL_RED_2":
            if self._plan is not None:
                self._last_completed_green = (self._plan.green_ns_s, self._plan.green_ew_s)
                self._plan.move_next()
            self._current_segment = None
            self._last_segment_code = "ALL_RED_2"
            self._remaining_s = 0
            self._cycle_complete = True

    def is_green_for(self, direction: str) -> bool:
        """Kiểm tra quyền tín hiệu đèn xanh.

        Tuyệt đối không cấp quyền (trả về False) khi:
        - Chưa kích hoạt chu kỳ, đã hoàn thành hoặc đang ERROR.
        - Đoạn hiện tại là YELLOW, ALL_RED_1, ALL_RED_2.
        - Hướng không thuộc pha xanh hiện tại (trục còn lại).
        """
        if not isinstance(direction, str):
            raise TypeError("direction phải là chuỗi.")
        if direction not in DIRECTIONS:
            raise ValueError("direction phải là N, S, E hoặc W.")

        if self._plan is None or self._current_segment is None or self._cycle_complete or self._in_error:
            return False

        return self._current_segment.is_green_for(direction)

    def fail_safe(self) -> None:
        """Dừng do vi phạm bất biến; không phục vụ crossing mới, giữ tất cả đỏ."""
        self._in_error = True
        self._cycle_complete = False
        self._remaining_s = 0
        self._current_segment = None
        self._last_segment_code = 'ALL_RED_2'

    def to_signal_snapshot(self) -> SignalSnapshot:
        """Tạo đối tượng SignalSnapshot bất biến theo chuẩn Models."""
        if self._plan is None:
            raise RuntimeError("Controller chưa được kích hoạt chu kỳ nào.")

        code = self.current_segment_code
        if code is None:
            raise RuntimeError("Không xác định được mã đoạn tín hiệu hiện tại.")

        active_phase: Phase | None = {
            "NS_GREEN": "NS",
            "NS_YELLOW": "NS",
            "ALL_RED_1": None,
            "EW_GREEN": "EW",
            "EW_YELLOW": "EW",
            "ALL_RED_2": None,
        }[code]

        colors: dict[Direction, SignalColor] = {
            "NS_GREEN": {"N": "GREEN", "S": "GREEN", "E": "RED", "W": "RED"},
            "NS_YELLOW": {"N": "YELLOW", "S": "YELLOW", "E": "RED", "W": "RED"},
            "ALL_RED_1": {"N": "RED", "S": "RED", "E": "RED", "W": "RED"},
            "EW_GREEN": {"N": "RED", "S": "RED", "E": "GREEN", "W": "GREEN"},
            "EW_YELLOW": {"N": "RED", "S": "RED", "E": "YELLOW", "W": "YELLOW"},
            "ALL_RED_2": {"N": "RED", "S": "RED", "E": "RED", "W": "RED"},
        }[code]

        return SignalSnapshot(
            current_segment=code,
            active_phase=active_phase,
            remaining_s=self._remaining_s,
            signal_colors=dict(colors),
        )

    @staticmethod
    def _validate_queue_lengths(queue_lengths: Mapping[str, int]) -> dict[str, int]:
        """Kiểm tra và chuẩn hóa dữ liệu hàng đợi bốn hướng."""
        if not isinstance(queue_lengths, Mapping):
            raise TypeError("queue_lengths phải là mapping.")
        if set(queue_lengths) != set(DIRECTIONS):
            raise ValueError("queue_lengths phải có chính xác bốn khóa N/S/E/W.")
        counts: dict[str, int] = {}
        for d in DIRECTIONS:
            integer(f"queue_lengths[{d}]", queue_lengths[d], 0)
            counts[d] = queue_lengths[d]
        return counts
