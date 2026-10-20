"""Đối chứng headless: cùng arrivals và H giây, chỉ khác policy chọn xanh."""

from collections.abc import Mapping
import csv
from dataclasses import dataclass, replace
import io
import json
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


def compare_finished_run(config: Config, summary: Mapping) -> ComparisonResult:
    """Replay a fully completed UI run, preserving its original summary.

    The caller supplies the configuration frozen at Start, not the current form.
    Only status may differ: horizon replay stops where a cycle-based run completed.
    """
    if (summary.get('policy') != 'adaptive' or summary.get('status') != 'COMPLETED'
            or summary.get('cycles_completed') != config.cycles_to_run):
        raise ValueError('Chỉ so sánh khi phiên Adaptive đã chạy đủ số chu kỳ đã cấu hình (COMPLETED).')
    result = compare_policies(config, summary['simulation_seconds'])
    replay = result.adaptive.summary
    if (not result.adaptive.reached_horizon or set(summary) != set(replay)
            or any(summary[key] != replay[key] for key in replay if key != 'status')):
        raise ValueError('Bản cấu hình không tái lập đúng phiên vừa chạy; chưa thể so sánh.')
    return replace(result, adaptive=replace(result.adaptive, summary=summary))


# preferred=None: context only; more completed cycles/green/hold is not inherently better.
COMPARISON_METRICS = (
    ('departed_vehicles', 'Xe đã vượt vạch', 'xe', 'higher'),
    ('avg_queue', 'Queue trung bình', 'xe', 'lower'),
    ('remaining_vehicles', 'Xe chưa vượt vạch cuối phiên', 'xe', 'lower'),
    ('avg_stopped_delay_s', 'Thời gian dừng TB của xe đã vượt vạch', 's', 'lower'),
    ('avg_wait_departed_s', 'Thời gian xuất hiện tới vượt vạch TB', 's', 'lower'),
    ('throughput_per_min', 'Số xe qua vạch mỗi phút', 'xe/phút', 'higher'),
    ('max_queue', 'Queue lớn nhất', 'xe', 'lower'),
    ('clearance_hold_s', 'Thời gian kéo dài đèn đỏ', 's', None),
    ('cycles_completed', 'Chu kỳ đã hoàn tất', 'chu kỳ', None),
    ('initial_total', 'Số xe ban đầu', 'xe', None),
    ('total_arrivals', 'Số xe mới đến', 'xe', None),
    ('simulation_seconds', 'Thời gian đã mô phỏng', 's', None),
    ('avg_green_ns_s', 'Xanh NS trung bình các chu kỳ đã chốt', 's', None),
    ('avg_green_ew_s', 'Xanh EW trung bình các chu kỳ đã chốt', 's', None),
)


def comparison_rows(result: ComparisonResult) -> list[dict]:
    """Positive improvement favors Adaptive; missing/zero baseline stays blank."""
    rows = []
    for metric, label, unit, preferred in COMPARISON_METRICS:
        adaptive, fixed = result.adaptive.summary[metric], result.fixed.summary[metric]
        delta = improvement = None
        if result.comparable and adaptive is not None and fixed is not None:
            delta = adaptive - fixed
            if preferred is not None and fixed != 0:
                improvement = (delta if preferred == 'higher' else -delta) / fixed * 100
        rows.append(dict(metric=metric, label=label, unit=unit, preferred=preferred,
                         adaptive=adaptive, fixed=fixed, adaptive_minus_fixed=delta,
                         improvement_pct=improvement))
    return rows


def comparison_csv_text(result: ComparisonResult, config: Config, *, run_id: str,
                        started_at_iso: str) -> str:
    """One rectangular CSV table, including the frozen config for reproducibility."""
    metadata = dict(
        comparison_schema_version=1, run_id=run_id, started_at_iso=started_at_iso,
        config_id=config.id, config_name=config.name, seed=result.seed,
        horizon_s=result.horizon_s, fixed_green_ns_s=config.green_budget_s // 2,
        fixed_green_ew_s=config.green_budget_s - config.green_budget_s // 2,
        comparable=result.comparable,
        adaptive_status=result.adaptive.summary['status'],
        fixed_status=result.fixed.summary['status'],
        fixed_error=result.fixed.summary['error_message'],
        config_json=json.dumps(config.to_dict(), ensure_ascii=False, allow_nan=False),
    )
    rows = [dict(metadata, **row) for row in comparison_rows(result)]
    out = io.StringIO(newline='')
    writer = csv.DictWriter(out, fieldnames=list(rows[0]), lineterminator='\n')
    writer.writeheader()
    writer.writerows(rows)
    return out.getvalue()
