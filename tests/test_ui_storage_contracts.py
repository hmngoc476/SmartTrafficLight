"""Kiểm tra artifacts/schema/fixture Task 5, không kiểm thử CRUD chưa có code."""

from copy import deepcopy
import json
from math import isclose, isfinite
from pathlib import Path
import struct
import xml.etree.ElementTree as ET

import pytest

ROOT = Path(__file__).resolve().parents[1]


def read_json(name):
    def reject_constant(value):
        raise ValueError(f"Non-standard JSON number: {value}")
    return json.loads((ROOT / name).read_text(encoding="utf-8"), parse_constant=reject_constant)


@pytest.fixture
def example():
    return read_json("docs/examples/junctions_v2.example.json")


@pytest.fixture
def validator():
    jsonschema = pytest.importorskip("jsonschema", reason="Công cụ kiểm tra JSON Schema chưa có; không thêm dependency Task 5.")
    schema = read_json("docs/schema/junctions_v2.schema.json")
    jsonschema.Draft202012Validator.check_schema(schema)
    return jsonschema.Draft202012Validator(schema)


def test_example_and_runtime_skeleton_match_schema(example, validator):
    validator.validate(example)
    runtime = read_json("data/junctions.json")
    validator.validate(runtime)
    assert runtime == {"schema_version": 2, "configs": []}
    assert "configurations" not in example


def test_sample_ids_unique_and_business_invariants(example):
    """Chỉ xác nhận dữ liệu mẫu, không thay thế ConfigManager validation."""
    ids = [config["id"] for config in example["configs"]]
    assert all(isinstance(value, str) and value.strip() for value in ids)
    assert len(ids) == len(set(ids))
    for config in example["configs"]:
        assert config["green_budget_s"] >= 2 * config["min_green_s"]
        assert set(config["rates_per_min"]) == set(config["initial_queue"]) == {"N", "S", "E", "W"}
        assert all(type(value) is int for value in config["initial_queue"].values())
        assert all(type(value) in (int, float) and isfinite(value) for value in config["rates_per_min"].values())
        reciprocal = 1 / config["motion_2d"]["dt_s"]
        assert isclose(reciprocal, round(reciprocal), rel_tol=0, abs_tol=1e-9)
        assert round(reciprocal) == 5
    json.dumps(example, allow_nan=False)


def test_schema_does_not_guarantee_id_uniqueness(example, validator):
    duplicate = deepcopy(example["configs"][0])
    duplicate["name"] = "Một tên khác nhưng cùng ID"
    example["configs"].append(duplicate)
    assert validator.is_valid(example)
    ids = [config["id"] for config in example["configs"]]
    assert len(ids) != len(set(ids))  # Manager tương lai phải từ chối riêng.


def test_schema_cross_field_rules_need_manager(example, validator):
    example["configs"][0]["green_budget_s"] = 15
    example["configs"][0]["motion_2d"]["dt_s"] = 0.3
    assert validator.is_valid(example)
    assert example["configs"][0]["green_budget_s"] < 2 * example["configs"][0]["min_green_s"]
    assert not isclose(1 / 0.3, round(1 / 0.3), rel_tol=0, abs_tol=1e-9)


@pytest.mark.parametrize(
    "path,value",
    [
        (("schema_version",), 1),
        (("configs", 0, "id"), ""),
        (("configs", 0, "name"), "   "),
        (("configs", 0, "rates_per_min", "N"), -1),
        (("configs", 0, "rates_per_min", "E"), 31),
        (("configs", 0, "rates_per_min", "N"), True),
        (("configs", 0, "initial_queue", "S"), 2.5),
        (("configs", 0, "initial_queue", "S"), "2"),
        (("configs", 0, "initial_queue", "S"), 101),
        (("configs", 0, "initial_queue", "S"), -1),
        (("configs", 0, "cycles_to_run"), 0),
        (("configs", 0, "cycles_to_run"), 101),
        (("configs", 0, "min_green_s"), 0),
        (("configs", 0, "yellow_s"), 0),
        (("configs", 0, "all_red_s"), 0),
        (("configs", 0, "headway_s"), 0),
        (("configs", 0, "seed"), True),
        (("configs", 0, "motion_2d", "enabled"), 1),
        (("configs", 0, "motion_2d", "dt_s"), 0),
        (("configs", 0, "motion_2d", "dt_s"), 1.1),
        (("configs", 0, "motion_2d", "vehicle_length_m"), 0),
        (("configs", 0, "motion_2d", "min_gap_m"), -1),
        (("configs", 0, "motion_2d", "max_speed_mps"), 0),
        (("configs", 0, "motion_2d", "accel_mps2"), 0),
        (("configs", 0, "motion_2d", "approach_visible_m"), 0),
        (("configs", 0, "motion_2d", "intersection_width_m"), 0),
        (("configs", 0, "motion_2d", "stop_margin_m"), -1),
        (("configs", 0, "motion_2d", "clearance_limit_s"), 0),
    ],
)
def test_schema_rejects_invalid_fixture_values(example, validator, path, value):
    target = example
    for component in path[:-1]:
        target = target[component]
    target[path[-1]] = value
    assert not validator.is_valid(example)


