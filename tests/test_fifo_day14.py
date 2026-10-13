"""FIFO nâng cao ngày 14; chỉ dùng public API của Models."""

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from src.models import Lane, Vehicle


def cross_front(lane: Lane, t: float) -> Vehicle:
    vehicle = lane.peek()
    assert vehicle is not None
    vehicle.update_motion(0, 1)
    vehicle.mark_crossed(t)
    assert lane.pop_crossed() is vehicle
    return vehicle


@pytest.mark.parametrize('direction', ['N', 'S', 'E', 'W'])
def test_twenty_vehicles_fifo(direction):
    lane = Lane(direction)
    vehicles = [Vehicle(f'{direction}-{i}', direction, arrival_t=i) for i in range(20)]
    for vehicle in vehicles:
        lane.enqueue(vehicle)
    for i, vehicle in enumerate(vehicles):
        assert lane.count() == 20 - i
        assert lane.peek() is vehicle
        assert lane.peek() is vehicle
        before = lane.get_vehicles()
        with pytest.raises(ValueError):
            lane.pop_crossed()
        assert lane.get_vehicles() == before
        assert cross_front(lane, 20 + i) is vehicle
    assert lane.count() == 0
    assert lane.peek() is None
    assert lane.pop_crossed() is None


def test_new_vehicle_stays_at_tail():
    lane = Lane('N')
    a, b, c = [Vehicle(name, 'N', arrival_t=i) for i, name in enumerate('abc')]
    lane.enqueue(a)
    lane.enqueue(b)
    assert cross_front(lane, 2) is a
    lane.enqueue(c)
    assert lane.get_vehicles() == (b, c)
    assert cross_front(lane, 3) is b
    assert cross_front(lane, 4) is c


def test_four_lanes_counts_and_independence():
    lanes = {d: Lane(d) for d in 'NSEW'}
    sizes = dict(N=7, S=4, E=16, W=5)
    for d, lane in lanes.items():
        for i in range(sizes[d]):
            lane.enqueue(Vehicle(f'{d}-{i}', d, arrival_t=i))
    assert lanes['N'].count() + lanes['S'].count() == 11
    assert lanes['E'].count() + lanes['W'].count() == 21
    for d, lane in lanes.items():
        others = {key: value.get_vehicles() for key, value in lanes.items() if key != d}
        for i in range(sizes[d]):
            assert cross_front(lane, 30 + i).vehicle_id == f'{d}-{i}'
        for key, snapshot in others.items():
            assert lanes[key].get_vehicles() == snapshot


def test_rejections_preserve_queue_and_clocks():
    lane = Lane('N')
    lane.enqueue(Vehicle('a', 'N'))
    lane.reset_green_clock(10, 2, 3)
    before = lane.get_vehicles()
    for vehicle in (Vehicle('b', 'S'), Vehicle('a', 'N')):
        with pytest.raises(ValueError):
            lane.enqueue(vehicle)
        assert lane.get_vehicles() == before
    with pytest.raises(ValueError):
        lane.pop_crossed()
    assert lane.get_vehicles() == before
    assert lane.green_started_at == 10
    assert lane.next_cross_eligible_at == 12


def test_headway_with_new_arrival_and_new_green():
    lane = Lane('N')
    lane.enqueue(Vehicle('a', 'N'))
    lane.reset_green_clock(10, 2, 3)
    assert not lane.is_cross_eligible(11.99)
    assert lane.is_cross_eligible(12)
    cross_front(lane, 12)
    assert not lane.is_cross_eligible(100)  # Queue rỗng.
    lane.enqueue(Vehicle('b', 'N', arrival_t=13))
    assert not lane.is_cross_eligible(14.99)
    assert lane.is_cross_eligible(15)
    lane.reset_green_clock()
    assert not lane.is_cross_eligible(100)
    lane.reset_green_clock(20, 2, 3)
    assert not lane.is_cross_eligible(21.99)
    assert lane.is_cross_eligible(22)
