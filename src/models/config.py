"""Cấu hình ngã tư; arrival_rates dùng đơn vị xe/phút (cần thống nhất Core)."""
from dataclasses import asdict, dataclass, field
from math import isclose, isfinite
from typing import Any

DIRECTIONS = ('N', 'S', 'E', 'W')


def number(name: str, value: object, low: float | None = None,
           high: float | None = None, *, positive: bool = False) -> None:
    """Từ chối sai kiểu, bool và số không hữu hạn; không ép kiểu."""
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise TypeError(f'{name} phải là số, không phải bool hoặc chuỗi.')
    try:
        finite = isfinite(value)
    except OverflowError:
        finite = False
    if not finite:
        raise ValueError(f'{name} phải hữu hạn.')
    if positive and value <= 0:
        raise ValueError(f'{name} phải lớn hơn 0.')
    if low is not None and value < low:
        raise ValueError(f'{name} phải >= {low}.')
    if high is not None and value > high:
        raise ValueError(f'{name} phải <= {high}.')


def integer(name: str, value: object, low: int | None = None,
            high: int | None = None) -> None:
    if isinstance(value, bool) or not isinstance(value, int):
        raise TypeError(f'{name} phải là số nguyên, không phải bool.')
    number(name, value, low, high)


def text(name: str, value: object) -> None:
    if not isinstance(value, str):
        raise TypeError(f'{name} phải là chuỗi.')
    if not value.strip():
        raise ValueError(f'{name} không được rỗng.')


def direction(value: object) -> None:
    if not isinstance(value, str):
        raise TypeError('Hướng phải là chuỗi.')
    if value not in DIRECTIONS:
        raise ValueError('Hướng phải là N, S, E hoặc W.')


@dataclass
class Motion2DConfig:
    """Các default đề xuất khi bảng tham số V2.3 chưa được cung cấp."""
    dt_s: float = 0.2
    vehicle_length_m: float = 4.5
    min_gap_m: float = 2.0
    max_speed_mps: float = 13.9
    accel_mps2: float = 2.0
    approach_visible_m: float = 100.0
    intersection_width_m: float = 20.0
    stop_margin_m: float = 0.5
    clearance_limit_s: float = 30.0

    def __post_init__(self) -> None:
        self.validate()

    def validate(self) -> None:
        """Kiểm tra tất cả tham số chuyển động."""
        number('dt_s', self.dt_s, high=1, positive=True)
        reciprocal = 1 / self.dt_s
        if not isfinite(reciprocal) or not isclose(reciprocal, round(reciprocal), rel_tol=0, abs_tol=1e-9):
            raise ValueError('1 / dt_s phải là số nguyên trong sai số 1e-9.')
        for name in ('vehicle_length_m', 'max_speed_mps', 'accel_mps2',
                     'approach_visible_m', 'intersection_width_m', 'clearance_limit_s'):
            number(name, getattr(self, name), positive=True)
        for name in ('min_gap_m', 'stop_margin_m'):
            number(name, getattr(self, name), low=0)


@dataclass
class Config:
    """Dữ liệu cấu hình, không chứa thuật toán điều khiển tín hiệu."""
    id: str = 'default'
    name: str = 'Ngã tư mặc định'
    arrival_rates: dict[str, float] = field(default_factory=lambda: dict.fromkeys(DIRECTIONS, 10.0))
    initial_queue: dict[str, int] = field(default_factory=lambda: dict.fromkeys(DIRECTIONS, 0))
    green_budget_s: float = 60.0
    min_green_s: float = 10.0
    yellow_s: float = 3.0
    all_red_s: float = 1.0
    startup_delay_s: float = 2.0
    headway_s: float = 2.0
    cycles_to_run: int = 10
    seed: int = 42
    motion2d: Motion2DConfig = field(default_factory=Motion2DConfig)

    def __post_init__(self) -> None:
        self.validate()
        self.arrival_rates = self.arrival_rates.copy()
        self.initial_queue = self.initial_queue.copy()
        self.motion2d = Motion2DConfig(**asdict(self.motion2d))

    def validate(self) -> None:
        """Raise TypeError/ValueError tiếng Việt khi dữ liệu không hợp lệ."""
        text('id', self.id)
        text('name', self.name)
        for name in ('arrival_rates', 'initial_queue'):
            values = getattr(self, name)
            if not isinstance(values, dict):
                raise TypeError(f'{name} phải là dictionary.')
            if set(values) != set(DIRECTIONS):
                raise ValueError(f'{name} phải có chính xác bốn hướng N/S/E/W.')
            for key, value in values.items():
                if name == 'initial_queue':
                    integer(f'{name}.{key}', value, 0, 100)
                else:
                    number(f'{name}.{key}', value, 0, 30)
        for name in ('min_green_s', 'yellow_s', 'all_red_s', 'headway_s'):
            number(name, getattr(self, name), low=1)
        number('startup_delay_s', self.startup_delay_s, low=0)
        number('green_budget_s', self.green_budget_s, low=2 * self.min_green_s)
        integer('cycles_to_run', self.cycles_to_run, 1, 100)
        integer('seed', self.seed)
        if not isinstance(self.motion2d, Motion2DConfig):
            raise TypeError('motion2d phải là Motion2DConfig.')
        self.motion2d.validate()

    def to_dict(self) -> dict[str, Any]:
        """Bản sao dữ liệu có thể serialize JSON; kiểm tra trước khi xuất."""
        self.validate()
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> 'Config':
        """Nhận một cấu hình đầy đủ từ to_dict(), không nhận envelope Storage."""
        if not isinstance(data, dict):
            raise TypeError('Cấu hình phải là dictionary.')
        if set(data) != set(cls.__dataclass_fields__):
            raise ValueError('Cấu hình có trường thiếu hoặc thừa.')
        values = data.copy()
        motion = values['motion2d']
        if not isinstance(motion, dict):
            raise TypeError('motion2d trong JSON phải là dictionary.')
        if set(motion) != set(Motion2DConfig.__dataclass_fields__):
            raise ValueError('motion2d có trường thiếu hoặc thừa.')
        values['motion2d'] = Motion2DConfig(**motion)
        return cls(**values)
