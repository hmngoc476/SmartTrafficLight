"""Validation và roundtrip cấu hình Models."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import json
import pytest
from src.models.config import Config, Motion2DConfig


def test_roundtrip_and_independent_defaults():
    a, b = Config(), Config()
    assert Config.from_dict(json.loads(json.dumps(a.to_dict()))) == a
    a.arrival_rates['N'] = 20
    a.motion2d.min_gap_m = 3
    assert b.arrival_rates['N'] == 10
    assert b.motion2d.min_gap_m == 2
    data = b.to_dict()
    data['initial_queue']['N'] = 9
    assert b.initial_queue['N'] == 0


@pytest.mark.parametrize('value', [-1, 31, float('nan'), float('inf'), True, '10'])
def test_bad_rates(value):
    with pytest.raises((ValueError, TypeError)):
        Config(arrival_rates=dict(N=value, S=0, E=0, W=0))


@pytest.mark.parametrize('value', [-1, 101, 1.5, True, '1'])
def test_bad_initial_queue(value):
    with pytest.raises((ValueError, TypeError)):
        Config(initial_queue=dict(N=value, S=0, E=0, W=0))


@pytest.mark.parametrize('field', ['arrival_rates', 'initial_queue'])
def test_directions(field):
    for value in ({'N': 0}, dict.fromkeys(('N', 'S', 'E', 'W', 'X'), 0)):
        with pytest.raises(ValueError):
            Config(**{field: value})


@pytest.mark.parametrize('field,value', [
    ('id', ' '), ('name', ''), ('id', 1), ('min_green_s', 0),
    ('yellow_s', 0), ('all_red_s', 0), ('startup_delay_s', -1),
    ('headway_s', 0), ('cycles_to_run', 0), ('cycles_to_run', 101),
    ('cycles_to_run', True), ('seed', True), ('seed', 1.5),
    ('green_budget_s', float('inf')), ('motion2d', {}),
])
def test_bad_fields(field, value):
    with pytest.raises((ValueError, TypeError)):
        Config(**{field: value})


def test_budget_and_boundaries():
    with pytest.raises(ValueError):
        Config(green_budget_s=15, min_green_s=10)
    Config(green_budget_s=20, min_green_s=10, seed=-1,
           arrival_rates=dict(N=0, S=30, E=1, W=0),
           initial_queue=dict(N=0, S=100, E=1, W=0))
    Motion2DConfig(dt_s=0.2, min_gap_m=0, stop_margin_m=0)
    Motion2DConfig(dt_s=1)


@pytest.mark.parametrize('field', list(Motion2DConfig.__dataclass_fields__))
@pytest.mark.parametrize('value', [float('nan'), float('inf'), True, '1'])
def test_bad_motion_values(field, value):
    with pytest.raises((ValueError, TypeError)):
        Motion2DConfig(**{field: value})


@pytest.mark.parametrize('field,value', [
    ('dt_s', 0), ('dt_s', 1.1), ('dt_s', 0.3), ('dt_s', 1e-320),
    ('vehicle_length_m', 0), ('min_gap_m', -1), ('max_speed_mps', 0),
    ('accel_mps2', 0), ('approach_visible_m', 0),
    ('intersection_width_m', 0), ('stop_margin_m', -1), ('clearance_limit_s', 0),
])
def test_motion_bounds(field, value):
    with pytest.raises(ValueError):
        Motion2DConfig(**{field: value})


def test_schema_and_revalidation():
    for data in ({}, {**Config().to_dict(), 'unknown': 1}):
        with pytest.raises(ValueError):
            Config.from_dict(data)
    data = Config().to_dict()
    data['motion2d'] = {}
    with pytest.raises(ValueError):
        Config.from_dict(data)
    config = Config()
    config.headway_s = -1
    with pytest.raises(ValueError):
        config.to_dict()
