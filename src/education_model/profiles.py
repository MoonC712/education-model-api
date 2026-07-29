from __future__ import annotations

import numpy as np
import pandas as pd
from sklearn.cluster import KMeans

from .math_utils import effective_sample_size, fay_brr_standard_error, weighted_quantile


def four_group_archetypes(frame: pd.DataFrame, dimensions: list[str], manifest: dict) -> pd.DataFrame:
    weight_name = manifest["dataset"]["student_weight"]
    prefix = manifest["dataset"]["replicate_weight_prefix"]
    rep_names = [f"{prefix}{i}" for i in range(1, manifest["dataset"]["replicate_count"] + 1)]
    rep_names = [name for name in rep_names if name in frame.columns]
    fay = manifest["dataset"]["fay_factor"]
    rows = []
    groups = sorted(frame["ANALYSIS_GROUP"].dropna().unique())
    for group in groups:
        part = frame.loc[frame["ANALYSIS_GROUP"] == group]
        for dimension in dimensions:
            estimate = weighted_quantile(part[dimension], part[weight_name], 0.5)
            replicate_estimates = [weighted_quantile(part[dimension], part[name], 0.5) for name in rep_names]
            se = fay_brr_standard_error(estimate, replicate_estimates, fay) if rep_names else np.nan
            rows.append({
                "group": group,
                "dimension": dimension,
                "weighted_median": estimate,
                "standard_error": se,
                "ci95_lower": max(0.0, estimate - 1.96 * se) if np.isfinite(se) else np.nan,
                "ci95_upper": min(100.0, estimate + 1.96 * se) if np.isfinite(se) else np.nan,
                "unweighted_n": int(part[dimension].notna().sum()),
                "effective_n": effective_sample_size(part.loc[part[dimension].notna(), weight_name])
            })
    return pd.DataFrame(rows)


def representative_prototypes(
    frame: pd.DataFrame,
    dimensions: list[str],
    manifest: dict,
    prototypes_per_group: int = 3,
    random_state: int = 42
) -> pd.DataFrame:
    weight_name = manifest["dataset"]["student_weight"]
    output = []
    groups = sorted(frame["ANALYSIS_GROUP"].dropna().unique())
    for group in groups:
        selected_columns = [*dimensions, weight_name]
        if 'PROFILE_ID' in frame.columns:
            selected_columns = ['PROFILE_ID', *selected_columns]
        part = frame.loc[frame["ANALYSIS_GROUP"] == group, selected_columns].dropna().copy()
        if len(part) < prototypes_per_group:
            continue
        matrix = part[dimensions].to_numpy(dtype=float)
        weights = part[weight_name].to_numpy(dtype=float)
        model = KMeans(n_clusters=prototypes_per_group, random_state=random_state, n_init=20)
        labels = model.fit_predict(matrix, sample_weight=weights)
        total_weight = weights.sum()
        used_rows = set()
        for cluster in range(prototypes_per_group):
            members = np.flatnonzero(labels == cluster)
            if not len(members):
                continue
            distances = np.linalg.norm(matrix[members] - model.cluster_centers_[cluster], axis=1)
            order = members[np.argsort(distances)]
            exemplar = next((idx for idx in order if idx not in used_rows), order[0])
            used_rows.add(int(exemplar))
            row = {
                "group": group,
                "prototype": f"prototype_{cluster + 1}",
                "population_weight_share_within_group": float(weights[members].sum() / total_weight)
            }
            if 'PROFILE_ID' in part.columns:
                row['PROFILE_ID'] = str(part.iloc[exemplar]['PROFILE_ID'])
            row.update({dimension: float(matrix[exemplar, j]) for j, dimension in enumerate(dimensions)})
            output.append(row)
    return pd.DataFrame(output)
