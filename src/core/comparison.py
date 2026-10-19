"""Đối chứng headless: cùng arrivals và H giây, chỉ khác policy chọn xanh."""

from collections.abc import Mapping
from dataclasses import dataclass
from types import MappingProxyType

from src.core.arrivals import ArrivalTape
from src.core.simulation import SimulationEngine
from src.models.config import Config
from src.models.snapshot import DIRECTIONS


@dataclass(frozen=True, slots=True)
class PolicyResult:
    policy: str
    summary: Mapping
    arrivals_by_direction: tuple[int, int, int, int]
    reached_horizon: bool

    def __post_init__(self):
        object.__setattr__(self, 'summary', MappingProxyType(dict(self.summary)))

    def to_dict(self):
        return dict(self.summary, reached_horizon=self.reached_horizon,
                    arrivals_by_direction=dict(zip(DIRECTIONS, self.arrivals_by_direction)))


@dataclass(frozen=True, slots=True)
class ComparisonResult:
    seed: int
    horizon_s: int
    arrivals: ArrivalTape
    adaptive: PolicyResult
    fixed: PolicyResult

    @property
    def comparable(self) -> bool:
        return self.adaptive.reached_horizon and self.fixed.reached_horizon

    def to_dict(self):
        return dict(seed=self.seed, horizon_s=self.horizon_s, comparable=self.comparable,
                    adaptive=self.adaptive.to_dict(), fixed=self.fixed.to_dict())


def compare_policies(config: Config, horizon_s: int) -> ComparisonResult:
    """Không so số chu kỳ: clearance của mỗi policy có thể kéo dài khác nhau."""
    tape = ArrivalTape.from_config(config, horizon_s)
    results = []
    for policy in ('adaptive', 'fixed'):
        engine = SimulationEngine(config, policy=policy, arrival_tape=tape, horizon_s=horizon_s)
        engine.start()
        engine.run_ticks(horizon_s)
        elapsed = engine.sim_time
        totals = tuple(sum(row[i] for row in tape.rows[:elapsed]) for i in range(4))
        results.append(PolicyResult(policy, engine.summary(), totals,
                                    elapsed == horizon_s and engine.session_state != 'ERROR'))
    return ComparisonResult(config.seed, horizon_s, tape, *results)
