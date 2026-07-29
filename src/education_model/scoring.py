from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd

from .math_utils import (
    weighted_cronbach_alpha,
    weighted_pca_first_component,
    weighted_percentile_rank,
    weighted_spearman,
    weighted_winsorize,
    weighted_zscore,
)


def create_background_groups(frame: pd.DataFrame, manifest: dict) -> tuple[pd.DataFrame, dict]:
    data = frame.copy()
    weight = data[manifest["dataset"]["student_weight"]].to_numpy(dtype=float)
    components = manifest["dataset"]["background_components"]
    z_columns = []
    for variable in components:
        z_name = f"Z_{variable}"
        data[z_name] = weighted_zscore(data[variable], weight)
        z_columns.append(z_name)
    complete = data[z_columns].notna().all(axis=1)
    data["BACKGROUND_INDEX"] = np.nan
    data.loc[complete, "BACKGROUND_INDEX"] = data.loc[complete, z_columns].mean(axis=1)

    from .math_utils import weighted_quantile

    q_low, q_high = weighted_quantile(
        data["BACKGROUND_INDEX"],
        weight,
        [manifest["grouping"]["background_low_quantile"], manifest["grouping"]["background_high_quantile"]]
    )
    data["BACKGROUND_BAND"] = pd.NA
    data.loc[data["BACKGROUND_INDEX"] <= q_low, "BACKGROUND_BAND"] = "lower_background"
    data.loc[data["BACKGROUND_INDEX"] >= q_high, "BACKGROUND_BAND"] = "higher_background"

    location = pd.to_numeric(data[manifest["dataset"]["school_location"]], errors="coerce")
    data["LOCATION_BAND"] = pd.NA
    data.loc[location.isin(manifest["grouping"]["rural_location_codes"]), "LOCATION_BAND"] = "rural_school"
    data.loc[location.isin(manifest["grouping"]["urban_location_codes"]), "LOCATION_BAND"] = "urban_school"

    data["ANALYSIS_GROUP"] = pd.NA
    eligible = data["BACKGROUND_BAND"].notna() & data["LOCATION_BAND"].notna()
    data.loc[eligible, "ANALYSIS_GROUP"] = (
        data.loc[eligible, "LOCATION_BAND"].astype(str) + "__" + data.loc[eligible, "BACKGROUND_BAND"].astype(str)
    )
    return data, {"lower_cut": float(q_low), "upper_cut": float(q_high)}


def build_dimension_scores(frame: pd.DataFrame, manifest: dict) -> tuple[pd.DataFrame, dict]:
    data = frame.copy()
    weight_name = manifest["dataset"]["student_weight"]
    weights = data[weight_name].to_numpy(dtype=float)
    validation: dict = {"dimensions": {}}

    for dimension, specification in manifest["dimensions"].items():
        available = [item for item in specification["indicators"] if item["variable"] in data.columns]
        if len(available) < specification["minimum_nonmissing"]:
            raise ValueError(f"{dimension}: insufficient indicators after audit")
        z_names = []
        for item in available:
            variable = item["variable"]
            aligned = pd.to_numeric(data[variable], errors="coerce").to_numpy(dtype=float) * item["direction"]
            winsorised = weighted_winsorize(aligned, weights)
            z_name = f"{dimension.upper()}__{variable}__Z"
            data[z_name] = weighted_zscore(winsorised, weights)
            z_names.append(z_name)

        valid_counts = data[z_names].notna().sum(axis=1)
        raw_name = f"{dimension.upper()}__RAW"
        data[raw_name] = data[z_names].mean(axis=1, skipna=True)
        data.loc[valid_counts < specification["minimum_nonmissing"], raw_name] = np.nan
        data[dimension] = weighted_percentile_rank(data[raw_name], weights)

        complete = data[z_names].notna().all(axis=1)
        complete_frame = data.loc[complete, z_names]
        complete_weights = data.loc[complete, weight_name]
        alpha = weighted_cronbach_alpha(complete_frame, complete_weights)
        pc_scores, explained, loadings = weighted_pca_first_component(complete_frame, complete_weights)
        equal_scores = complete_frame.mean(axis=1).to_numpy()
        sensitivity_corr = weighted_spearman(equal_scores, pc_scores, complete_weights.to_numpy())

        loo = {}
        if len(z_names) > 2:
            full = data.loc[complete, raw_name].to_numpy()
            for omitted in z_names:
                reduced = data.loc[complete, [z for z in z_names if z != omitted]].mean(axis=1).to_numpy()
                loo[omitted] = weighted_spearman(full, reduced, complete_weights.to_numpy())

        validation["dimensions"][dimension] = {
            "measurement_model": specification.get("measurement_model", "formative"),
            "indicators": [item["variable"] for item in available],
            "complete_case_n": int(complete.sum()),
            "score_coverage": float(data[dimension].notna().mean()),
            "descriptive_cronbach_alpha_not_a_validity_gate": None if not np.isfinite(alpha) else float(alpha),
            "pca_first_component_explained_variance": None if not np.isfinite(explained) else float(explained),
            "equal_weight_vs_pca_spearman": None if not np.isfinite(sensitivity_corr) else float(sensitivity_corr),
            "pca_loadings": {item["variable"]: float(loadings[i]) for i, item in enumerate(available)} if np.isfinite(loadings).all() else {},
            "leave_one_indicator_out_spearman": {key: float(value) for key, value in loo.items() if np.isfinite(value)}
        }
    return data, validation


def save_validation(validation: dict, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        json.dump(validation, handle, indent=2)
