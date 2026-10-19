"""Read-only dashboard view. Canonical Engine.summary() remains a dict."""
from collections.abc import Mapping
from dataclasses import dataclass
from types import MappingProxyType

from src.core.statistics import CycleMetrics
from src.models.snapshot import SimulationSnapshot


@dataclass(frozen=True, slots=True)
class DashboardData:
    snapshot: SimulationSnapshot
    current_green: tuple[int, int]
    previous_green: tuple[int, int] | None
    queue_series: tuple[tuple[int, int], ...]
    cycle_metrics: tuple[CycleMetrics, ...]
    conflict_occupancy_count: int
    min_gap_config_m: float
    observed_min_gap_m: float | None
    summary: Mapping[str, object] | None

    def __post_init__(self):
        if self.summary is not None:
            object.__setattr__(self, 'summary', MappingProxyType(dict(self.summary)))
