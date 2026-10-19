"""Regression checks for empty initialization and explicit JSON persistence."""

import json
from pathlib import Path
import sys

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.core.storage import FileStorage
from src.core.manager import ConfigManager


@pytest.fixture
def sample_configs():
    example = ROOT / "docs/examples/junctions_v2.example.json"
    return json.loads(example.read_text(encoding="utf-8"))["configs"]


def test_default_storage_uses_project_data_from_another_working_directory(tmp_path, monkeypatch):
    filepath = ROOT / "data" / "junctions.json"
    original_contents = filepath.read_bytes()
    monkeypatch.chdir(tmp_path)

    configs = FileStorage.load_configs()
    manager = ConfigManager()

    assert manager.filepath == filepath
    assert manager.list() == configs
    assert configs == json.loads(original_contents)["configs"]
    assert filepath.read_bytes() == original_contents
    assert not (tmp_path / "data").exists()


def test_missing_nested_file_creates_empty_v2_and_reloads(tmp_path):
    filepath = tmp_path / "new" / "nested" / "junctions.json"

    assert FileStorage.load_configs(filepath) == []
    assert json.loads(filepath.read_text(encoding="utf-8")) == {
        "schema_version": 2,
        "configs": [],
    }
    first_contents = filepath.read_bytes()

    assert FileStorage.load_configs(filepath) == []
    assert filepath.read_bytes() == first_contents


def test_load_existing_populated_file_preserves_data_and_bytes(tmp_path, sample_configs):
    sample_configs[0]["id"] = "USER-001"
    sample_configs[0]["name"] = "Cấu hình người dùng"
    filepath = tmp_path / "junctions.json"
    payload = {"schema_version": 2, "configs": sample_configs}
    filepath.write_text(
        json.dumps(payload, ensure_ascii=False, indent=4) + "\n",
        encoding="utf-8",
    )
    original_contents = filepath.read_bytes()

    assert FileStorage.load_configs(filepath) == sample_configs
    assert filepath.read_bytes() == original_contents


def test_sample_configs_roundtrip_only_after_explicit_save(tmp_path, sample_configs):
    filepath = tmp_path / "data" / "junctions.json"
    assert FileStorage.load_configs(filepath) == []

    FileStorage.save_configs(sample_configs, filepath)

    assert FileStorage.load_configs(filepath) == sample_configs
    assert json.loads(filepath.read_text(encoding="utf-8")) == {
        "schema_version": 2,
        "configs": sample_configs,
    }
