"""FIFO, tính nguyên vẹn Queue và hợp đồng clock."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from src.models.deque import Deque
import pytest
from src.models.lane import Lane
from src.models.vehicle import Vehicle


def test_empty_lane():
    lane = Lane('N')
    assert isinstance(lane._queue, Deque)
    assert lane.direction == 'N'
    assert lane.count() == 0
    assert lane.peek() is None
    assert lane.pop_crossed() is None
    assert lane.get_vehicles() == ()
    assert lane.green_started_at is None
    assert lane.next_cross_eligible_at is None
    assert not lane.is_cross_eligible(10)


def test_fifo_and_readonly_view():
    lane = Lane('N')
    vehicles = [Vehicle(str(i), 'N', arrival_t=i) for i in range(3)]
    for v in vehicles:
        lane.enqueue(v)
    view = lane.get_vehicles()
    assert isinstance(view, tuple)
    assert lane.count() == 3
    assert lane.peek() is vehicles[0]
    assert lane.count() == 3
    vehicles[1].update_motion(0, 1)
    vehicles[1].mark_crossed(5)
    with pytest.raises(ValueError):
        lane.pop_crossed()
    assert lane.get_vehicles() == view
    vehicles[0].update_motion(0, 1)
    vehicles[0].mark_crossed(4)
    assert lane.pop_crossed() is vehicles[0]
    assert lane.pop_crossed() is vehicles[1]
    vehicles[2].update_motion(0, 1)
    vehicles[2].mark_crossed(6)
    assert lane.pop_crossed() is vehicles[2]
    assert lane.count() == 0
    assert len(view) == 3


@pytest.mark.parametrize('kind', ['direction', 'duplicate', 'late_arrival', 'crossed', 'type'])
def test_rejected_enqueue_is_atomic(kind):
    lane = Lane('N')
    lane.enqueue(Vehicle('a', 'N', arrival_t=2))
    before = lane.get_vehicles()
    candidate = {
        'direction': Vehicle('b', 'S', arrival_t=3),
        'duplicate': Vehicle('a', 'N', arrival_t=3),
        'late_arrival': Vehicle('b', 'N', arrival_t=1),
        'crossed': Vehicle('b', 'N', arrival_t=3, s_front_m=0),
        'type': 'not a vehicle',
    }[kind]
    if kind == 'crossed':
        candidate.mark_crossed(4)
    with pytest.raises((ValueError, TypeError)):
        lane.enqueue(candidate)
    assert lane.get_vehicles() == before
    assert lane.count() == 1


def test_id_cannot_be_reused_after_pop():
    lane = Lane('N')
    v = Vehicle('a', 'N', s_front_m=0)
    lane.enqueue(v)
    v.mark_crossed(1)
    lane.pop_crossed()
    with pytest.raises(ValueError):
        lane.enqueue(Vehicle('a', 'N', arrival_t=2))
    assert lane.count() == 0


def test_startup_headway_and_reset():
    lane = Lane('N')
    a, b = Vehicle('a', 'N', s_front_m=0), Vehicle('b', 'N')
    lane.enqueue(a)
    lane.enqueue(b)
    assert not lane.is_cross_eligible(100)
    lane.reset_green_clock(10, startup_delay_s=2, headway_s=3)
    assert lane.green_started_at == 10
    assert not lane.is_cross_eligible(11.9)
    assert lane.is_cross_eligible(12)
    a.mark_crossed(12)
    lane.pop_crossed()
    assert lane.next_cross_eligible_at == 15
    assert not lane.is_cross_eligible(14.9)
    assert lane.is_cross_eligible(15)
    lane.reset_green_clock()
    assert lane.next_cross_eligible_at is None
    assert not lane.is_cross_eligible(100)
    lane.reset_green_clock(20, 2, 3)
    assert lane.next_cross_eligible_at == 22
    assert lane.peek() is b


@pytest.mark.parametrize('direction', 'NSEW')
@pytest.mark.parametrize('green_start,startup,expected', [
    (24, 0, 27.6),  # Headway từ pha trước vẫn chưa hết.
    (24, 6, 30),    # Startup của pha mới kết thúc muộn hơn headway.
    (30, 0, 30),    # Headway đã hết trong khoảng đỏ.
])
def test_new_green_keeps_last_crossing_even_after_empty_queue(direction, green_start, startup, expected):
    lane = Lane(direction)
    first = Vehicle('first', direction, s_front_m=0)
    lane.enqueue(first)
    lane.reset_green_clock(0, startup_delay_s=0, headway_s=13)
    first.mark_crossed(14.6)
    assert lane.pop_crossed() is first
    assert lane.count() == 0

    lane.reset_green_clock()
    lane.reset_green_clock()  # Tắt clock nhiều lần không được xóa lịch sử.
    lane.enqueue(Vehicle('next', direction, arrival_t=20))
    assert not lane.is_cross_eligible(100)

    lane.reset_green_clock(green_start, startup_delay_s=startup, headway_s=13)
    assert lane.next_cross_eligible_at == pytest.approx(expected)
    assert not lane.is_cross_eligible(expected - .01)
    assert lane.is_cross_eligible(expected)


@pytest.mark.parametrize('args', [(-1, 0, 1), (1, -1, 1), (1, 0, 0), (True, 0, 1), (float('inf'), 0, 1)])
def test_bad_clock_is_atomic(args):
    lane = Lane('N')
    lane.reset_green_clock(1, 2, 3)
    with pytest.raises((ValueError, TypeError)):
        lane.reset_green_clock(*args)
    assert lane.green_started_at == 1
    assert lane.next_cross_eligible_at == 3


def test_invalid_direction():
    with pytest.raises(ValueError):
        Lane('X')
