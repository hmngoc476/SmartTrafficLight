"""Bảng arrivals bất biến để hai policy dùng chính xác cùng dữ liệu đến."""

from dataclasses import dataclass
import random

from src.core.algorithms import poisson_sample
from src.models.config import Config, DIRECTIONS, integer


@dataclass(frozen=True, slots=True)
class ArrivalTape:
    rows: tuple[tuple[int, int, int, int], ...]

    def __post_init__(self):
        rows = tuple(tuple(row) for row in self.rows)
        for row in rows:
            if len(row) != 4:
                raise ValueError('Mỗi hàng arrivals phải đủ N/S/E/W theo thứ tự.')
            for value in row:
                integer('arrival count', value, 0)
        object.__setattr__(self, 'rows', rows)

    @classmethod
    def from_config(cls, config: Config, horizon_s: int) -> 'ArrivalTape':
        config.validate()
        integer('horizon_s', horizon_s, 1)
        rng = random.Random(config.seed)
        return cls(tuple(tuple(poisson_sample(config.rates_per_min[d] / 60, rng)
                               for d in DIRECTIONS) for _ in range(horizon_s)))

    def at(self, tick: int) -> tuple[int, int, int, int]:
        integer('tick', tick, 0)
        return self.rows[tick]
