"""Canonical V2.3 CSV reporting, separate from JSON configuration storage."""
from __future__ import annotations

from collections.abc import Mapping, Sequence
import csv
import io
from pathlib import Path

from src.core.statistics import CycleMetrics

DATA_DIR = Path(__file__).resolve().parents[2] / 'data'
HISTORY_PATH = DATA_DIR / 'sim_history.csv'
CYCLES_PATH = DATA_DIR / 'cycle_metrics.csv'
HISTORY_HEADER = [
    'run_id', 'started_at_iso', 'config_id', 'mode', 'seed', 'cycles_completed',
    'simulation_seconds', 'initial_vehicles', 'arrived_vehicles', 'departed_vehicles',
    'remaining_vehicles', 'avg_wait_departed_s', 'max_queue', 'avg_queue', 'status',
    'crossed_stop_total', 'exited_world_total', 'clearance_hold_s', 'avg_stopped_delay_s',
]
CYCLE_HEADER = [
    'run_id', 'cycle_index', 'q_ns_start', 'q_ew_start', 'green_ns_s', 'green_ew_s',
    'arrivals_ns', 'arrivals_ew', 'departed_ns', 'departed_ew', 'q_ns_end', 'q_ew_end',
    'avg_queue_cycle', 'actual_cycle_s',
]


def summary_row(summary: Mapping, *, run_id: str, started_at_iso: str) -> dict:
    if summary['status'] not in ('STOPPED', 'COMPLETED'):
        raise ValueError('Chỉ lưu CSV cho phiên STOPPED hoặc COMPLETED.')
    values = dict(summary, run_id=run_id, started_at_iso=started_at_iso,
                  mode=summary['policy'], initial_vehicles=summary['initial_total'],
                  arrived_vehicles=summary['total_arrivals'])
    return {key: values[key] for key in HISTORY_HEADER}


def cycle_row(run_id: str, metric: CycleMetrics) -> dict:
    if metric.provisional:
        raise ValueError('Không ghi chu kỳ đang chạy vào CSV.')
    return {key: run_id if key == 'run_id' else getattr(metric, key) for key in CYCLE_HEADER}


def _read_rows(path: Path, header: list[str]) -> list[dict]:
    if not path.exists() or path.stat().st_size == 0:
        return []
    with path.open(encoding='utf-8', newline='') as handle:
        reader = csv.DictReader(handle)
        if reader.fieldnames != header:
            raise ValueError(f"Header CSV '{path.name}' không khớp hợp đồng; cần migration thủ công.")
        return list(reader)


def _append_rows(path: Path, header: list[str], rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    needs_header = not path.exists() or path.stat().st_size == 0
    with path.open('a', encoding='utf-8', newline='') as handle:
        writer = csv.DictWriter(handle, fieldnames=header)
        if needs_header:
            writer.writeheader()
        writer.writerows(rows)
        handle.flush()


class HistoryStorage:
    @staticmethod
    def append_run(summary: Mapping, cycles: Sequence[CycleMetrics], history_path=None,
                   cycles_path=None, *, run_id: str, started_at_iso: str) -> bool:
        row = summary_row(summary, run_id=run_id, started_at_iso=started_at_iso)
        closed = [cycle_row(run_id, metric) for metric in cycles if not metric.provisional]
        history_path = Path(history_path) if history_path is not None else HISTORY_PATH
        cycles_path = Path(cycles_path) if cycles_path is not None else CYCLES_PATH
        history = _read_rows(history_path, HISTORY_HEADER)
        existing_cycles = _read_rows(cycles_path, CYCLE_HEADER)
        if any(r['run_id'] == run_id for r in history):
            return False
        if closed and any(r['run_id'] == run_id for r in existing_cycles):
            return False
        if closed:
            _append_rows(cycles_path, CYCLE_HEADER, closed)
        _append_rows(history_path, HISTORY_HEADER, [row])
        return True


def summary_csv_text(summary: Mapping, cycles: Sequence[CycleMetrics], *, run_id: str,
                     started_at_iso: str) -> str:
    out = io.StringIO(newline='')
    writer = csv.DictWriter(out, fieldnames=HISTORY_HEADER, lineterminator='\n')
    writer.writeheader()
    writer.writerow(summary_row(summary, run_id=run_id, started_at_iso=started_at_iso))
    closed = [cycle_row(run_id, metric) for metric in cycles if not metric.provisional]
    if closed:
        out.write('\n')
        writer = csv.DictWriter(out, fieldnames=CYCLE_HEADER, lineterminator='\n')
        writer.writeheader()
        writer.writerows(closed)
    return out.getvalue()
