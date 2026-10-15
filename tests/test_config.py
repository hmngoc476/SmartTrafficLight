"""Validation và JSON roundtrip cấu hình theo hợp đồng V2 của main."""

from copy import deepcopy
import json
from pathlib import Path
import sys

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.models.config import Config, Motion2DConfig

SIGNAL_DURATIONS = (
    'green_budget_s', 'min_green_s', 'yellow_s',
    'all_red_s', 'startup_delay_s', 'headway_s',
)
MOTION_NUMBERS = (
    'dt_s', 'vehicle_length_m', 'min_gap_m', 'max_speed_mps',
    'accel_mps2', 'approach_visible_m', 'intersection_width_m',
    'stop_margin_m', 'clearance_limit_s',
)


@pytest.fixture
def example_config():
    envelope = json.loads(
        (ROOT / 'docs/examples/junctions_v2.example.json').read_text(encoding='utf-8')
    )
    return envelope['configs'][0]


def test_documented_example_roundtrip(example_config):
    config = Config.from_dict(example_config)
    assert config.to_dict() == example_config
    assert Config.from_dict(json.loads(json.dumps(config.to_dict(), allow_nan=False))) == config


def test_roundtrip_matches_json_schema(example_config):
    jsonschema = pytest.importorskip('jsonschema')
    schema = json.loads(
        (ROOT / 'docs/schema/junctions_v2.schema.json').read_text(encoding='utf-8')
    )
    configs = [Config(), Config.from_dict(example_config)]
    jsonschema.Draft202012Validator(schema).validate(
        {'schema_version': 2, 'configs': [config.to_dict() for config in configs]}
    )


def test_canonical_names_and_defaults():
    config = Config()
    data = config.to_dict()
    assert 'rates_per_min' in data and 'motion_2d' in data
    assert 'arrival_rates' not in data and 'motion2d' not in data
    assert config.motion_2d.enabled is True
    assert config.motion_2d.max_speed_mps == 9.0
    assert config.motion_2d.approach_visible_m == 60.0
    assert config.motion_2d.intersection_width_m == 16.0
    assert all(type(getattr(config, name)) is int for name in SIGNAL_DURATIONS)


def test_independent_defaults_and_detached_inputs():
    a, b = Config(), Config()
    a.rates_per_min['N'] = 20
    a.motion_2d.min_gap_m = 3
    assert b.rates_per_min['N'] == 10
    assert b.motion_2d.min_gap_m == 2
    rates = dict(N=12, S=9, E=18, W=7)
    queues = dict(N=7, S=4, E=16, W=5)
    motion = Motion2DConfig()
    config = Config(rates_per_min=rates, initial_queue=queues, motion_2d=motion)
    rates['N'] = 0
    queues['N'] = 0
    motion.max_speed_mps = 1
    assert config.rates_per_min['N'] == 12
    assert config.initial_queue['N'] == 7
    assert config.motion_2d.max_speed_mps == 9
    data = config.to_dict()
    data['rates_per_min']['N'] = 0
    data['initial_queue']['N'] = 0
    data['motion_2d']['enabled'] = False
    assert config.rates_per_min['N'] == 12
    assert config.initial_queue['N'] == 7
    assert config.motion_2d.enabled is True


def test_parser_detaches_input(example_config):
    expected = deepcopy(example_config)
    config = Config.from_dict(example_config)
    example_config['rates_per_min']['N'] = 0
    example_config['initial_queue']['N'] = 0
    example_config['motion_2d']['max_speed_mps'] = 1
    assert config.to_dict() == expected


@pytest.mark.parametrize('value', [-1, 31, float('nan'), float('inf'), True, '10'])
def test_bad_rates(value):
    with pytest.raises((ValueError, TypeError)):
        Config(rates_per_min=dict(N=value, S=0, E=0, W=0))


@pytest.mark.parametrize('value', [-1, 101, 1.0, 1.5, True, '1'])
def test_bad_initial_queue(value):
    with pytest.raises((ValueError, TypeError)):
        Config(initial_queue=dict(N=value, S=0, E=0, W=0))


@pytest.mark.parametrize('field', ['rates_per_min', 'initial_queue'])
def test_directions(field):
    for value in ({'N': 0}, dict.fromkeys(('N', 'S', 'E', 'W', 'X'), 0)):
        with pytest.raises(ValueError):
            Config(**{field: value})


@pytest.mark.parametrize('field,value', [
    ('id', ' '), ('name', ''), ('id', 1), ('min_green_s', 0),
    ('yellow_s', 0), ('all_red_s', 0), ('startup_delay_s', -1),
    ('headway_s', 0), ('cycles_to_run', 0), ('cycles_to_run', 101),
    ('cycles_to_run', True), ('cycles_to_run', 1.0), ('cycles_to_run', '1'),
    ('seed', True), ('seed', 1.0), ('seed', 1.5), ('seed', '1'),
    ('green_budget_s', float('inf')), ('motion_2d', {}),
])
def test_bad_fields(field, value):
    with pytest.raises((ValueError, TypeError)):
        Config(**{field: value})


