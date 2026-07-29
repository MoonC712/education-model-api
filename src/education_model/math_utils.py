from __future__ import annotations

import numpy as np
import pandas as pd
from scipy.stats import rankdata


def _clean(values, weights):
    x = np.asarray(values, dtype=float)
    w = np.asarray(weights, dtype=float)
    mask = np.isfinite(x) & np.isfinite(w) & (w > 0)
    return x[mask], w[mask], mask


def weighted_mean(values, weights) -> float:
    x, w, _ = _clean(values, weights)
    return float(np.sum(w * x) / np.sum(w)) if len(x) else np.nan


def weighted_variance(values, weights) -> float:
    x, w, _ = _clean(values, weights)
    if not len(x):
        return np.nan
    mean = np.sum(w * x) / np.sum(w)
    return float(np.sum(w * (x - mean) ** 2) / np.sum(w))


def weighted_sd(values, weights) -> float:
    var = weighted_variance(values, weights)
    return float(np.sqrt(var)) if np.isfinite(var) else np.nan


def weighted_quantile(values, weights, quantiles):
    x, w, _ = _clean(values, weights)
    q = np.atleast_1d(np.asarray(quantiles, dtype=float))
    if not len(x):
        return np.full_like(q, np.nan, dtype=float)
    if np.any((q < 0) | (q > 1)):
        raise ValueError("Quantiles must lie between 0 and 1.")
    order = np.argsort(x, kind="mergesort")
    x, w = x[order], w[order]
    positions = (np.cumsum(w) - 0.5 * w) / np.sum(w)
    out = np.interp(q, positions, x, left=x[0], right=x[-1])
    return out if np.ndim(quantiles) else float(out[0])


def weighted_winsorize(values, weights, lower=0.005, upper=0.995):
    x = np.asarray(values, dtype=float).copy()
    lo, hi = weighted_quantile(x, weights, [lower, upper])
    finite = np.isfinite(x)
    x[finite] = np.clip(x[finite], lo, hi)
    return x


def weighted_zscore(values, weights):
    x = np.asarray(values, dtype=float)
    mean = weighted_mean(x, weights)
    sd = weighted_sd(x, weights)
    if not np.isfinite(sd) or sd <= 0:
        return np.full_like(x, np.nan, dtype=float)
    return (x - mean) / sd


def weighted_percentile_rank(values, weights):
    x = np.asarray(values, dtype=float)
    w = np.asarray(weights, dtype=float)
    result = np.full(len(x), np.nan, dtype=float)
    mask = np.isfinite(x) & np.isfinite(w) & (w > 0)
    if not np.any(mask):
        return result
    indices = np.flatnonzero(mask)
    order_local = np.argsort(x[mask], kind="mergesort")
    ordered_indices = indices[order_local]
    ordered_x = x[ordered_indices]
    ordered_w = w[ordered_indices]
    total = ordered_w.sum()
    start = 0
    cumulative_before = 0.0
    while start < len(ordered_x):
        end = start + 1
        while end < len(ordered_x) and ordered_x[end] == ordered_x[start]:
            end += 1
        tie_weight = ordered_w[start:end].sum()
        percentile = 100.0 * (cumulative_before + 0.5 * tie_weight) / total
        result[ordered_indices[start:end]] = percentile
        cumulative_before += tie_weight
        start = end
    return result


def weighted_covariance_matrix(frame: pd.DataFrame, weights) -> np.ndarray:
    matrix = frame.to_numpy(dtype=float)
    w = np.asarray(weights, dtype=float)
    mask = np.isfinite(matrix).all(axis=1) & np.isfinite(w) & (w > 0)
    matrix, w = matrix[mask], w[mask]
    if len(matrix) < 2:
        return np.full((frame.shape[1], frame.shape[1]), np.nan)
    means = np.average(matrix, axis=0, weights=w)
    centered = matrix - means
    return (centered * w[:, None]).T @ centered / w.sum()


def weighted_correlation(x, y, weights) -> float:
    x = np.asarray(x, dtype=float)
    y = np.asarray(y, dtype=float)
    w = np.asarray(weights, dtype=float)
    mask = np.isfinite(x) & np.isfinite(y) & np.isfinite(w) & (w > 0)
    if mask.sum() < 3:
        return np.nan
    x, y, w = x[mask], y[mask], w[mask]
    mx, my = np.average(x, weights=w), np.average(y, weights=w)
    cov = np.average((x - mx) * (y - my), weights=w)
    vx = np.average((x - mx) ** 2, weights=w)
    vy = np.average((y - my) ** 2, weights=w)
    if vx <= 0 or vy <= 0:
        return np.nan
    return float(cov / np.sqrt(vx * vy))


def weighted_spearman(x, y, weights) -> float:
    x = np.asarray(x, dtype=float)
    y = np.asarray(y, dtype=float)
    w = np.asarray(weights, dtype=float)
    mask = np.isfinite(x) & np.isfinite(y) & np.isfinite(w) & (w > 0)
    if mask.sum() < 3:
        return np.nan
    return weighted_correlation(rankdata(x[mask]), rankdata(y[mask]), w[mask])


def weighted_cronbach_alpha(frame: pd.DataFrame, weights) -> float:
    if frame.shape[1] < 2:
        return np.nan
    cov = weighted_covariance_matrix(frame, weights)
    if not np.isfinite(cov).all():
        return np.nan
    k = frame.shape[1]
    total_variance = cov.sum()
    if total_variance <= 0:
        return np.nan
    return float(k / (k - 1) * (1 - np.trace(cov) / total_variance))


def weighted_pca_first_component(frame: pd.DataFrame, weights):
    matrix = frame.to_numpy(dtype=float)
    w = np.asarray(weights, dtype=float)
    mask = np.isfinite(matrix).all(axis=1) & np.isfinite(w) & (w > 0)
    scores = np.full(len(frame), np.nan)
    if mask.sum() < max(3, frame.shape[1] + 1):
        return scores, np.nan, np.full(frame.shape[1], np.nan)
    complete = matrix[mask]
    complete_w = w[mask]
    means = np.average(complete, axis=0, weights=complete_w)
    centered = complete - means
    cov = (centered * complete_w[:, None]).T @ centered / complete_w.sum()
    eigenvalues, eigenvectors = np.linalg.eigh(cov)
    order = np.argsort(eigenvalues)[::-1]
    eigenvalues, eigenvectors = eigenvalues[order], eigenvectors[:, order]
    loading = eigenvectors[:, 0]
    if loading.sum() < 0:
        loading *= -1
    scores[mask] = centered @ loading
    explained = float(eigenvalues[0] / eigenvalues.sum()) if eigenvalues.sum() > 0 else np.nan
    return scores, explained, loading


def effective_sample_size(weights) -> float:
    w = np.asarray(weights, dtype=float)
    w = w[np.isfinite(w) & (w > 0)]
    return float(w.sum() ** 2 / np.sum(w ** 2)) if len(w) else np.nan


def fay_brr_standard_error(full_estimate: float, replicate_estimates, fay_factor=0.5) -> float:
    reps = np.asarray(replicate_estimates, dtype=float)
    reps = reps[np.isfinite(reps)]
    if not len(reps) or not np.isfinite(full_estimate):
        return np.nan
    variance = np.sum((reps - full_estimate) ** 2) / (len(reps) * (1 - fay_factor) ** 2)
    return float(np.sqrt(variance))
