"""Tích hợp JSON V2 → Config → Adaptive và lưu lại không đổi schema."""

from copy import deepcopy
import json
from pathlib import Path
import sys

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.core.algorithms import allocate_green_adaptive
from src.core.manager import ConfigManager
from src.core.storage import FileStorage
from src.models.config import Config


@pytest.mark.parametrize("enabled", [True, False])
def test_storage_manager_config_adaptive_roundtrip(tmp_path, enabled):
    example = json.loads(
        (ROOT / "docs/examples/junctions_v2.example.json").read_text(encoding="utf-8")
    )["configs"][0]
    payload = deepcopy(example)
    payload["motion_2d"]["enabled"] = enabled
    path = tmp_path / "junctions.json"
    FileStorage.save_configs([payload], path)

    manager = ConfigManager(path)
    config = Config.from_dict(manager.get_config(payload["id"]))
    ns = config.initial_queue["N"] + config.initial_queue["S"]
    ew = config.initial_queue["E"] + config.initial_queue["W"]
    green = allocate_green_adaptive(ns, ew, config.green_budget_s, config.min_green_s)
    assert green == (21, 39)
    assert all(type(duration) is int for duration in green)
    assert sum(green) == config.green_budget_s
    assert config.motion_2d.enabled is enabled

    FileStorage.save_configs([config.to_dict()], path)
    restored = FileStorage.load_configs(path)
    assert restored == [payload]
    assert Config.from_dict(restored[0]) == config
    assert json.loads(path.read_text(encoding="utf-8")) == {
        "schema_version": 2,
        "configs": [payload],
    }


def test_default_config_can_call_adaptive():
    config = Config()
    assert allocate_green_adaptive(
        0, 0, config.green_budget_s, config.min_green_s
    ) == (30, 30)
