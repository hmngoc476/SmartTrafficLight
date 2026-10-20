"""Lịch tín hiệu danh định; Controller quyết định khi nào chuyển đoạn."""

from src.models.deque import Deque
from dataclasses import dataclass, field

from src.models.config import Config, direction, integer, number


@dataclass(frozen=True)
class SignalSegment:
    """Một đoạn bất biến; vàng và đỏ không có active_phase cấp quyền đi."""

    code: str
    active_phase: str | None
    color: str
    duration_s: int

    def __post_init__(self) -> None:
        expected = {
            'NS_GREEN': ('NS', 'GREEN'),
            'NS_YELLOW': (None, 'YELLOW'),
            'ALL_RED_1': (None, 'RED'),
            'EW_GREEN': ('EW', 'GREEN'),
            'EW_YELLOW': (None, 'YELLOW'),
            'ALL_RED_2': (None, 'RED'),
        }
        if not isinstance(self.code, str):
            raise TypeError('code phải là chuỗi.')
        if self.code not in expected:
            raise ValueError('Mã đoạn tín hiệu không hợp lệ.')
        if not isinstance(self.color, str):
            raise TypeError('color phải là chuỗi.')
        if self.active_phase is not None and not isinstance(self.active_phase, str):
            raise TypeError('active_phase phải là chuỗi hoặc None.')
        if (self.active_phase, self.color) != expected[self.code]:
            raise ValueError('code, color và active_phase không nhất quán.')
        integer('duration_s', self.duration_s, 1)

    @property
    def green_directions(self) -> tuple[str, ...]:
        """Các hướng có xanh; tuple rỗng cho mọi đoạn vàng/đỏ."""
        if self.code == 'NS_GREEN':
            return ('N', 'S')
        if self.code == 'EW_GREEN':
            return ('E', 'W')
        return ()

    def is_green_for(self, traffic_direction: str) -> bool:
        """Chỉ xét tín hiệu; hướng sai bị từ chối để phát hiện lỗi tích hợp."""
        direction(traffic_direction)
        return traffic_direction in self.green_directions


@dataclass(frozen=True, eq=False)
class SignalPlan:
    """Sáu đoạn cố định, deque riêng chỉ tiến khi Core gọi move_next()."""

    green_ns_s: int
    green_ew_s: int
    yellow_s: int = 3
    all_red_s: int = 1
    cycle_no: int = 1
    _segments: tuple[SignalSegment, ...] = field(init=False, repr=False)
    _pending: Deque[SignalSegment] = field(init=False, repr=False)

    def __post_init__(self) -> None:
        for name in ('green_ns_s', 'green_ew_s', 'yellow_s', 'all_red_s', 'cycle_no'):
            integer(name, getattr(self, name), 1)
        segments = (
            SignalSegment('NS_GREEN', 'NS', 'GREEN', self.green_ns_s),
            SignalSegment('NS_YELLOW', None, 'YELLOW', self.yellow_s),
            SignalSegment('ALL_RED_1', None, 'RED', self.all_red_s),
            SignalSegment('EW_GREEN', 'EW', 'GREEN', self.green_ew_s),
            SignalSegment('EW_YELLOW', None, 'YELLOW', self.yellow_s),
            SignalSegment('ALL_RED_2', None, 'RED', self.all_red_s),
        )
        object.__setattr__(self, '_segments', segments)
        object.__setattr__(self, '_pending', Deque(segments))

    @property
    def segments(self) -> tuple[SignalSegment, ...]:
        """Toàn bộ lịch bất biến, vẫn còn đầy đủ sau khi chu kỳ kết thúc."""
        return self._segments

    @property
    def nominal_duration_s(self) -> int:
        """Tổng thời gian danh định, không gồm clearance hold của Controller."""
        return sum(segment.duration_s for segment in self.segments)

    def current(self) -> SignalSegment | None:
        """Xem đoạn hiện tại mà không làm thay đổi lịch."""
        return self._pending[0] if self._pending else None

    def move_next(self) -> SignalSegment | None:
        """Hoàn tất đoạn hiện tại do Core xác nhận; không tự lặp chu kỳ."""
        if self._pending:
            self._pending.popleft()
        return self.current()

    def is_cycle_end(self) -> bool:
        """True chỉ sau khi đoạn ALL_RED_2 đã được hoàn tất."""
        return not self._pending

    @classmethod
    def from_config(cls, config: Config, green_ns_s: int, green_ew_s: int,
                    cycle_no: int = 1) -> 'SignalPlan':
        """Nhận phân bổ của Algorithm, kiểm tra budget/min; không tính Adaptive."""
        if not isinstance(config, Config):
            raise TypeError('config phải là Config.')
        config.validate()
        integer('green_ns_s', green_ns_s, 1)
        integer('green_ew_s', green_ew_s, 1)
        if green_ns_s + green_ew_s != config.green_budget_s:
            raise ValueError('Tổng hai thời gian xanh phải bằng green_budget_s.')
        if min(green_ns_s, green_ew_s) < config.min_green_s:
            raise ValueError('Mỗi pha xanh phải >= min_green_s.')

        def whole_seconds(name: str, value: float) -> int:
            number(name, value, low=1)
            if value % 1 != 0:
                raise ValueError(f'{name} phải là số giây nguyên, không cắt thập phân.')
            return int(value)

        return cls(green_ns_s, green_ew_s,
                   whole_seconds('yellow_s', config.yellow_s),
                   whole_seconds('all_red_s', config.all_red_s), cycle_no)
