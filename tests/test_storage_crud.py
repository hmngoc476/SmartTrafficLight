"""CRUD, strict JSON và hồi quy cho ghi đồng thời/ghi thất bại."""

from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
import json
from pathlib import Path
import sys
from threading import Event, Lock

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.core.manager import ConfigManager
from src.core.storage import FileStorage
from src.models.config import Config


def payload(config_id='A'):
    return Config(id=config_id).to_dict()


def test_crud_id_immutability_aliases_and_detached_cache(tmp_path):
    path = tmp_path / 'junctions.json'
    manager = ConfigManager(path)
    data = payload()
    assert manager.create_config(data)[0]
    data['name'] = 'Caller changed'
    assert manager.get('A')['name'] != data['name']
    assert not manager.create(payload())[0]
    assert manager.create(payload('B'))[0]
    assert not manager.update('B', payload('A'))[0]
    changed = payload('B') | {'name': 'Updated'}
    assert manager.update_config('B', changed)[0]
    assert ConfigManager(path).get_config('B')['name'] == 'Updated'
    returned = manager.get('A')
    returned['rates_per_min']['N'] = 30
    listed = manager.list_configs()
    listed[0]['name'] = 'External mutation'
    assert manager.get('A') == payload()
    assert manager.delete_config('B')[0]
    assert not manager.delete('missing')[0]
    assert FileStorage.load_configs(path) == [payload()]


@pytest.mark.parametrize('field,value', [
    ('name', ''), ('green_budget_s', 60.0), ('min_green_s', True),
    ('initial_queue', dict(N=1.5, S=0, E=0, W=0)),
    ('rates_per_min', dict(N=True, S=0, E=0, W=0)),
])
def test_invalid_direct_save_preserves_existing_file(tmp_path, field, value):
    path = tmp_path / 'junctions.json'
    FileStorage.save_configs([payload()], path)
    before = path.read_bytes()
    bad = payload('B') | {field: value}
    with pytest.raises((TypeError, ValueError)):
        FileStorage.save_configs([bad], path)
    assert path.read_bytes() == before
    assert not list(tmp_path.glob('.*.tmp'))


def test_disabled_motion_still_validated_and_missing_fields_not_filled(tmp_path):
    manager = ConfigManager(tmp_path / 'junctions.json')
    bad = payload()
    bad['motion_2d']['enabled'] = False
    bad['motion_2d']['dt_s'] = .3
    assert not manager.create(bad)[0]
    bad = payload()
    del bad['rates_per_min']['N']
    assert not manager.create(bad)[0]
    assert manager.list() == []


@pytest.mark.parametrize('operation', ['create', 'update', 'delete'])
@pytest.mark.parametrize('failure_stage', ['fsync', 'replace'])
def test_write_failure_preserves_disk_cache_and_other_temp_files(tmp_path, monkeypatch, operation, failure_stage):
    from src.core import storage

    path = tmp_path / 'junctions.json'
    manager = ConfigManager(path)
    assert manager.create(payload())[0]
    before_disk, before_cache = path.read_bytes(), manager.list()
    unrelated = tmp_path / 'junctions.json.tmp'
    unrelated.write_text('another operation owns this file')

    def fail(*args):
        raise OSError('simulated write failure')

    monkeypatch.setattr(storage.os, failure_stage, fail)
    actions = {
        'create': lambda: manager.create(payload('B')),
        'update': lambda: manager.update('A', payload() | {'name': 'changed'}),
        'delete': lambda: manager.delete('A'),
    }
    assert not actions[operation]()[0]
    assert path.read_bytes() == before_disk
    assert manager.list() == before_cache
    assert unrelated.read_text() == 'another operation owns this file'
    assert not list(tmp_path.glob('.*.tmp'))


@pytest.mark.parametrize('raw', [
    '{"schema_version":2,"schema_version":2,"configs":[]}',
    '{"schema_version":999,"configs":[]}',
    '{"schema_version":2}', '{"schema_version":2,"configs":{},"extra":0}',
    '{"schema_version":2,"configs":[{"id":"X"}]}',
    '{"schema_version":2,"configs":[],"extra":NaN}',
    '{"schema_version":2,"configs":[],"extra":Infinity}',
])
def test_invalid_load_preserves_bytes(tmp_path, raw):
    path = tmp_path / 'junctions.json'
    path.write_text(raw)
    with pytest.raises((TypeError, ValueError)):
        FileStorage.load_configs(path)
    assert path.read_text() == raw


def test_duplicate_ids_rejected_on_read_and_write(tmp_path):
    path = tmp_path / 'junctions.json'
    FileStorage.save_configs([payload()], path)
    before = path.read_bytes()
    with pytest.raises(ValueError):
        FileStorage.save_configs([payload(), payload() | {'name': 'another'}], path)
    assert path.read_bytes() == before
    path.write_text(json.dumps({'schema_version': 2, 'configs': [payload(), payload()]}))
    with pytest.raises(ValueError):
        ConfigManager(path)


@pytest.mark.parametrize('separate_managers', [False, True])
def test_overlapping_creates_are_serialized_and_keep_both_records(tmp_path, monkeypatch, separate_managers):
    from src.core import storage

    path = tmp_path / 'junctions.json'
    first = ConfigManager(path)
    second = ConfigManager(path) if separate_managers else first
    original_replace = storage.os.replace
    entered, attempted, release, second_replace = Event(), Event(), Event(), Event()
    paths, guard = [], Lock()

    def replace(src, dst):
        with guard:
            paths.append(Path(src))
            order = len(paths)
        if order == 1:
            entered.set()
            assert release.wait(5)
        else:
            second_replace.set()
        original_replace(src, dst)

    def create_second():
        attempted.set()
        return second.create(payload('B'))

    monkeypatch.setattr(storage.os, 'replace', replace)
    with ThreadPoolExecutor(max_workers=2) as pool:
        first_result = pool.submit(first.create, payload('A'))
        assert entered.wait(5)
        second_result = pool.submit(create_second)
        assert attempted.wait(5)
        try:
            overlapped = second_replace.wait(.1)
        finally:
            release.set()
        assert first_result.result(timeout=5)[0]
        assert second_result.result(timeout=5)[0]
    assert not overlapped
    assert len(set(paths)) == 2
    assert all(p.parent == path.parent and p.name != 'junctions.json.tmp' for p in paths)
    assert {item['id'] for item in FileStorage.load_configs(path)} == {'A', 'B'}
    second.reload()
    assert {item['id'] for item in second.list()} == {'A', 'B'}


def test_bad_reload_and_mutation_keep_cache_and_file(tmp_path):
    path = tmp_path / 'junctions.json'
    manager = ConfigManager(path)
    assert manager.create(payload())[0]
    before = deepcopy(manager.list())
    path.write_text('{broken')
    with pytest.raises(ValueError):
        manager.reload()
    assert not manager.create(payload('B'))[0]
    assert manager.list() == before
    assert path.read_text() == '{broken'
