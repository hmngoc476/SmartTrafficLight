import json
import os
from pathlib import Path

json_path = Path("data/junctions.json")

# [P0.1. Hoàn thiện FileStorage.load_configs() - Kiểm tra trùng lặp khóa JSON]
def dupes_check(pairs):
    out_dict = {}
    for key, val in pairs:
        if key in out_dict:
            raise ValueError(f"Phát hiện khóa JSON trùng lặp: '{key}'")
        out_dict[key] = val
    return out_dict

# [P0.1. Hoàn thiện FileStorage.load_configs() - Từ chối giá trị số không hợp lệ (NaN/Infinity)]
def num_check(val):
    raise ValueError(f"Từ chối giá trị số không hợp lệ: {val}")

class FileStorage:
    # [P0.1. Hoàn thiện FileStorage.load_configs()]
    @staticmethod
    def load_configs(filepath=json_path):
        """Read config list from JSON, creating an empty V2 file if missing."""
        filepath = Path(filepath)

        # [YÊU CẦU: Khởi tạo file skeleton JSON V2 nếu file chưa tồn tại]
        if not filepath.exists():
            filepath.parent.mkdir(parents=True, exist_ok=True)
            empty_data = {"schema_version": 2, "configs": []}
            with open(filepath, "w", encoding="utf-8") as f:
                json.dump(empty_data, f, ensure_ascii=False, indent=2)
            return []

        # [YÊU CẦU: Đọc strict JSON parsing, giữ nguyên nội dung file nếu sai cú pháp]
        try:
            with open(filepath, "r", encoding="utf-8") as f:
                data = json.load(
                    f,
                    object_pairs_hook= dupes_check,
                    parse_constant= num_check
                )
        except json.JSONDecodeError as e:
            raise ValueError(f"File JSON sai cú pháp, giữ nguyên nội dung file: {e}")

        # [YÊU CẦU: Kiểm tra JSON root là object (dict)]
        if not isinstance(data, dict):
            raise ValueError("Root của JSON phải là một object (dictionary).")

        # [YÊU CẦU: Không chấp nhận trường ngoài JSON Schema & Không tự chuyển đổi legacy (V1)]
        allowed_keys = {"schema_version", "configs"}
        actual_keys = set(data.keys())
        if actual_keys != allowed_keys:
            raise ValueError("Không chấp nhận trường ngoài JSON Schema hoặc dữ liệu legacy. Cần migration thủ công.")

        # [YÊU CẦU: Bắt buộc có schema_version và đúng phiên bản 2]
        if data.get("schema_version") != 2:
            raise ValueError("Bắt buộc có schema_version và đúng phiên bản 2.")

        # [YÊU CẦU: Bắt buộc có configs kiểu list]
        configs = data.get("configs")
        if not isinstance(configs, list):
            raise ValueError("Trường 'configs' bắt buộc phải là kiểu list.")

        # [YÊU CẦU: Validate từng cấu hình và kiểm tra ID trùng/rỗng trước khi chấp nhận dữ liệu]
        seen_ids = set()
        for cfg in configs:
            if not isinstance(cfg, dict):
                raise ValueError("Mỗi cấu hình bên trong 'configs' phải là một object.")
            cfg_id = cfg.get("id")
            if not cfg_id or not isinstance(cfg_id, str) or not cfg_id.strip():
                raise ValueError("Có cấu hình bị thiếu trường 'id' hoặc 'id' không hợp lệ.")
            if cfg_id in seen_ids:
                raise ValueError(f"Phát hiện ID trùng lặp trước khi chấp nhận dữ liệu: '{cfg_id}'")
            seen_ids.add(cfg_id)

        return configs

    # [P1.2. Hoàn thiện FileStorage.save_configs()]
    @staticmethod
    def save_configs(configs, filepath=json_path):
        """Save configs in to JSON safely (via temp file)."""
        filepath = Path(filepath)

        # [YÊU CẦU: Validate toàn bộ payload trước khi ghi]
        if not isinstance(configs, list):
            raise TypeError("Dữ liệu configs phải là một mảng (list).")
        seen_ids = set()
        for cfg in configs:
            if not isinstance(cfg, dict):
                raise TypeError("Mỗi cấu hình trong configs phải là một object (dict).")
            cfg_id = cfg.get("id")
            if not cfg_id or not isinstance(cfg_id, str) or not cfg_id.strip():
                raise ValueError("Có cấu hình bị thiếu 'id' hoặc 'id' không phải chuỗi hợp lệ.")
            if cfg_id in seen_ids:
                raise ValueError(f"Phát hiện ID trùng lặp trước khi lưu: '{cfg_id}'")
            seen_ids.add(cfg_id)

        # [YÊU CẦU: Tạo file tạm duy nhất trong cùng thư mục đích]
        filepath.parent.mkdir(parents=True, exist_ok=True)
        temp_path = filepath.with_name(filepath.name + ".tmp")

        payload = {
            "schema_version": 2,
            "configs": configs
        }

        try:
        # [YÊU CẦU: Ghi UTF-8 và Dùng json.dump(..., allow_nan=False)]
            with open(temp_path, "w", encoding="utf-8") as f:
                json.dump(payload, f, ensure_ascii=False, indent=2, allow_nan=False)

                # [YÊU CẦU: Flush và os.fsync() trước khi replace]
                f.flush()
                os.fsync(f.fileno())

            # [YÊU CẦU: Đóng file tạm trước khi os.replace()]
            os.replace(temp_path, filepath)

        except Exception as e:
            # [YÊU CẦU: Dọn file tạm nếu ghi thất bại & Không làm mất file gốc]
            if temp_path.exists():
                temp_path.unlink()
            raise RuntimeError(f"Ghi file JSON thất bại, giữ nguyên file gốc: {e}")
