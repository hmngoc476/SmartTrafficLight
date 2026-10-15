import json
import os
from pathlib import Path

json_path = Path("data/junctions.json")


class FileStorage:
    @staticmethod
    def load_configs(filepath=json_path):
        """Read config list from JSON, creating an empty V2 file if missing."""
        filepath = Path(filepath)
        if not filepath.exists():
            filepath.parent.mkdir(parents=True, exist_ok=True)
            FileStorage.save_configs([], filepath)
            return []

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
