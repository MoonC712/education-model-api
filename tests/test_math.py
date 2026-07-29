import numpy as np
import pandas as pd

from education_model.math_utils import (
    fay_brr_standard_error,
    weighted_cronbach_alpha,
    weighted_mean,
    weighted_percentile_rank,
    weighted_quantile,
    weighted_sd,
    weighted_zscore,
)


def test_weighted_quantile_respects_weights():
    x = np.array([0.0, 10.0])
    w = np.array([9.0, 1.0])
    assert weighted_quantile(x, w, 0.5) < 5.0


def test_weighted_zscore_has_mean_zero_sd_one():
    x = np.array([1.0, 2.0, 8.0, 10.0])
    w = np.array([1.0, 2.0, 1.0, 3.0])
    z = weighted_zscore(x, w)
    assert abs(weighted_mean(z, w)) < 1e-12
    assert abs(weighted_sd(z, w) - 1.0) < 1e-12


def test_percentile_rank_is_monotonic_and_bounded():
    x = np.array([1.0, 2.0, 2.0, 5.0])
    w = np.ones(4)
    p = weighted_percentile_rank(x, w)
    assert np.all((p >= 0) & (p <= 100))
    assert p[0] < p[1] == p[2] < p[3]


def test_cronbach_alpha_high_for_parallel_items():
    frame = pd.DataFrame({"a": [1, 2, 3, 4], "b": [2, 4, 6, 8], "c": [1, 2, 3, 4]})
    alpha = weighted_cronbach_alpha(frame, np.ones(4))
    assert alpha > 0.9


def test_fay_brr_formula():
    full = 10.0
    reps = np.array([9.0, 11.0])
    expected = np.sqrt(((1.0 ** 2 + 1.0 ** 2) / (2 * 0.5 ** 2)))
    assert abs(fay_brr_standard_error(full, reps, 0.5) - expected) < 1e-12
