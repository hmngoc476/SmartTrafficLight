"""CRUD JSON V2; khóa toàn bộ giao dịch, chỉ đổi cache sau ghi thành công."""

from __future__ import annotations

import copy
from pathlib import Path
from typing import Any

from src.core.storage import FileStorage, json_path
from src.models.config import Config


class ConfigManager:
    def __init__(self, filepath: str | Path = json_path):
        self.filepath = Path(filepath).resolve()
        self._config_map: dict[str, dict[str, Any]] = {}
        self._reload_cache()

    def _read_map(self):
        # FileStorage validates every Config and rejects duplicate IDs.
        return {config['id']: config for config in FileStorage.load_configs(self.filepath)}

    def _reload_cache(self) -> None:
        with FileStorage.transaction(self.filepath):
            self._config_map = self._read_map()

    @staticmethod
    def _validate(data, configs, is_update=False, config_id=None):
        try:
            Config.from_dict(data)
        except (TypeError, ValueError) as error:
            return False, str(error)
        if is_update:
            if config_id not in configs:
                return False, f"Không tìm thấy cấu hình với ID '{config_id}'."
            if data['id'] != config_id:
                return False, 'Không được thay đổi ID khi cập nhật.'
        elif data['id'] in configs:
            return False, f"ID '{data['id']}' đã tồn tại."
        return True, 'Cấu hình hợp lệ.'

    def validate(self, data, is_update=False, config_id=None) -> tuple[bool, str]:
        with FileStorage.transaction(self.filepath):
            return self._validate(data, self._config_map, is_update, config_id)

    valid_config = validate

    def list(self) -> list[dict[str, Any]]:
        """Bản sao cache; gọi reload() để cập nhật thay đổi từ Manager khác."""
        with FileStorage.transaction(self.filepath):
            return copy.deepcopy(list(self._config_map.values()))

    list_configs = list

    def get(self, config_id: str) -> dict[str, Any] | None:
        with FileStorage.transaction(self.filepath):
            return copy.deepcopy(self._config_map.get(config_id))

    get_config = get

    def reload(self) -> None:
        """Nạp lại cache có kiểm soát; file sai không làm mất cache hiện tại."""
        self._reload_cache()

    def _mutate(self, operation, config_id=None, data=None):
        # Đọc lại trong cùng khóa để các Manager khác nhau không ghi đè dữ liệu cũ.
        with FileStorage.transaction(self.filepath):
            try:
                current = self._read_map()
                if operation == 'delete':
                    if config_id not in current:
                        return False, f"Không tìm thấy cấu hình với ID '{config_id}'."
                else:
                    data = copy.deepcopy(data)
                    valid, message = self._validate(data, current, operation == 'update', config_id)
                    if not valid:
                        return False, message
                    config_id = data['id']
                candidate = copy.deepcopy(current)
                if operation == 'delete':
                    del candidate[config_id]
                else:
                    candidate[config_id] = data
                FileStorage.save_configs(list(candidate.values()), self.filepath)
            except Exception as error:
                return False, f'Chưa lưu được cấu hình, giữ nguyên cache: {error}'
            self._config_map = candidate
            return True, f"Thao tác {operation} cấu hình '{config_id}' thành công."

    def create(self, data) -> tuple[bool, str]:
        return self._mutate('create', data=data)

    def update(self, config_id, new_data) -> tuple[bool, str]:
        return self._mutate('update', config_id, new_data)

    def delete(self, config_id) -> tuple[bool, str]:
        return self._mutate('delete', config_id)

    # Public API cũ trên main vẫn hoạt động cho các caller chưa chuyển tên.
    create_config = create
    update_config = update
    delete_config = delete
