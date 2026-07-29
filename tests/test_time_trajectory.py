from __future__ import annotations

import numpy as np
import pandas as pd

from education_model.interventions import SimulationOptions, simulate_intervention, time_response_factor
from education_model.model_reference import percentile_from_weighted_reference


def model_manifest():
    return {
        "dataset": {"student_weight": "W_FSTUWT"},
        "dimensions": {
            "digital_access": {
                "minimum_nonmissing": 2,
                "indicators": [
                    {"variable": "ICTHOME"},
                    {"variable": "ICTQUAL"},
                    {"variable": "ICTENQ"},
                ],
            }
        },
    }


def reference_frame():
    rows = []
    for i, z in enumerate(np.linspace(-2, 2, 101)):
        rows.append({
            "PROFILE_ID": f"P{i}",
            "ANALYSIS_GROUP": "g",
            "W_FSTUWT": 1.0,
            "DIGITAL_ACCESS__ICTHOME__Z": z,
            "DIGITAL_ACCESS__ICTQUAL__Z": -0.2,
            "DIGITAL_ACCESS__ICTENQ__Z": 0.1,
            "DIGITAL_ACCESS__RAW": (z - 0.2 + 0.1) / 3,
            "digital_access": 100 * (i + 0.5) / 101,
        })
    return pd.DataFrame(rows)


def intervention_manifest():
    return {
        "interventions": {
            "laptop": {
                "enabled": True,
                "label": "Laptop",
                "kind": "direct_target",
                "targets": [{"indicator": "DIGITAL_ACCESS__ICTHOME__Z", "target_percentile": 0.9}],
                "time_half_life_months": 3,
                "evidence_followup_months": 12,
            }
        }
    }


def test_saturating_time_factors_are_strictly_distinct():
    intervention = intervention_manifest()["interventions"]["laptop"]
    factors = [time_response_factor(intervention, month)[0] for month in [1, 6, 12, 24]]
    assert factors == sorted(factors)
    assert len({round(value, 12) for value in factors}) == 4
    assert all(0 < value < 1 for value in factors)


def test_responsive_profile_has_four_distinct_time_vectors():
    ref = reference_frame()
    profile = ref.iloc[0]
    values = []
    for month in [1, 6, 12, 24]:
        result = simulate_intervention(
            profile, ref, model_manifest(), intervention_manifest(), "laptop",
            SimulationOptions(horizon_months=month),
        )
        values.append(result["projected_vector"]["digital_access"])
    assert values == sorted(values)
    assert len({round(value, 6) for value in values}) == 4


def test_continuous_percentile_interpolates_between_reference_points():
    x = np.array([0.0, 1.0, 2.0])
    w = np.ones(3)
    p1 = percentile_from_weighted_reference(0.25, x, w)
    p2 = percentile_from_weighted_reference(0.75, x, w)
    assert p1 < p2
    assert np.isclose(percentile_from_weighted_reference(1.0, x, w), 50.0)
