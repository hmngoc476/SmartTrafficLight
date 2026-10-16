from __future__ import annotations

from pathlib import Path
from typing import Any
import copy

from src.core.storage import FileStorage, json_path
from src.models.config import Config


class ConfigManager:
    def __init__(self, filepath: str | Path = json_path):
        self.filepath = Path(filepath)
        self._config_map: dict[str, dict[str, Any]] = {}
        self._reload_cache()

    # [P1.1. Bắt lỗi ID trùng / thiếu khi khởi tạo cache (_reload_cache)]
    def _reload_cache(self) -> None:
        """Read JSON file, validate strictly each config and build an in-memory Hash Map index"""
        configs = FileStorage.load_configs(self.filepath)
        temp_map: dict[str, dict[str, Any]] = {}

        for cfg in configs:
            if not isinstance(cfg, dict):
                raise TypeError("Mỗi cấu hình trong JSON phải là một dictionary.")

            # [P0.2: Validate dữ liệu bằng Config.from_dict() từ Models]
            Config.from_dict(cfg)

            cfg_id = cfg.get("id")
            if not cfg_id or not isinstance(cfg_id, str):
                raise ValueError("Cấu hình bị thiếu trường 'id' hoặc 'id' không hợp lệ.")

            if cfg_id in temp_map:
                raise ValueError(f"Phát hiện ID trùng lặp trong file JSON: '{cfg_id}'")

            temp_map[cfg_id] = cfg

        self._config_map = temp_map

    # [P0.2. Sử dụng Config.from_dict() để thống nhất validation]
    # [P0.3. Khóa ID cấu hình không đổi khi Update]
    def validate(
            self,
            data: dict[str, Any],
            is_update: bool = False,
            config_id: str | None = None,
    ) -> tuple[bool, str]:
        """Validate cấu hình sử dụng Config.from_dict() làm chuẩn Models."""
        if not isinstance(data, dict):
            return False, "Dữ liệu cấu hình phải là một object (dict)."

        # [P0.3. Khóa ID cấu hình không đổi khi Update]
        if is_update and config_id is not None:
            if config_id not in self._config_map:
                return False, f"Không tìm thấy cấu hình với ID '{config_id}'."
            new_id = data.get("id")
            if new_id != config_id:
                return (
                    False,
                    f"Không được thay đổi ID khi cập nhật (ID gốc: '{config_id}', ID mới: '{new_id}').",
                )

        # [P0.2. Sử dụng Config.from_dict() để thống nhất validation]
        # - Không xây dựng lại toàn bộ quy tắc validation trong Manager
        # - Không tự chuyển string/float/bool thành integer
        # - Không tự điền hướng N/S/E/W còn thiếu
        # - Kiểm tra đầy đủ motion_2d ngay cả khi enabled=False
        try:
            Config.from_dict(data)
        except (ValueError, TypeError) as e:
            return False, str(e)

        cfg_id = data["id"]

        # Kiểm tra ID trùng khi tạo mới
        if not is_update:
            if cfg_id in self._config_map:
                return False, f"ID '{cfg_id}' đã tồn tại. Vui lòng chọn ID khác."

        return True, "Cấu hình hợp lệ."

    # [P2.2. Chuẩn hóa Public API ConfigManager và Aliases]
    def valid_config(
            self,
            data: dict[str, Any],
            is_update: bool = False,
            config_id: str | None = None,
    ) -> tuple[bool, str]:
        return self.validate(data, is_update=is_update, config_id=config_id)

    # [P1.3. Ngăn thay đổi HashMap ngoài CRUD]
    def list(self) -> list[dict[str, Any]]:
        """Get list of all configs (returns deep copy)."""
        return copy.deepcopy(list(self._config_map.values()))

    # [P2.2. Chuẩn hóa Public API ConfigManager và Aliases]
    def list_configs(self) -> list[dict[str, Any]]:
        return self.list()

    # [P1.3. Ngăn thay đổi HashMap ngoài CRUD]
    def get(self, config_id: str) -> dict[str, Any] | None:
        """Get config by ID (returns deep copy)."""
        cfg = self._config_map.get(config_id)
        return copy.deepcopy(cfg) if cfg is not None else None

    # [P2.2. Chuẩn hóa Public API ConfigManager và Aliases]
    def get_config(self, config_id: str) -> dict[str, Any] | None:
        return self.get(config_id)

    # [P0.4. Đồng bộ HashMap và Atomic Persistence]
    def create(self, data: dict[str, Any]) -> tuple[bool, str]:
        """Create new config"""
        is_valid, msg = self.valid_config(data, is_update=False)
        if not is_valid:
            return False, msg

        cfg_id = data["id"]

        # 1. Tạo candidate HashMap
        candidate_map = copy.deepcopy(self._config_map)
        candidate_map[cfg_id] = copy.deepcopy(data)

        # 2. FileStorage.save_configs() thành công mới cập nhật RAM
        try:
            FileStorage.save_configs(list(candidate_map.values()), self.filepath)
        except Exception as e:
            return False, f"Lưu cấu hình thất bại, giữ nguyên dữ liệu RAM: {e}"

        # 3. Save thành công -> Thay cache chính
        self._config_map = candidate_map
        return True, f"Tạo cấu hình '{cfg_id}' thành công!"

    # [P0.3. Khóa ID cấu hình không đổi khi Update]
    # [P0.4. Đồng bộ HashMap và Atomic Persistence]
    def update(self, config_id: str, new_data: dict[str, Any]) -> tuple[bool, str]:
        """Update an existing config"""
        is_valid, msg = self.valid_config(new_data, is_update=True, config_id=config_id)
        if not is_valid:
            return False, msg

        # 1. Tạo candidate HashMap
        candidate_map = copy.deepcopy(self._config_map)
        candidate_map[config_id] = copy.deepcopy(new_data)

        # 2. FileStorage.save_configs() thành công mới cập nhật RAM
        try:
            FileStorage.save_configs(list(candidate_map.values()), self.filepath)
        except Exception as e:
            return False, f"Cập nhật cấu hình thất bại, giữ nguyên dữ liệu RAM: {e}"

        # 3. Save thành công -> Thay cache chính
        self._config_map = candidate_map
        return True, f"Cập nhật cấu hình '{config_id}' thành công!"

    # [P0.4. Đồng bộ HashMap và Atomic Persistence]
    def delete(self, config_id: str) -> tuple[bool, str]:
        """Delete a config"""
        if config_id not in self._config_map:
            return False, f"Không tìm thấy cấu hình với ID '{config_id}'."

        # 1. Tạo candidate HashMap
        candidate_map = copy.deepcopy(self._config_map)
        del candidate_map[config_id]

        # 2. FileStorage.save_configs() thành công mới cập nhật RAM
        try:
            FileStorage.save_configs(list(candidate_map.values()), self.filepath)
        except Exception as e:
            return False, f"Xoá cấu hình thất bại, giữ nguyên dữ liệu RAM: {e}"

        # 3. Save thành công -> Thay cache chính
        self._config_map = candidate_map
        return True, f"Đã xóa cấu hình '{config_id}' thành công!"
