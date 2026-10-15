from pathlib import Path
from src.core.storage import FileStorage, json_path

#Default 2D motion configuration
motion_2d = {
    "enabled": True,
    "dt_s": 0.2,
    "vehicle_length_m": 4.5,
    "min_gap_m": 2.0,
    "max_speed_mps": 9.0,
    "accel_mps2": 2.0,
    "approach_visible_m": 60.0,
    "intersection_width_m": 16.0,
    "stop_margin_m": 0.5,
    "clearance_limit_s": 30
}

class ConfigManager:
    def __init__(self, filepath=json_path):
        self.filepath = Path(filepath)
        self._config_map: dict[str, dict] = {}
        self._reload_cache()

    def _reload_cache(self):
        """Read JSON file and build an in-memory Hash Map index"""
        configs = FileStorage.load_configs(self.filepath)
        self._config_map = {cfg["id"]: cfg for cfg in configs if "id" in cfg}

    def list_configs(self) -> list:
        """Get the list of all configs"""
        return list(self._config_map.values())

    def get_config(self, config_id: str) -> dict | None:
        """Get config by ID"""
        return self._config_map.get(config_id)

    def valid_config(self, data: dict, is_update: bool = False) -> tuple[bool, str]:
        """Valid config inputs"""
        cfg_id = str(data.get("id", "")).strip()
        if not cfg_id:
            return False, "ID cấu hình không được để trống."

        # Check duplicate ID when creating new config
        if not is_update:
            if cfg_id in self._config_map:
                return False, f"ID '{cfg_id}' đã tồn tại. Vui lòng chọn ID khác."

        # Check green budget and minimum green time constraints
        green_budget = data.get("green_budget_s", 60)
        min_green = data.get("min_green_s", 10)

        if min_green < 1:
            return False, "Thời gian đèn xanh tối thiểu phải >= 1 giây."
        if green_budget < 2 * min_green:
            return False, "Tổng thời gian ngân sách đèn xanh phải >= 2 x thời gian đèn xanh tối thiểu."

        # Check arrival rates (0 - 30 vehicles/min)
        rates = data.get("rates_per_min", {})
        for direction in ["N", "S", "E", "W"]:
            rate = rates.get(direction, 0)
            if not (0 <= rate <= 30):
                return False, f"Lưu lượng xe hướng {direction} phải trong khoảng từ 0 đến 30 xe/phút."

        # Check initial queues (0 - 100 vehicles)
        queues = data.get("initial_queue", {})
        for direction in ["N", "S", "E", "W"]:
            q = queues.get(direction, 0)
            if not (0 <= q <= 100):
                return False, f"Hàng chờ ban đầu hướng {direction} phải trong khoảng từ 0 đến 100 xe."

        return True, "Cấu hình hợp lệ."

    def create_config(self, data: dict) -> tuple[bool, str]:
        """Create new config and save to JSON file"""
        if "motion_2d" not in data or not data["motion_2d"]:
            data["motion_2d"] = motion_2d.copy()

        is_valid, msg = self.valid_config(data, is_update=False)
        if not is_valid:
            return False, msg

        self._config_map[data["id"]] = data
        FileStorage.save_configs(self.list_configs(), self.filepath)
        return True, f"Tạo cấu hình '{data['id']}' thành công!"

    def update_config(self, config_id: str, new_data: dict) -> tuple[bool, str]:
        """Update an existing config"""
        if config_id not in self._config_map:
            return False, f"Không tìm thấy cấu hình với ID '{config_id}'."

        if "motion_2d" not in new_data or not new_data["motion_2d"]:
            new_data["motion_2d"] = motion_2d.copy()

        is_valid, msg = self.valid_config(new_data, is_update=True)
        if not is_valid:
            return False, msg

        self._config_map[config_id] = new_data
        FileStorage.save_configs(self.list_configs(), self.filepath)
        return True, f"Cập nhật cấu hình '{config_id}' thành công!"

    def delete_config(self, config_id: str) -> tuple[bool, str]:
        """Delete a config by ID"""
        if config_id not in self._config_map:
            return False, f"Không tìm thấy cấu hình với ID '{config_id}'."

        del self._config_map[config_id]
        FileStorage.save_configs(self.list_configs(), self.filepath)
        return True, f"Đã xóa cấu hình '{config_id}' thành công!"
