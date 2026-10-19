"""Canonical V2.3 CSV reporting, separate from JSON configuration storage."""
from __future__ import annotations

from collections.abc import Mapping, Sequence
from contextlib import ExitStack
from datetime import datetime
import csv
import io
import os
from pathlib import Path
import tempfile

from src.core.statistics import CycleMetrics
from src.core.storage import FileStorage
from src.models.config import integer, number

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
    if not isinstance(summary, Mapping):
        raise TypeError('Summary phải là mapping từ Core.')
    if summary['status'] not in ('STOPPED', 'COMPLETED'):
        raise ValueError('Chỉ lưu CSV cho phiên STOPPED hoặc COMPLETED.')
    values = dict(summary, run_id=run_id, started_at_iso=started_at_iso,
                  mode=summary['policy'], initial_vehicles=summary['initial_total'],
                  arrived_vehicles=summary['total_arrivals'])
    row = {key: values[key] for key in HISTORY_HEADER}
    for key in ('run_id', 'config_id', 'started_at_iso'):
        if not isinstance(row[key], str) or not row[key].strip():
            raise ValueError(f'{key} phải là chuỗi không rỗng.')
    try:
        timestamp = datetime.fromisoformat(started_at_iso)
        if timestamp.utcoffset() is None:
            raise ValueError
    except ValueError as error:
        raise ValueError('started_at_iso phải là thời điểm ISO có timezone.') from error
    if row['mode'] not in ('adaptive', 'fixed'):
        raise ValueError('mode phải là adaptive hoặc fixed.')
    integer('seed', row['seed'])
    for key in ('cycles_completed', 'simulation_seconds', 'initial_vehicles', 'arrived_vehicles',
                'departed_vehicles', 'remaining_vehicles', 'max_queue', 'crossed_stop_total',
                'exited_world_total'):
        integer(key, row[key], 0)
    for key in ('avg_wait_departed_s', 'avg_stopped_delay_s', 'avg_queue'):
        if row[key] is not None:
            number(key, row[key], low=0)
    number('clearance_hold_s', row['clearance_hold_s'], low=0)
    if (row['departed_vehicles'] != row['crossed_stop_total']
            or row['initial_vehicles'] + row['arrived_vehicles'] != row['remaining_vehicles'] + row['crossed_stop_total']
            or row['exited_world_total'] > row['crossed_stop_total']):
        raise ValueError('Summary vi phạm bảo toàn xe hoặc crossing/exit.')
    if ((row['avg_wait_departed_s'] is None) != (row['crossed_stop_total'] == 0)
            or (row['avg_stopped_delay_s'] is None) != (row['crossed_stop_total'] == 0)
            or (row['avg_queue'] is None) != (row['simulation_seconds'] == 0)):
        raise ValueError('Average phải để trống đúng khi chưa có mẫu.')
    return row


def cycle_row(run_id: str, metric: CycleMetrics) -> dict:
    if not isinstance(metric, CycleMetrics):
        raise TypeError('Chu kỳ phải là CycleMetrics từ Core.')
    if metric.provisional:
        raise ValueError('Không ghi chu kỳ đang chạy vào CSV.')
    row = {key: run_id if key == 'run_id' else getattr(metric, key) for key in CYCLE_HEADER}
    for key in CYCLE_HEADER:
        if key not in ('run_id', 'avg_queue_cycle'):
            integer(key, row[key], 1 if key in ('cycle_index', 'green_ns_s', 'green_ew_s', 'actual_cycle_s') else 0)
    number('avg_queue_cycle', metric.avg_queue_cycle, low=0)
    integer('started_at_s', metric.started_at_s, 0)
    integer('ended_at_s', metric.ended_at_s, metric.started_at_s + 1)
    number('clearance_hold_s', metric.clearance_hold_s, low=0)
    for axis in ('ns', 'ew'):
        if row[f'q_{axis}_start'] + row[f'arrivals_{axis}'] != row[f'q_{axis}_end'] + row[f'departed_{axis}']:
            raise ValueError('Chu kỳ vi phạm bảo toàn Queue.')
    return row


def _prepare(summary, cycles, *, run_id, started_at_iso):
    row = summary_row(summary, run_id=run_id, started_at_iso=started_at_iso)
    if not all(isinstance(metric, CycleMetrics) for metric in cycles):
        raise TypeError('Chu kỳ phải là CycleMetrics từ Core.')
    closed = [metric for metric in cycles if not metric.provisional]
    rows = [cycle_row(run_id, metric) for metric in closed]
    if len(closed) != row['cycles_completed'] or [m.cycle_index for m in closed] != list(range(1, len(closed)+1)):
        raise ValueError('Danh sách chu kỳ đã chốt không khớp Summary.')
    previous_end = 0
    for metric in closed:
        if metric.started_at_s != previous_end or metric.ended_at_s > row['simulation_seconds']:
            raise ValueError('Thời gian chu kỳ không khớp phiên.')
        previous_end = metric.ended_at_s
    if (sum(m.departures for m in closed) > row['departed_vehicles']
            or sum(m.arrivals for m in closed) > row['arrived_vehicles']
            or sum(m.clearance_hold_s for m in closed) > row['clearance_hold_s'] + 1e-9):
        raise ValueError('Tổng chu kỳ vượt quá số liệu toàn phiên.')
    return row, rows


