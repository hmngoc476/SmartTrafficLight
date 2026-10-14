import json
import os
from pathlib import Path

json_path = Path("data/junctions.json")

config_data = {
    "schema_version": 2,
    "configs": [
        {
            "id": "JCT-001",
            "name": "Giao lộ mẫu - lệch hướng Đông Tây",
            "rates_per_min": {"N": 12, "S": 9, "E": 18, "W": 7},
            "initial_queue": {"N": 7, "S": 4, "E": 16, "W": 5},
            "green_budget_s": 60,
            "min_green_s": 10,
            "yellow_s": 3,
            "all_red_s": 1,
            "startup_delay_s": 2,
            "headway_s": 2,
            "cycles_to_run": 10,
            "seed": 2026,
            "motion_2d": {
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
        }
    ]
}


class FileStorage:
    @staticmethod
    def load_configs(filepath=json_path):
        """Read config list from JSON. Auto-create if file doesn't exist."""
        filepath = Path(filepath)
        if not filepath.exists():
            filepath.parent.mkdir(parents=True, exist_ok=True)
            FileStorage.save_configs(config_data["configs"], filepath)
            return config_data["configs"]

        with open(filepath, "r", encoding="utf-8") as f:
            data = json.load(f)
            return data.get("configs", [])

    @staticmethod
    def save_configs(configs, filepath=json_path):
        """Save configs in to JSON safely (via temp file)."""
        filepath = Path(filepath)
        filepath.parent.mkdir(parents=True, exist_ok=True)

        payload = {
            "schema_version": 2,
            "configs": configs
        }

        temp_path = filepath.with_suffix(".tmp")
        with open(temp_path, "w", encoding="utf-8") as f:
            json.dump(payload, f, ensure_ascii=False, indent=2)

        os.replace(temp_path, filepath)
