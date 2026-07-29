from __future__ import annotations

import numpy as np
import pandas as pd

from education_model.visualization import (
    DIMENSIONS,
    archetypes_wide,
    compute_population_embedding,
    json_safe,
    normalise_group,
)


def sample_profiles(n: int = 20) -> pd.DataFrame:
    rng = np.random.default_rng(7)
    frame = pd.DataFrame({
        "PROFILE_ID": [f"KOR{i:06d}" for i in range(n)],
        "ANALYSIS_GROUP": ["urban_school__lower_background"] * (n - 1) + [np.nan],
    })
    for dimension in DIMENSIONS:
        frame[dimension] = rng.uniform(0, 100, n)
    return frame


def test_normalise_group_handles_nan():
    assert normalise_group(np.nan) == "not_in_four_group_comparison"


def test_embedding_has_selected_profile_and_components():
    profiles = sample_profiles(50)
    embedding, explained = compute_population_embedding(
        profiles,
        components=3,
        max_points=10,
        include_profile_id="KOR000049",
    )
    assert len(embedding) == 10
    assert "KOR000049" in set(embedding["PROFILE_ID"])
    assert {"PC1", "PC2", "PC3"}.issubset(embedding.columns)
    assert len(explained) == 3


def test_archetypes_wide():
    archetypes = pd.DataFrame(
        [
            {"group": "g1", "dimension": dimension, "weighted_median": i + 10}
            for i, dimension in enumerate(DIMENSIONS)
        ]
    )
    wide = archetypes_wide(archetypes)
    assert len(wide) == 1
    assert set(DIMENSIONS).issubset(wide.columns)


def test_json_safe_replaces_non_finite_values():
    converted = json_safe({"a": np.nan, "b": np.float64(2.5), "c": [np.inf, 1]})
    assert converted == {"a": None, "b": 2.5, "c": [None, 1]}


def test_embedding_metadata_has_plain_language_axis_labels():
    profiles = sample_profiles(80)
    embedding, explained, metadata = compute_population_embedding(
        profiles, components=3, max_points=20, include_metadata=True
    )
    assert len(metadata) == 3
    assert metadata[0]["display_name"].startswith("Axis 1")
    assert set(metadata[0]["loadings"]) == set(DIMENSIONS)
    assert np.isclose(sum(explained), sum(item["explained_variance_ratio"] for item in metadata))
