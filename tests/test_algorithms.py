"""Kiểm thử hợp đồng Poisson và Adaptive bằng implementation thật.

P-05 chỉ kiểm tra phép quy đổi đơn vị.
"""

from itertools import product
from pathlib import Path
import random
import sys
from types import SimpleNamespace

import pytest

# Ứng dụng chạy từ source; test không phụ thuộc thứ tự import của smoke tests.
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.core.algorithms import allocate_green_adaptive, poisson_sample


def test_p05_rate_conversion():
    """18 xe/phút và tick 1 giây tương ứng lambda = 0.3 xe/tick."""
    rate_per_min = 18
    tick_s = 1
    lam = rate_per_min * tick_s / 60
    assert lam == pytest.approx(0.3)


#@pytest.mark.skip(reason="Poisson chưa triển khai trong Task 3; hiện thực ngày 15/10/2026.")
class TestPoissonContract:
    def test_p01_zero_lambda(self):
        rng = random.Random(2026)
        previous_state = rng.getstate()
        result = poisson_sample(0, rng)
        assert type(result) is int
        assert result == 0
        assert rng.getstate() == previous_state

    def test_p02_negative_lambda(self):
        rng = random.Random(2026)
        previous_state = rng.getstate()
        with pytest.raises(ValueError):
            poisson_sample(-0.5, rng)
        assert rng.getstate() == previous_state

    def test_p03_reproducible_seed(self):
        first_rng = random.Random(2026)
        second_rng = random.Random(2026)
        first = [poisson_sample(0.3, first_rng) for _ in range(100)]
        second = [poisson_sample(0.3, second_rng) for _ in range(100)]
        assert first == second

    def test_p04_nonnegative_integer_samples(self):
        rng = random.Random(2026)
        samples = [poisson_sample(0.3, rng) for _ in range(100)]
        assert all(type(sample) is int and sample >= 0 for sample in samples)

    def test_p06_no_global_random_state_change(self):
        global_state = random.getstate()
        rng = random.Random(2026)
        try:
            for _ in range(100):
                poisson_sample(0.3, rng)
            assert random.getstate() == global_state
        finally:
            random.setstate(global_state)

    def test_p07_positive_lambda_consumes_supplied_rng(self):
        rng = random.Random(2026)
        previous_state = rng.getstate()
        poisson_sample(0.3, rng)
        assert rng.getstate() != previous_state

    @pytest.mark.parametrize("lam", [float("nan"), float("inf"), -float("inf")], ids=["nan", "positive-inf", "negative-inf"])
    def test_p08_nonfinite_lambda(self, lam):
        with pytest.raises(ValueError):
            poisson_sample(lam, random.Random(2026))

    @pytest.mark.parametrize("lam", [True, "0.3", None, 0.3j], ids=["bool", "string", "none", "complex"])
    def test_p09_invalid_lambda_type(self, lam):
        with pytest.raises(TypeError):
            poisson_sample(lam, random.Random(2026))

    @pytest.mark.parametrize("rng", [object(), SimpleNamespace(random=1)], ids=["missing-random", "noncallable-random"])
    def test_p10_invalid_rng_interface(self, rng):
        with pytest.raises(TypeError):
            poisson_sample(0.3, rng)


class TestAdaptiveContract:
    @pytest.mark.parametrize(
        "q_ns,q_ew,green_budget,min_green,expected",
        [
            pytest.param(11, 21, 60, 10, (21, 39), id="A-01-reference-21-39"),
            pytest.param(1, 19, 60, 10, (10, 50), id="A-02-minimum-10-50"),
            pytest.param(0, 0, 60, 10, (30, 30), id="A-03-empty-even"),
            pytest.param(0, 0, 61, 10, (30, 31), id="A-04-empty-odd"),
            pytest.param(20, 0, 60, 10, (50, 10), id="A-05-only-ns"),
            pytest.param(0, 20, 60, 10, (10, 50), id="A-06-only-ew"),
            pytest.param(12, 12, 60, 10, (30, 30), id="A-07-balanced"),
            pytest.param(3, 7, 60, 10, (18, 42), id="A-08-ratio"),
            pytest.param(1, 1, 61, 10, (31, 30), id="A-09-half-up-nonempty"),
            pytest.param(1, 19, 20, 10, (10, 10), id="A-10-exact-minimum-budget"),
            pytest.param(1, 5, 60, 10, (10, 50), id="A-11-exact-minimum-share"),
            pytest.param(1, 3, 42, 10, (11, 31), id="A-12-half-up-10-point-5"),
        ],
    )
    def test_expected_allocations(self, q_ns, q_ew, green_budget, min_green, expected):
        result = allocate_green_adaptive(q_ns, q_ew, green_budget, min_green)
        assert result == expected
        assert all(type(duration) is int for duration in result)
        assert sum(result) == green_budget
        assert min(result) >= min_green

    @pytest.mark.parametrize(
        "arguments",
        [
            pytest.param((-1, 0, 60, 10), id="A-13-negative-ns"),
            pytest.param((0, -1, 60, 10), id="A-14-negative-ew"),
            pytest.param((11, 21, 15, 10), id="A-15-insufficient-budget"),
            pytest.param((11, 21, 0, 10), id="A-16-zero-budget"),
            pytest.param((11, 21, -1, 10), id="A-17-negative-budget"),
            pytest.param((11, 21, 60, 0), id="A-18-zero-minimum"),
            pytest.param((11, 21, 60, -1), id="A-19-negative-minimum"),
        ],
    )
    def test_invalid_values(self, arguments):
        with pytest.raises(ValueError):
            allocate_green_adaptive(*arguments)

    @pytest.mark.parametrize("position", range(4), ids=["q-ns", "q-ew", "budget", "minimum"])
    @pytest.mark.parametrize("value", [True, 1.0, "1", None], ids=["bool", "float", "string", "none"])
    def test_a20_invalid_parameter_types(self, position, value):
        arguments = [11, 21, 60, 10]
        arguments[position] = value
        with pytest.raises(TypeError):
            allocate_green_adaptive(*arguments)

    def test_a21_invariants_across_valid_inputs(self):
        for q_ns, q_ew, settings in product([0, 1, 11, 100], [0, 1, 21, 100], [(20, 10), (60, 10), (61, 10)]):
            green_budget, min_green = settings
            result = allocate_green_adaptive(q_ns, q_ew, green_budget, min_green)
            assert isinstance(result, tuple) and len(result) == 2
            assert all(type(duration) is int for duration in result)
            assert sum(result) == green_budget
            assert all(min_green <= duration <= green_budget - min_green for duration in result)
