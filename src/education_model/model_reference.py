from __future__ import annotations

import numpy as np


def percentile_from_weighted_reference(value: float, reference_values, reference_weights) -> float:
    """Map a value to a continuous weighted percentile in a fixed reference distribution.

    At an observed reference value, this matches the midpoint weighted percentile used by the
    baseline scorer. Between observed values it linearly interpolates the weighted CDF. This is
    important for time trajectories: two genuinely different projected raw scores do not collapse
    to the same stepwise percentile merely because no sampled observation lies between them.
    """
    x = np.asarray(reference_values, dtype=float)
    w = np.asarray(reference_weights, dtype=float)
    mask = np.isfinite(x) & np.isfinite(w) & (w > 0)
    x, w = x[mask], w[mask]
    if not len(x) or not np.isfinite(value):
        return float("nan")

    order = np.argsort(x, kind="mergesort")
    x, w = x[order], w[order]

    unique_x, starts = np.unique(x, return_index=True)
    group_weights = np.add.reduceat(w, starts)
    cumulative_before = np.cumsum(group_weights) - group_weights
    midpoint_positions = (cumulative_before + 0.5 * group_weights) / group_weights.sum()

    percentile = np.interp(
        float(value),
        unique_x,
        midpoint_positions,
        left=midpoint_positions[0],
        right=midpoint_positions[-1],
    )
    return float(100.0 * percentile)


def weighted_reference_quantile(reference_values, reference_weights, quantile: float) -> float:
    """Return a weighted quantile from a fixed reference distribution."""
    if not 0 <= quantile <= 1:
        raise ValueError("quantile must be between 0 and 1")
    x = np.asarray(reference_values, dtype=float)
    w = np.asarray(reference_weights, dtype=float)
    mask = np.isfinite(x) & np.isfinite(w) & (w > 0)
    x, w = x[mask], w[mask]
    if not len(x):
        return float("nan")
    order = np.argsort(x, kind="mergesort")
    x, w = x[order], w[order]
    positions = (np.cumsum(w) - 0.5 * w) / w.sum()
    return float(np.interp(quantile, positions, x, left=x[0], right=x[-1]))
