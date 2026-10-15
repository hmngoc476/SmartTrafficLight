"""Minh chứng lịch danh định, không mô phỏng tick hoặc điều khiển clearance."""

from src.models import Config, SignalPlan


def main() -> None:
    plan = SignalPlan.from_config(Config(), 21, 39)
    while (segment := plan.current()) is not None:
        print(f'{segment.code:12} {segment.duration_s:2} s; green={segment.green_directions}')
        plan.move_next()
    print(f'nominal_duration_s={plan.nominal_duration_s}; cycle_end={plan.is_cycle_end()}')


if __name__ == '__main__':
    main()
