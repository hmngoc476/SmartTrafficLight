"""Chạy các kịch bản/seed thật và xuất báo cáo thí nghiệm, độc lập UI/CSV lịch sử."""

import argparse
import json
from pathlib import Path
from statistics import mean, pstdev

from src.core.comparison import compare_policies
from src.models.config import Config, Motion2DConfig


def scenarios() -> dict[str, Config]:
    return {
        'empty': Config(initial_queue=dict.fromkeys('NSEW', 0), rates_per_min=dict.fromkeys('NSEW', 0)),
        'balanced': Config(initial_queue=dict.fromkeys('NSEW', 4), rates_per_min=dict.fromkeys('NSEW', 12)),
        'ns_heavy': Config(initial_queue=dict(N=16, S=12, E=2, W=1), rates_per_min=dict(N=24, S=20, E=6, W=6)),
        'ew_heavy': Config(initial_queue=dict(N=2, S=1, E=16, W=12), rates_per_min=dict(N=6, S=6, E=24, W=20)),
        'peak': Config(initial_queue=dict.fromkeys('NSEW', 100), rates_per_min=dict.fromkeys('NSEW', 30)),
        'clearance': Config(initial_queue=dict(N=20,S=20,E=4,W=4),
                            rates_per_min=dict(N=12,S=12,E=6,W=6),
                            motion_2d=Motion2DConfig(max_speed_mps=2)),
    }


def run_experiment(configs, seeds, horizon_s):
    seeds = tuple(seeds)
    if not seeds:
        raise ValueError('Cần ít nhất một seed.')
    records = []
    for name, config in configs.items():
        for seed in seeds:
            payload = config.to_dict()
            payload['seed'] = seed
            result = compare_policies(Config.from_dict(payload), horizon_s)
            records.append(dict(scenario=name, **result.to_dict()))
    metrics = ('departed_vehicles', 'remaining_vehicles', 'avg_queue', 'avg_wait_departed_s',
               'avg_stopped_delay_s', 'clearance_hold_s', 'cycles_completed')
    aggregates = []
    for name in configs:
        valid = [r for r in records if r['scenario'] == name and r['comparable']]
        for policy in ('adaptive', 'fixed'):
            stats = {}
            for metric in metrics:
                values = [r[policy][metric] for r in valid if r[policy][metric] is not None]
                stats[metric] = dict(samples=len(values), mean=mean(values) if values else None,
                                    population_std=pstdev(values) if values else None)
            aggregates.append(dict(scenario=name, policy=policy, comparable_pairs=len(valid), metrics=stats))
    return dict(horizon_s=horizon_s, seeds=seeds, records=records, aggregates=aggregates)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--horizon', type=int, default=180)
    parser.add_argument('--seeds', type=int, nargs='+', default=list(range(10)))
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    result = run_experiment(scenarios(), args.seeds, args.horizon)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, ensure_ascii=False, allow_nan=False, indent=2), encoding='utf-8')
    print(f"{len(result['records'])} cặp chạy; báo cáo: {args.output}")


if __name__ == '__main__':
    main()
