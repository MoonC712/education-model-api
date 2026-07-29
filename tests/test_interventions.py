from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd

from education_model.interventions import SimulationOptions, simulate_intervention


DIMENSIONS = ["resources", "human_support", "digital_access", "learning_agency", "wellbeing"]


def model_manifest():
    return {
        "dataset": {"student_weight": "W_FSTUWT"},
        "dimensions": {
            "resources": {
                "minimum_nonmissing": 2,
                "indicators": [{"variable": "HOMEPOS"}, {"variable": "EDUSHORT"}],
            },
            "human_support": {
                "minimum_nonmissing": 2,
                "indicators": [{"variable": "FAMSUP"}, {"variable": "TEACHSUP"}],
            },
            "digital_access": {
                "minimum_nonmissing": 2,
                "indicators": [{"variable": "ICTHOME"}, {"variable": "ICTQUAL"}, {"variable": "ICTENQ"}],
            },
            "learning_agency": {
                "minimum_nonmissing": 2,
                "indicators": [{"variable": "GROSAGR"}, {"variable": "MATHEFF"}, {"variable": "MATHPERS"}],
            },
            "wellbeing": {
                "minimum_nonmissing": 2,
                "indicators": [{"variable": "BELONG"}, {"variable": "LIFESAT"}, {"variable": "ANXMAT"}],
            },
        },
    }


def reference_frame():
    rows = []
    for i, z in enumerate(np.linspace(-2, 2, 21)):
        row = {"PROFILE_ID": f"P{i}", "ANALYSIS_GROUP": "g", "W_FSTUWT": 1.0}
        for dimension, spec in model_manifest()["dimensions"].items():
            for item in spec["indicators"]:
                row[f"{dimension.upper()}__{item['variable']}__Z"] = z
            row[f"{dimension.upper()}__RAW"] = z
            row[dimension] = 100 * (i + 0.5) / 21
        rows.append(row)
    return pd.DataFrame(rows)


def simple_manifest(kind="direct_target"):
    target = {"indicator": "DIGITAL_ACCESS__ICTHOME__Z", "target_percentile": 0.9}
    if kind == "standardized_shift":
        target = {
            "indicator": "LEARNING_AGENCY__GROSAGR__Z",
            "conservative_effect_sd": 0.2,
            "central_effect_sd": 0.33,
            "optimistic_effect_sd": 0.4,
            "cap_percentile": 0.95,
        }
    return {
        "interventions": {
            "test": {
                "enabled": True,
                "label": "Test",
                "kind": kind,
                "targets": [target],
                "evidence_level": "test",
            }
        }
    }


def test_direct_target_moves_only_affected_dimension():
    reference = reference_frame()
    profile = reference.iloc[3]
    result = simulate_intervention(
        profile,
        reference,
        model_manifest(),
        simple_manifest("direct_target"),
        "test",
        SimulationOptions(quality=1.0, dosage=1.0),
    )
    assert result["projected_vector"]["digital_access"] > result["baseline_vector"]["digital_access"]
    for dimension in ["resources", "human_support", "learning_agency", "wellbeing"]:
        assert result["projected_vector"][dimension] == result["baseline_vector"][dimension]


def test_zero_quality_produces_no_change():
    reference = reference_frame()
    profile = reference.iloc[3]
    result = simulate_intervention(
        profile,
        reference,
        model_manifest(),
        simple_manifest("direct_target"),
        "test",
        SimulationOptions(quality=0.0, dosage=1.0),
    )
    assert all(abs(value) < 1e-12 for value in result["vector_change"].values())


def test_standardized_shift_uses_scenario_and_cap():
    reference = reference_frame()
    profile = reference.iloc[10]
    result = simulate_intervention(
        profile,
        reference,
        model_manifest(),
        simple_manifest("standardized_shift"),
        "test",
        SimulationOptions(scenario="central", quality=1.0, dosage=1.0),
    )
    change = result["indicator_changes"][0]
    assert np.isclose(change["change_z"], 0.33)
    assert result["projected_vector"]["learning_agency"] > result["baseline_vector"]["learning_agency"]


def test_same_intervention_can_move_profiles_differently():
    reference = reference_frame()
    low = reference.iloc[2]
    high = reference.iloc[16]
    low_result = simulate_intervention(
        low, reference, model_manifest(), simple_manifest(), "test", SimulationOptions()
    )
    high_result = simulate_intervention(
        high, reference, model_manifest(), simple_manifest(), "test", SimulationOptions()
    )
    assert low_result["vector_change"]["digital_access"] > high_result["vector_change"]["digital_access"]


def test_direct_target_above_target_reports_reason():
    reference = reference_frame()
    profile = reference.iloc[20]
    result = simulate_intervention(
        profile,
        reference,
        model_manifest(),
        simple_manifest("direct_target"),
        "test",
        SimulationOptions(),
    )
    assert result["responsive"] is False
    assert result["indicator_changes"][0]["reason_code"] == "already_at_or_above_target"
    assert result["no_change_reasons"]


def test_missing_target_indicator_does_not_invent_baseline():
    reference = reference_frame()
    profile = reference.iloc[3].copy()
    profile["DIGITAL_ACCESS__ICTHOME__Z"] = np.nan
    result = simulate_intervention(
        profile,
        reference,
        model_manifest(),
        simple_manifest("direct_target"),
        "test",
        SimulationOptions(),
    )
    assert result["responsive"] is False
    assert result["indicator_changes"][0]["reason_code"] == "missing_baseline_indicator"
    assert result["indicator_changes"][0]["before_z"] is None