@pytest.mark.parametrize('field', SIGNAL_DURATIONS)
@pytest.mark.parametrize('value', [60.0, True, False, '60'])
def test_signal_durations_reject_non_integer_types(field, value, example_config):
    with pytest.raises(TypeError):
        Config(**{field: value})
    example_config[field] = value
    with pytest.raises(TypeError):
        Config.from_dict(example_config)


def test_budget_and_boundaries():
    with pytest.raises(ValueError):
        Config(green_budget_s=15, min_green_s=10)
    Config(green_budget_s=20, min_green_s=10, startup_delay_s=0, seed=-1,
           rates_per_min=dict(N=0, S=30, E=1, W=0),
           initial_queue=dict(N=0, S=100, E=1, W=0))
    assert Config(seed=10 ** 1000).seed == 10 ** 1000
    Motion2DConfig(dt_s=0.2, min_gap_m=0, stop_margin_m=0)
    Motion2DConfig(dt_s=1)
    Motion2DConfig(dt_s=1 / 3)
    Motion2DConfig(clearance_limit_s=0.5)


@pytest.mark.parametrize('field', MOTION_NUMBERS)
@pytest.mark.parametrize('value', [float('nan'), float('inf'), True, '1'])
@pytest.mark.parametrize('enabled', [True, False])
def test_bad_motion_values(field, value, enabled):
    with pytest.raises((ValueError, TypeError)):
        Motion2DConfig(enabled=enabled, **{field: value})


@pytest.mark.parametrize('value', [0, 1, 0.0, 1.0, 'true', 'false', None])
def test_enabled_requires_boolean(value, example_config):
    with pytest.raises(TypeError):
        Motion2DConfig(enabled=value)
    example_config['motion_2d']['enabled'] = value
    with pytest.raises(TypeError):
        Config.from_dict(example_config)


@pytest.mark.parametrize('field,value', [
    ('dt_s', 0), ('dt_s', 1.1), ('dt_s', 0.3), ('dt_s', 1e-320),
    ('vehicle_length_m', 0), ('min_gap_m', -1), ('max_speed_mps', 0),
    ('accel_mps2', 0), ('approach_visible_m', 0),
    ('intersection_width_m', 0), ('stop_margin_m', -1), ('clearance_limit_s', 0),
])
@pytest.mark.parametrize('enabled', [True, False])
def test_motion_bounds(field, value, enabled):
    with pytest.raises(ValueError):
        Motion2DConfig(enabled=enabled, **{field: value})


def test_disabled_nondefault_motion_roundtrip(example_config):
    example_config['motion_2d'].update(
        enabled=False, dt_s=0.25, vehicle_length_m=5.1, min_gap_m=1.3,
        max_speed_mps=11.5, accel_mps2=3.2, approach_visible_m=80.0,
        intersection_width_m=18.0, stop_margin_m=0.7, clearance_limit_s=42.5,
    )
    config = Config.from_dict(example_config)
    assert config.motion_2d.enabled is False
    assert config.to_dict() == example_config
    assert Config.from_dict(json.loads(json.dumps(config.to_dict(), allow_nan=False))) == config


@pytest.mark.parametrize('field', ['rates_per_min', 'motion_2d'])
def test_legacy_aliases_are_rejected(field, example_config):
    alias = {'rates_per_min': 'arrival_rates', 'motion_2d': 'motion2d'}[field]
    example_config[alias] = example_config.pop(field)
    with pytest.raises(ValueError):
        Config.from_dict(example_config)


@pytest.mark.parametrize('field', [
    'id', 'name', 'rates_per_min', 'initial_queue', *SIGNAL_DURATIONS,
    'cycles_to_run', 'seed', 'motion_2d',
])
def test_parser_requires_full_config(field, example_config):
    del example_config[field]
    with pytest.raises(ValueError):
        Config.from_dict(example_config)


@pytest.mark.parametrize('field', ['enabled', *MOTION_NUMBERS])
def test_parser_requires_full_motion_config(field, example_config):
    del example_config['motion_2d'][field]
    with pytest.raises(ValueError):
        Config.from_dict(example_config)


def test_schema_and_revalidation():
    for data in ({}, {**Config().to_dict(), 'unknown': 1}):
        with pytest.raises(ValueError):
            Config.from_dict(data)
    data = Config().to_dict()
    data['motion_2d']['unknown'] = 1
    with pytest.raises(ValueError):
        Config.from_dict(data)
    config = Config()
    config.headway_s = -1
    with pytest.raises(ValueError):
        config.to_dict()


def test_serialization_revalidates_mutated_types_and_disabled_parameters():
    config = Config()
    config.green_budget_s = 60.0
    with pytest.raises(TypeError):
        config.to_dict()
    config.green_budget_s = 60
    config.motion_2d.enabled = False
    config.motion_2d.dt_s = 0.3
    with pytest.raises(ValueError):
        config.to_dict()
