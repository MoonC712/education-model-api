from __future__ import annotations

import numpy as np
import pandas as pd

from education_model.interventions import (
    SimulationOptions,
    compare_policies,
    simulate_intervention,
    simulate_policy_package,
    vector_change_statuses,
)
from education_model.narratives import narrative_codes_to_profile, propose_narrative_codes
from education_model.narrative_validation import full_validation_report


DIMENSIONS = ["resources", "human_support", "digital_access", "learning_agency", "wellbeing"]


def model_manifest():
    return {
        "dataset": {"student_weight": "W_FSTUWT"},
        "dimensions": {
            "resources": {"minimum_nonmissing": 2, "indicators": [{"variable": "HOMEPOS"}, {"variable": "EDUSHORT"}]},
            "human_support": {"minimum_nonmissing": 2, "indicators": [{"variable": "FAMSUP"}, {"variable": "TEACHSUP"}]},
            "digital_access": {"minimum_nonmissing": 2, "indicators": [{"variable": "ICTHOME"}, {"variable": "ICTQUAL"}, {"variable": "ICTENQ"}]},
            "learning_agency": {"minimum_nonmissing": 2, "indicators": [{"variable": "GROSAGR"}, {"variable": "MATHEFF"}, {"variable": "MATHPERS"}]},
            "wellbeing": {"minimum_nonmissing": 2, "indicators": [{"variable": "BELONG"}, {"variable": "LIFESAT"}, {"variable": "ANXMAT"}]},
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


def intervention_manifest():
    return {
        "interventions": {
            "home": {
                "enabled": True,
                "label": "Home access",
                "kind": "direct_target",
                "targets": [{"indicator": "DIGITAL_ACCESS__ICTHOME__Z", "target_percentile": 0.9}],
                "implementation_months": 6,
                "evidence_followup_months": 12,
                "evidence_level": "High",
            },
            "use": {
                "enabled": True,
                "label": "Guided use",
                "kind": "direct_target",
                "targets": [{"indicator": "DIGITAL_ACCESS__ICTENQ__Z", "target_percentile": 0.7}],
                "implementation_months": 6,
                "evidence_followup_months": 12,
                "evidence_level": "High",
            },
        },
        "policy_packages": {
            "digital": {"enabled": True, "label": "Digital package", "components": ["home", "use"]}
        },
    }


def narrative_schema():
    return {
        "levels": ["unknown", "very_low", "low", "typical", "high", "very_high"],
        "level_quantiles": {"very_low": 0.1, "low": 0.25, "typical": 0.5, "high": 0.75, "very_high": 0.9},
        "indicators": {
            "HOMEPOS": {"dimension": "resources", "label": "Home", "patterns": {"high": ["own desk"]}},
            "EDUSHORT": {"dimension": "resources", "label": "School", "patterns": {"low": ["few materials"]}},
            "FAMSUP": {"dimension": "human_support", "label": "Family", "patterns": {"high": ["parents encourage"]}},
            "TEACHSUP": {"dimension": "human_support", "label": "Teacher", "patterns": {"high": ["teacher helps"]}},
            "ICTHOME": {"dimension": "digital_access", "label": "Home ICT", "patterns": {"low": ["shared phone"]}},
            "ICTQUAL": {"dimension": "digital_access", "label": "School ICT", "patterns": {}},
            "ICTENQ": {"dimension": "digital_access", "label": "Use", "patterns": {}},
            "GROSAGR": {"dimension": "learning_agency", "label": "Growth", "patterns": {}},
            "MATHEFF": {"dimension": "learning_agency", "label": "Efficacy", "patterns": {}},
            "MATHPERS": {"dimension": "learning_agency", "label": "Persistence", "patterns": {}},
            "BELONG": {"dimension": "wellbeing", "label": "Belong", "patterns": {}},
            "LIFESAT": {"dimension": "wellbeing", "label": "Life", "patterns": {}},
            "ANXMAT": {"dimension": "wellbeing", "label": "Anxiety", "patterns": {}},
        },
    }


def test_time_horizon_scales_implementation():
    ref = reference_frame()
    profile = ref.iloc[2]
    early = simulate_intervention(profile, ref, model_manifest(), intervention_manifest(), "home", SimulationOptions(horizon_months=1))
    full = simulate_intervention(profile, ref, model_manifest(), intervention_manifest(), "home", SimulationOptions(horizon_months=6))
    assert 0 < early["vector_change"]["digital_access"] < full["vector_change"]["digital_access"]
    expected_early = 1 - 2 ** (-1 / 6)
    expected_six = 1 - 2 ** (-6 / 6)
    assert np.isclose(early["time_factor"], expected_early)
    assert np.isclose(full["time_factor"], expected_six)


def test_policy_package_applies_components_sequentially():
    ref = reference_frame()
    result = simulate_policy_package(ref.iloc[2], ref, model_manifest(), intervention_manifest(), "digital", SimulationOptions(horizon_months=6))
    assert len(result["component_results"]) == 2
    assert result["projected_vector"]["digital_access"] > result["baseline_vector"]["digital_access"]


def test_compare_keeps_fit_and_evidence_separate():
    ref = reference_frame()
    table, _ = compare_policies(ref.iloc[2], ref, model_manifest(), intervention_manifest(), SimulationOptions(horizon_months=6))
    assert {"need_alignment_percent", "evidence_level", "expected_total_positive_movement"}.issubset(table.columns)
    assert len(table) == 3


def test_zero_status_distinguishes_already_covered():
    ref = reference_frame()
    result = simulate_intervention(ref.iloc[-1], ref, model_manifest(), intervention_manifest(), "home", SimulationOptions(horizon_months=6))
    statuses = vector_change_statuses(result)
    assert any(item["status"] == "Already covered" for item in statuses)


def test_narrative_proposal_keeps_unmentioned_unknown():
    schema = narrative_schema()
    proposals = propose_narrative_codes("She uses a shared phone. Her parents encourage her.", schema)
    assert proposals["ICTHOME"]["level"] == "low"
    assert proposals["FAMSUP"]["level"] == "high"
    assert proposals["ICTQUAL"]["level"] == "unknown"


def test_narrative_vector_requires_minimum_indicators():
    ref = reference_frame()
    schema = narrative_schema()
    codes = {key: "unknown" for key in schema["indicators"]}
    codes["HOMEPOS"] = "high"
    result = narrative_codes_to_profile(codes, ref, model_manifest(), schema)
    assert result["vector"]["resources"] is None
    codes["EDUSHORT"] = "low"
    result = narrative_codes_to_profile(codes, ref, model_manifest(), schema)
    assert result["vector"]["resources"] is not None


def test_validation_reports_human_and_algorithm_agreement():
    human = pd.DataFrame([
        {"narrative_id": "N1", "coder_id": "A", "indicator": "ICTHOME", "level": "low"},
        {"narrative_id": "N1", "coder_id": "B", "indicator": "ICTHOME", "level": "low"},
        {"narrative_id": "N2", "coder_id": "A", "indicator": "ICTHOME", "level": "unknown"},
        {"narrative_id": "N2", "coder_id": "B", "indicator": "ICTHOME", "level": "unknown"},
    ])
    algorithm = pd.DataFrame([
        {"narrative_id": "N1", "indicator": "ICTHOME", "level": "low"},
        {"narrative_id": "N2", "indicator": "ICTHOME", "level": "unknown"},
    ])
    report = full_validation_report(human, algorithm)
    assert report["human_inter_rater"]["overall_exact_agreement"] == 1.0
    assert report["algorithm_vs_human_consensus"]["unknown_detection_accuracy"] == 1.0