def _read_rows(path: Path, header: list[str]) -> list[dict]:
    if not path.exists() or path.stat().st_size == 0:
        return []
    with path.open(encoding='utf-8', newline='') as handle:
        reader = csv.DictReader(handle)
        if reader.fieldnames != header:
            raise ValueError(f"Header CSV '{path.name}' không khớp hợp đồng; cần migration thủ công.")
        rows = list(reader)
        if any(set(row) != set(header) or any(value is None for value in row.values()) for row in rows):
            raise ValueError(f"Dòng CSV '{path.name}' bị thiếu/thừa cột; giữ nguyên file.")
        return rows


def _text_row(row):
    return {key: '' if value is None else str(value) for key, value in row.items()}


def _merge_rows(existing, incoming, keys):
    index = {}
    for row in existing:
        key = tuple(row[k] for k in keys)
        if any(not value.strip() for value in key) or key in index:
            raise ValueError('CSV có khóa trống/trùng; cần kiểm tra dữ liệu trước khi ghi tiếp.')
        index[key] = row
    merged, changed = list(existing), False
    for row in incoming:
        row = _text_row(row)
        key = tuple(row[k] for k in keys)
        if key in index:
            if index[key] != row:
                raise ValueError('Cùng run_id/chu kỳ nhưng nội dung khác; giữ nguyên file.')
        else:
            index[key] = row
            merged.append(row)
            changed = True
    return merged, changed


def _write_atomic(path: Path, header: list[str], rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(mode='w', encoding='utf-8', newline='',
                dir=path.parent, prefix=f'.{path.name}.', suffix='.tmp', delete=False) as handle:
            temporary = Path(handle.name)
            writer = csv.DictWriter(handle, fieldnames=header)
            writer.writeheader()
            writer.writerows(rows)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
    except Exception:
        if temporary is not None:
            temporary.unlink(missing_ok=True)
        raise


class HistoryStorage:
    @staticmethod
    def append_run(summary: Mapping, cycles: Sequence[CycleMetrics], history_path=None,
                   cycles_path=None, *, run_id: str, started_at_iso: str) -> bool:
        """True if files gained rows; False only if both already contain identical data.

        Each file is replaced atomically; retry repairs a partial two-file write.
        Sorted path locks serialize concurrent sessions in one Streamlit process.
        """
        row, closed = _prepare(summary, cycles, run_id=run_id, started_at_iso=started_at_iso)
        history_path = Path(history_path if history_path is not None else HISTORY_PATH).resolve()
        cycles_path = Path(cycles_path if cycles_path is not None else CYCLES_PATH).resolve()
        if history_path == cycles_path:
            raise ValueError('Hai file CSV phải có đường dẫn khác nhau.')
        with ExitStack() as stack:
            for path in sorted((history_path, cycles_path)):
                stack.enter_context(FileStorage.transaction(path))
            history = _read_rows(history_path, HISTORY_HEADER)
            existing_cycles = _read_rows(cycles_path, CYCLE_HEADER)
            merged_history, history_changed = _merge_rows(history, [row], ('run_id',))
            merged_cycles, cycles_changed = _merge_rows(existing_cycles, closed, ('run_id','cycle_index'))
            try:
                if cycles_changed:
                    _write_atomic(cycles_path, CYCLE_HEADER, merged_cycles)
                if history_changed:
                    _write_atomic(history_path, HISTORY_HEADER, merged_history)
            except OSError as error:
                raise RuntimeError(f'Chưa ghi đủ lịch sử CSV; báo cáo được giữ để thử lại: {error}') from error
        return history_changed or cycles_changed


def summary_csv_text(summary: Mapping, cycles: Sequence[CycleMetrics], *, run_id: str,
                     started_at_iso: str) -> str:
    row, closed = _prepare(summary, cycles, run_id=run_id, started_at_iso=started_at_iso)
    out = io.StringIO(newline='')
    writer = csv.DictWriter(out, fieldnames=HISTORY_HEADER, lineterminator='\n')
    writer.writeheader()
    writer.writerow(row)
    if closed:
        out.write('\n')
        writer = csv.DictWriter(out, fieldnames=CYCLE_HEADER, lineterminator='\n')
        writer.writeheader()
        writer.writerows(closed)
    return out.getvalue()
