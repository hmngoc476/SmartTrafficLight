"""JSON V2: validate đầy đủ, file tạm riêng và ghi nguyên tử trong một process."""

from contextlib import contextmanager
import json
import os
from pathlib import Path
import tempfile
from threading import Lock, RLock

from src.models.config import Config

json_path = Path('data/junctions.json')
_locks_guard = Lock()
_path_locks: dict[Path, RLock] = {}


def dupes_check(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f"Phát hiện khóa JSON trùng lặp: '{key}'")
        result[key] = value
    return result


def num_check(value):
    raise ValueError(f'Từ chối giá trị số không hợp lệ: {value}')


class FileStorage:
    @staticmethod
    @contextmanager
    def transaction(filepath=json_path):
        """Tuần tự hóa read/candidate/write/cache cùng đường dẫn giữa các thread.

        RLock cho phép Manager giữ khóa giao dịch rồi gọi load/save. Đây là
        đồng bộ trong process Streamlit; không phải khóa liên process.
        """
        path = Path(filepath).resolve()
        with _locks_guard:
            lock = _path_locks.setdefault(path, RLock())
        with lock:
            yield

    @staticmethod
    def _validated_configs(configs):
        if not isinstance(configs, list):
            raise TypeError('Dữ liệu configs phải là một mảng (list).')
        validated = []
        seen = set()
        for payload in configs:
            config = Config.from_dict(payload)
            if config.id in seen:
                raise ValueError(f"Phát hiện ID trùng lặp: '{config.id}'")
            seen.add(config.id)
            validated.append(config.to_dict())
        return validated

    @staticmethod
    def load_configs(filepath=json_path):
        """Thiếu file tạo root rỗng; dữ liệu sai luôn bị từ chối và giữ nguyên."""
        path = Path(filepath)
        with FileStorage.transaction(path):
            if not path.exists():
                FileStorage.save_configs([], path)
                return []
            try:
                with path.open(encoding='utf-8') as stream:
                    data = json.load(stream, object_pairs_hook=dupes_check, parse_constant=num_check)
            except json.JSONDecodeError as error:
                raise ValueError(f'File JSON sai cú pháp, giữ nguyên nội dung file: {error}') from error
            if not isinstance(data, dict) or set(data) != {'schema_version', 'configs'}:
                raise ValueError('Root phải có đúng schema_version và configs; legacy cần migration có kiểm soát.')
            if type(data['schema_version']) is not int or data['schema_version'] != 2:
                raise ValueError('Phiên bản JSON chưa được hỗ trợ; yêu cầu schema_version=2.')
            return FileStorage._validated_configs(data['configs'])

    @staticmethod
    def save_configs(configs, filepath=json_path):
        """Validate trước khi mở file; chỉ replace sau khi flush/fsync thành công."""
        payload = {'schema_version': 2, 'configs': FileStorage._validated_configs(configs)}
        path = Path(filepath)
        with FileStorage.transaction(path):
            path.parent.mkdir(parents=True, exist_ok=True)
            temporary = None
            try:
                with tempfile.NamedTemporaryFile(
                    mode='w', encoding='utf-8', dir=path.parent,
                    prefix=f'.{path.name}.', suffix='.tmp', delete=False,
                ) as stream:
                    temporary = Path(stream.name)
                    json.dump(payload, stream, ensure_ascii=False, indent=2, allow_nan=False)
                    stream.flush()
                    os.fsync(stream.fileno())
                os.replace(temporary, path)
            except Exception as error:
                if temporary is not None:
                    temporary.unlink(missing_ok=True)
                raise RuntimeError(f'Ghi file JSON thất bại, giữ nguyên file gốc: {error}') from error