@pytest.mark.parametrize("key", ["schema_version", "configs"])
def test_required_root_fields(example, validator, key):
    del example[key]
    assert not validator.is_valid(example)


def test_missing_direction_and_unofficial_keys(example, validator):
    invalid = deepcopy(example)
    del invalid["configs"][0]["rates_per_min"]["W"]
    assert not validator.is_valid(invalid)
    invalid = deepcopy(example)
    invalid["configs"][0]["rates_per_min"]["X"] = 1
    assert not validator.is_valid(invalid)
    invalid = deepcopy(example)
    invalid["configs"][0]["arrival_rates"] = invalid["configs"][0].pop("rates_per_min")
    assert not validator.is_valid(invalid)
    invalid = deepcopy(example)
    invalid["vehicles"] = []
    assert not validator.is_valid(invalid)


def test_valid_boundary_values(example, validator):
    config = example["configs"][0]
    config["startup_delay_s"] = 0
    config["seed"] = -7
    config["motion_2d"].update(dt_s=1, min_gap_m=0, stop_margin_m=0)
    validator.validate(example)


def test_schema_integer_semantics_need_application_type_check(example, validator):
    example["configs"][0]["initial_queue"]["N"] = 1.0
    assert validator.is_valid(example)  # JSON Schema integer theo giá trị số.
    assert type(example["configs"][0]["initial_queue"]["N"]) is float


def test_wireframe_form_values_match_example(example):
    namespace = "{http://www.w3.org/2000/svg}"
    root = ET.parse(ROOT / "docs/wireframes/tab1_config.svg").getroot()
    labels = [item.text or "" for item in root.findall(namespace + "text")]
    config = example["configs"][0]
    expected = {
        "Tên cấu hình": config["name"],
        "Configuration ID · hệ thống quản lý / chỉ đọc": config["id"],
        "Green Budget · giây": config["green_budget_s"],
        "Min Green · giây": config["min_green_s"],
        "Yellow · giây": config["yellow_s"],
        "All Red · giây": config["all_red_s"],
        "Startup Delay · giây": config["startup_delay_s"],
        "Headway · giây": config["headway_s"],
        "Số chu kỳ · 1–100": config["cycles_to_run"],
        "Random seed · số nguyên": config["seed"],
    }
    for direction in ("N", "S", "E", "W"):
        expected[f"{direction} · xe/phút"] = config["rates_per_min"][direction]
        expected[f"Initial {direction} · xe"] = config["initial_queue"][direction]
    motion_labels = {
        "dt · giây / substep": "dt_s", "Vehicle Length · mét": "vehicle_length_m",
        "Min Gap · mét": "min_gap_m", "Max Speed · m/s": "max_speed_mps",
        "Acceleration · m/s²": "accel_mps2", "Approach Visible · mét": "approach_visible_m",
        "Intersection Width · mét": "intersection_width_m", "Stop Margin · mét": "stop_margin_m",
        "Clearance Limit · giây": "clearance_limit_s",
    }
    expected.update({label: config["motion_2d"][key] for label, key in motion_labels.items()})
    for label, value in expected.items():
        assert labels[labels.index(label) + 1] == str(value), label
    assert config["motion_2d"]["enabled"] is True
    assert "Bật motion 2D · enabled = true" in labels
    simulation_text = " ".join(ET.parse(ROOT / "docs/wireframes/tab2_simulation.svg").getroot().itertext())
    assert config["id"] in simulation_text and config["name"] in simulation_text
    assert "N 12  /  S 9  /  E 18  /  W 7 xe/phút" in simulation_text


@pytest.mark.parametrize("name", ["tab1_config", "tab2_simulation"])
def test_wireframes_are_real_png_and_svg(name):
    png = (ROOT / f"docs/wireframes/{name}.png").read_bytes()
    assert png[:8] == b"\x89PNG\r\n\x1a\n"
    assert struct.unpack(">II", png[16:24]) == (1920, 1080)
    root = ET.parse(ROOT / f"docs/wireframes/{name}.svg").getroot()
    assert root.tag == "{http://www.w3.org/2000/svg}svg"
    assert root.attrib["viewBox"] == "0 0 1920 1080"
    text = " ".join(root.itertext())
    assert "Smart Traffic Light Simulator" in text
    assert "DỮ LIỆU MINH HỌA" in text


def test_tab2_direction_metadata_and_phase():
    root = ET.parse(ROOT / "docs/wireframes/tab2_simulation.svg").getroot()
    stops = {"N": (-2, -8), "S": (2, 8), "E": (8, -2), "W": (-8, 2)}
    vectors = {"N": (0, 1), "S": (0, -1), "E": (-1, 0), "W": (1, 0)}
    for item in root.iter():
        if "data-origin" not in item.attrib:
            continue
        direction, s = item.attrib["data-origin"], float(item.attrib["data-s"])
        stop, vector = stops[direction], vectors[direction]
        assert float(item.attrib["data-front-x"]) == stop[0] + s * vector[0]
        assert float(item.attrib["data-front-y"]) == stop[1] + s * vector[1]
    text = " ".join(root.itertext())
    assert "N/S: GREEN" in text and "E/W: RED" in text
    assert "E/W: GREEN" not in text
