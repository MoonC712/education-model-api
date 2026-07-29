from __future__ import annotations

import json
from pathlib import Path

import pandas as pd
from fastapi.testclient import TestClient

from education_model.api import create_app
from education_model.visualization import DIMENSIONS


def create_project(root: Path) -> None:
    (root / "outputs").mkdir()
    (root / "config").mkdir()
    profiles = pd.DataFrame(
        [
            {
                "PROFILE_ID": "KOR000001",
                "ANALYSIS_GROUP": "urban_school__lower_background",
                "W_FSTUWT": 1.0,
                **{dimension: (25.0 if dimension == "digital_access" else 50.0) for dimension in DIMENSIONS},
                **{f"{dimension.upper()}__RAW": 0.0 for dimension in DIMENSIONS},
                "RESOURCES__HOMEPOS__Z": 0.0,
                "RESOURCES__EDUSHORT__Z": 0.0,
                "HUMAN_SUPPORT__FAMSUP__Z": 0.0,
                "HUMAN_SUPPORT__TEACHSUP__Z": 0.0,
                "DIGITAL_ACCESS__ICTHOME__Z": -1.0,
                "DIGITAL_ACCESS__ICTQUAL__Z": 0.0,
                "DIGITAL_ACCESS__ICTENQ__Z": 0.0,
                "LEARNING_AGENCY__GROSAGR__Z": 0.0,
                "LEARNING_AGENCY__MATHEFF__Z": 0.0,
                "LEARNING_AGENCY__MATHPERS__Z": 0.0,
                "WELLBEING__BELONG__Z": 0.0,
                "WELLBEING__LIFESAT__Z": 0.0,
                "WELLBEING__ANXMAT__Z": 0.0,
            },
            {
                "PROFILE_ID": "KOR000002",
                "ANALYSIS_GROUP": None,
                "W_FSTUWT": 1.0,
                **{dimension: 75.0 for dimension in DIMENSIONS},
                **{f"{dimension.upper()}__RAW": 1.0 for dimension in DIMENSIONS},
                "RESOURCES__HOMEPOS__Z": 1.0,
                "RESOURCES__EDUSHORT__Z": 1.0,
                "HUMAN_SUPPORT__FAMSUP__Z": 1.0,
                "HUMAN_SUPPORT__TEACHSUP__Z": 1.0,
                "DIGITAL_ACCESS__ICTHOME__Z": 1.0,
                "DIGITAL_ACCESS__ICTQUAL__Z": 1.0,
                "DIGITAL_ACCESS__ICTENQ__Z": 1.0,
                "LEARNING_AGENCY__GROSAGR__Z": 1.0,
                "LEARNING_AGENCY__MATHEFF__Z": 1.0,
                "LEARNING_AGENCY__MATHPERS__Z": 1.0,
                "WELLBEING__BELONG__Z": 1.0,
                "WELLBEING__LIFESAT__Z": 1.0,
                "WELLBEING__ANXMAT__Z": 1.0,
            },
        ]
    )
    profiles.to_csv(root / "outputs" / "korea_model_profiles.csv.gz", index=False, compression="gzip")
    archetype_rows = []
    for dimension in DIMENSIONS:
        archetype_rows.append({
            "group": "urban_school__lower_background",
            "dimension": dimension,
            "weighted_median": 50.0,
            "standard_error": 1.0,
            "ci95_lower": 48.0,
            "ci95_upper": 52.0,
            "unweighted_n": 1,
            "effective_n": 1.0,
        })
    pd.DataFrame(archetype_rows).to_csv(root / "outputs" / "four_group_archetypes.csv", index=False)
    (root / "outputs" / "run_summary.json").write_text(json.dumps({"country": "KOR"}))

    model_manifest = {
        "dataset": {"student_weight": "W_FSTUWT"},
        "dimensions": {
            "resources": {"minimum_nonmissing": 2, "indicators": [{"variable": "HOMEPOS", "role": "home"}, {"variable": "EDUSHORT", "role": "school"}]},
            "human_support": {"minimum_nonmissing": 2, "indicators": [{"variable": "FAMSUP", "role": "family"}, {"variable": "TEACHSUP", "role": "teacher"}]},
            "digital_access": {"minimum_nonmissing": 2, "indicators": [{"variable": "ICTHOME", "role": "home ICT"}, {"variable": "ICTQUAL", "role": "quality"}, {"variable": "ICTENQ", "role": "use"}]},
            "learning_agency": {"minimum_nonmissing": 2, "indicators": [{"variable": "GROSAGR", "role": "mindset"}, {"variable": "MATHEFF", "role": "efficacy"}, {"variable": "MATHPERS", "role": "persistence"}]},
            "wellbeing": {"minimum_nonmissing": 2, "indicators": [{"variable": "BELONG", "role": "belonging"}, {"variable": "LIFESAT", "role": "satisfaction"}, {"variable": "ANXMAT", "role": "anxiety"}]},
        },
    }
    (root / "config" / "indicator_manifest.json").write_text(json.dumps(model_manifest))
    narrative_schema = {
        "levels": ["unknown", "very_low", "low", "typical", "high", "very_high"],
        "level_quantiles": {"very_low": 0.1, "low": 0.25, "typical": 0.5, "high": 0.75, "very_high": 0.9},
        "indicators": {
            item["variable"]: {"dimension": dimension, "label": item["variable"], "description": "test", "patterns": {}}
            for dimension, spec in model_manifest["dimensions"].items()
            for item in spec["indicators"]
        },
    }
    (root / "config" / "narrative_schema.json").write_text(json.dumps(narrative_schema))
    intervention_manifest = {
        "interventions": {
            "laptop_internet_package": {
                "enabled": True,
                "label": "Laptop + internet",
                "kind": "direct_target",
                "evidence_level": "test",
                "direct_vector_claim": "test",
                "targets": [{"indicator": "DIGITAL_ACCESS__ICTHOME__Z", "target_percentile": 0.9}],
                "assumptions": [],
                "warnings": [],
            }
        }
    }
    (root / "config" / "intervention_manifest.json").write_text(json.dumps(intervention_manifest))
    pd.DataFrame([{"intervention": "laptop_internet_package", "source": "test"}]).to_csv(
        root / "config" / "intervention_evidence.csv", index=False
    )


def test_api_health_and_profile(tmp_path: Path):
    create_project(tmp_path)
    client = TestClient(create_app(tmp_path))
    assert client.get("/health").json()["status"] == "ok"
    response = client.get("/api/profiles/KOR000001")
    assert response.status_code == 200
    assert response.json()["vector"]["digital_access"] == 25.0


def test_api_simulate(tmp_path: Path):
    create_project(tmp_path)
    client = TestClient(create_app(tmp_path))
    response = client.post(
        "/api/simulate",
        json={"profile_id": "KOR000001", "intervention": "laptop_internet_package"},
    )
    assert response.status_code == 200
    assert response.json()["responsive"] is True
