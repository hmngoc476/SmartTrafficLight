"""Smoke tests cho cấu trúc V2.3, imports và cấu hình mẫu."""

import importlib
import json
from pathlib import Path
import sys
import tomllib

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
MODULES = {
    "models": ["vehicle", "lane", "signal", "config"],
    "core": ["algorithms", "controller", "geometry", "movement", "simulation", "statistics", "manager", "storage"],
    "ui": ["renderer_2d"],
}


def test_required_structure():
    required = ["src/__init__.py", "src/app.py", "data/junctions.json", ".gitignore", "pyproject.toml", "uv.lock", "README.md", "tests/test_algorithms.py", "tests/test_scaffold.py"]
    for package, modules in MODULES.items():
        required.append(f"src/{package}/__init__.py")
        required.extend(f"src/{package}/{module}.py" for module in modules)
    for name in required:
        assert (ROOT / name).is_file(), name


def test_packages_import():
    importlib.import_module("src")
    for package, modules in MODULES.items():
        importlib.import_module(f"src.{package}")
        for module in modules:
            importlib.import_module(f"src.{package}.{module}")


def test_runtime_json_is_valid_and_preserved():
    from src.core.storage import FileStorage

    path = ROOT / "data/junctions.json"
    original = path.read_bytes()
    data = json.loads(original)
    # Runtime storage may contain saved configs; empty initialization is tested separately.
    assert FileStorage.load_configs(path) == data["configs"]
    assert path.read_bytes() == original


def test_uv_metadata():
    project = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    lock = tomllib.loads((ROOT / "uv.lock").read_text(encoding="utf-8"))
    assert project["project"]["name"] == "smarttrafficlight"
    runtime = {dep.split(">=")[0] for dep in project["project"]["dependencies"]}
    assert {"streamlit", "plotly", "pandas"} <= runtime
    assert any(dep.startswith("pytest") for dep in project["dependency-groups"]["dev"])
    assert {"streamlit", "plotly", "pandas", "pytest"} <= {pkg["name"] for pkg in lock["package"]}
