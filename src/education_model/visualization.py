from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
from sklearn.decomposition import PCA
from sklearn.preprocessing import StandardScaler

from .project_paths import ProjectPaths


DIMENSIONS = [
    "resources",
    "human_support",
    "digital_access",
    "learning_agency",
    "wellbeing",
]

DIMENSION_LABELS = {
    "resources": "Resources",
    "human_support": "Human support",
    "digital_access": "Digital access",
    "learning_agency": "Learning agency",
    "wellbeing": "Wellbeing",
}

GROUP_LABELS = {
    "rural_school__lower_background": "Rural school · lower family background",
    "rural_school__higher_background": "Rural school · higher family background",
    "urban_school__lower_background": "Urban school · lower family background",
    "urban_school__higher_background": "Urban school · higher family background",
    "not_in_four_group_comparison": "Outside four-group comparison",
}


@dataclass(frozen=True)
class ProjectData:
    profiles: pd.DataFrame
    archetypes: pd.DataFrame
    model_manifest: dict[str, Any]
    intervention_manifest: dict[str, Any]
    evidence: pd.DataFrame
    narrative_schema: dict[str, Any]
    narrative_demo: pd.DataFrame
    run_summary: dict[str, Any]


def load_json(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def normalise_group(value: Any) -> str:
    if pd.isna(value) or value is None or str(value).strip() == "":
        return "not_in_four_group_comparison"
    return str(value)


def group_display(value: Any) -> str:
    code = normalise_group(value)
    return GROUP_LABELS.get(code, code.replace("__", " · ").replace("_", " ").title())


def load_project_data(paths: ProjectPaths) -> ProjectData:
    missing = paths.missing_visual_files()
    if missing:
        formatted = "\n".join(f"- {path}" for path in missing)
        raise FileNotFoundError(
            "The visualization files are not ready. Missing:\n"
            f"{formatted}\nRerun the updated pipeline before starting the dashboard."
        )

    profiles = pd.read_csv(paths.profiles)
    archetypes = pd.read_csv(paths.archetypes)
    profiles["ANALYSIS_GROUP"] = profiles["ANALYSIS_GROUP"].map(normalise_group)
    profiles["GROUP_LABEL"] = profiles["ANALYSIS_GROUP"].map(group_display)
    archetypes["GROUP_LABEL"] = archetypes["group"].map(group_display)
    model_manifest = load_json(paths.model_manifest)
    intervention_manifest = load_json(paths.intervention_manifest)
    evidence = pd.read_csv(paths.intervention_evidence)
    narrative_schema = load_json(paths.narrative_schema)
    narrative_demo = pd.read_csv(paths.narrative_demo) if paths.narrative_demo.exists() else pd.DataFrame()
    run_summary = load_json(paths.run_summary) if paths.run_summary.exists() else {}

    required_profile_columns = {"PROFILE_ID", "ANALYSIS_GROUP", *DIMENSIONS}
    missing_columns = sorted(required_profile_columns.difference(profiles.columns))
    if missing_columns:
        raise ValueError(f"Profile file is missing columns: {missing_columns}")
    return ProjectData(
        profiles=profiles,
        archetypes=archetypes,
        model_manifest=model_manifest,
        intervention_manifest=intervention_manifest,
        evidence=evidence,
        narrative_schema=narrative_schema,
        narrative_demo=narrative_demo,
        run_summary=run_summary,
    )


def profile_vector(row: pd.Series) -> dict[str, float | None]:
    result: dict[str, float | None] = {}
    for dimension in DIMENSIONS:
        value = pd.to_numeric(pd.Series([row.get(dimension)]), errors="coerce").iloc[0]
        result[dimension] = None if pd.isna(value) else float(value)
    return result


def profile_indicator_table(row: pd.Series, model_manifest: dict[str, Any]) -> pd.DataFrame:
    records: list[dict[str, Any]] = []
    for dimension, specification in model_manifest["dimensions"].items():
        for indicator in specification["indicators"]:
            column = f"{dimension.upper()}__{indicator['variable']}__Z"
            value = row.get(column, np.nan)
            records.append(
                {
                    "dimension": DIMENSION_LABELS.get(dimension, dimension),
                    "indicator": indicator["variable"],
                    "aligned_z_score": None if pd.isna(value) else float(value),
                    "role": indicator["role"],
                    "direction": "higher = more favourable",
                }
            )
    return pd.DataFrame(records)


def archetypes_wide(archetypes: pd.DataFrame) -> pd.DataFrame:
    required = {"group", "dimension", "weighted_median"}
    if not required.issubset(archetypes.columns):
        raise ValueError(f"Archetype file must include {sorted(required)}")
    wide = archetypes.pivot(index="group", columns="dimension", values="weighted_median").reset_index()
    wide["GROUP_LABEL"] = wide["group"].map(group_display)
    return wide


def simulation_frame(result: dict[str, Any]) -> pd.DataFrame:
    rows = []
    for dimension in DIMENSIONS:
        before = result["baseline_vector"].get(dimension)
        after = result["projected_vector"].get(dimension)
        delta = result["vector_change"].get(dimension)
        rows.append(
            {
                "dimension": dimension,
                "label": DIMENSION_LABELS[dimension],
                "before": before,
                "after": after,
                "change": delta,
            }
        )
    return pd.DataFrame(rows)


def _plain_axis_metadata(component_weights: np.ndarray, explained: float, axis_number: int) -> dict[str, Any]:
    """Create a plain-language label from one oriented PCA component."""
    weights = np.asarray(component_weights, dtype=float)
    absolute = np.abs(weights)
    positive = [i for i in np.argsort(-weights) if weights[i] > 0.12]
    negative = [i for i in np.argsort(weights) if weights[i] < -0.12]

    positive_names = [DIMENSION_LABELS[DIMENSIONS[i]] for i in positive[:2]]
    negative_names = [DIMENSION_LABELS[DIMENSIONS[i]] for i in negative[:2]]

    same_direction = not negative_names or not positive_names
    broad_loading = int((absolute >= 0.25).sum()) >= 4
    if same_direction and broad_loading:
        short_label = "Overall opportunity"
        positive_text = "higher across most of the five dimensions"
        negative_text = "lower across most of the five dimensions"
    elif positive_names and negative_names:
        short_label = f"{' & '.join(positive_names)} vs {' & '.join(negative_names)}"
        positive_text = f"more {' and '.join(positive_names).lower()}"
        negative_text = f"more {' and '.join(negative_names).lower()}"
    else:
        dominant = DIMENSION_LABELS[DIMENSIONS[int(np.argmax(absolute))]]
        short_label = f"Mainly {dominant}"
        if weights[int(np.argmax(absolute))] >= 0:
            positive_text = f"higher {dominant.lower()}"
            negative_text = f"lower {dominant.lower()}"
        else:
            positive_text = f"lower {dominant.lower()}"
            negative_text = f"higher {dominant.lower()}"

    return {
        "axis": f"PC{axis_number}",
        "display_name": f"Axis {axis_number} — {short_label}",
        "short_label": short_label,
        "positive_direction": positive_text,
        "negative_direction": negative_text,
        "explained_variance_ratio": float(explained),
        "loadings": {
            DIMENSIONS[i]: float(weights[i])
            for i in range(len(DIMENSIONS))
        },
    }


def compute_population_embedding(
    profiles: pd.DataFrame,
    components: int = 2,
    max_points: int = 2500,
    random_state: int = 42,
    include_profile_id: str | None = None,
    assigned_only: bool = False,
    include_metadata: bool = False,
):
    """Calculate a PCA population map and optionally return interpretable axis metadata.

    PCA signs are mathematically arbitrary. For reproducible labels, PC1 is oriented so its
    average loading is positive; later axes are oriented so their strongest loading is positive.
    """
    if components not in {2, 3}:
        raise ValueError("components must be 2 or 3")
    required = {"PROFILE_ID", "ANALYSIS_GROUP", *DIMENSIONS}
    missing = required.difference(profiles.columns)
    if missing:
        raise ValueError(f"Profiles are missing columns: {sorted(missing)}")

    working = profiles.copy()
    working["ANALYSIS_GROUP"] = working["ANALYSIS_GROUP"].map(normalise_group)
    if assigned_only:
        working = working.loc[working["ANALYSIS_GROUP"] != "not_in_four_group_comparison"]
    working = working.dropna(subset=DIMENSIONS).copy()
    if working.empty:
        raise ValueError("No complete five-vector profiles are available for PCA.")

    matrix = StandardScaler().fit_transform(working[DIMENSIONS].to_numpy(dtype=float))
    model = PCA(n_components=components, random_state=random_state)
    coordinates = model.fit_transform(matrix)

    oriented_components = model.components_.copy()
    for i in range(components):
        component = oriented_components[i]
        if i == 0:
            sign = 1.0 if component.sum() >= 0 else -1.0
        else:
            strongest = int(np.argmax(np.abs(component)))
            sign = 1.0 if component[strongest] >= 0 else -1.0
        coordinates[:, i] *= sign
        oriented_components[i] *= sign
        working[f"PC{i + 1}"] = coordinates[:, i]

    axis_metadata = [
        _plain_axis_metadata(oriented_components[i], model.explained_variance_ratio_[i], i + 1)
        for i in range(components)
    ]

    if max_points > 0 and len(working) > max_points:
        sampled = working.sample(n=max_points, random_state=random_state)
        if include_profile_id and include_profile_id in set(working["PROFILE_ID"]):
            selected = working.loc[working["PROFILE_ID"] == include_profile_id]
            if include_profile_id not in set(sampled["PROFILE_ID"]):
                sampled = pd.concat([sampled.iloc[:-1], selected.iloc[:1]], ignore_index=True)
        working = sampled

    working["GROUP_LABEL"] = working["ANALYSIS_GROUP"].map(group_display)
    output_columns = ["PROFILE_ID", "ANALYSIS_GROUP", "GROUP_LABEL", *DIMENSIONS]
    output_columns.extend([f"PC{i + 1}" for i in range(components)])
    explained = [float(value) for value in model.explained_variance_ratio_]
    result = working[output_columns].reset_index(drop=True)
    if include_metadata:
        return result, explained, axis_metadata
    return result, explained

def json_safe(value: Any) -> Any:
    """Recursively convert NumPy/Pandas values and NaN into valid JSON values."""
    if isinstance(value, dict):
        return {str(key): json_safe(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [json_safe(item) for item in value]
    if isinstance(value, np.generic):
        value = value.item()
    if isinstance(value, float) and not np.isfinite(value):
        return None
    if pd.isna(value) if not isinstance(value, (dict, list, tuple)) else False:
        return None
    return value
