from __future__ import annotations

from functools import lru_cache
import os
from pathlib import Path
from typing import Literal, Any

import pandas as pd
from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from .interventions import (
    SimulationOptions,
    compare_policies,
    list_interventions,
    list_policy_packages,
    simulate_intervention,
    simulate_policy_package,
    vector_change_statuses,
)
from .narratives import narrative_codes_to_profile, propose_narrative_codes, proposals_to_frame
from .project_paths import ProjectPaths
from .visualization import (
    DIMENSIONS,
    archetypes_wide,
    compute_population_embedding,
    group_display,
    json_safe,
    load_project_data,
    profile_indicator_table,
    profile_vector,
)


class SimulationRequest(BaseModel):
    profile_id: str = Field(min_length=1)
    intervention: str = Field(min_length=1)
    scenario: Literal["conservative", "central", "optimistic"] = "central"
    quality: float = Field(default=1.0, ge=0.0, le=1.0)
    dosage: float = Field(default=1.0, ge=0.0, le=1.0)
    horizon_months: int | None = Field(default=None, ge=0)


class PackageSimulationRequest(BaseModel):
    profile_id: str = Field(min_length=1)
    package: str = Field(min_length=1)
    scenario: Literal["conservative", "central", "optimistic"] = "central"
    quality: float = Field(default=1.0, ge=0.0, le=1.0)
    dosage: float = Field(default=1.0, ge=0.0, le=1.0)
    horizon_months: int | None = Field(default=None, ge=0)


class ComparisonRequest(BaseModel):
    profile_id: str = Field(min_length=1)
    scenario: Literal["conservative", "central", "optimistic"] = "central"
    quality: float = Field(default=1.0, ge=0.0, le=1.0)
    dosage: float = Field(default=1.0, ge=0.0, le=1.0)
    horizon_months: int | None = Field(default=12, ge=0)
    interventions: list[str] | None = None
    packages: list[str] | None = None


class NarrativeProposalRequest(BaseModel):
    text: str = Field(min_length=1)


class NarrativeScoreRequest(BaseModel):
    narrative_id: str = Field(default="NARRATIVE_CASE", min_length=1)
    codes: dict[str, Any]


def _cors_origins() -> list[str]:
    raw = os.getenv(
        "EDU_MODEL_CORS_ORIGINS",
        "http://localhost:3000,http://localhost:5173,http://localhost:8501",
    )
    return [item.strip() for item in raw.split(",") if item.strip()]


def create_app(root: Path | str | None = None) -> FastAPI:
    paths = ProjectPaths.from_root(root)
    app = FastAPI(
        title="Korea Educational Opportunity Model API",
        version="0.4.0",
        description=(
            "Anonymous Korea PISA baseline vectors, transparent policy comparisons, policy packages, "
            "and review-required narrative coding. Outputs are descriptive scenarios, not diagnoses or "
            "guaranteed causal predictions."
        ),
    )

    origins = _cors_origins()
    allow_all = "*" in origins
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"] if allow_all else origins,
        allow_credentials=False,
        allow_methods=["GET", "POST", "OPTIONS"],
        allow_headers=["Content-Type"],
    )

    @lru_cache(maxsize=1)
    def data():
        return load_project_data(paths)

    def selected_profile(profile_id: str) -> pd.Series:
        selected = data().profiles.loc[data().profiles["PROFILE_ID"] == profile_id]
        if selected.empty:
            raise HTTPException(status_code=404, detail="Profile not found")
        return selected.iloc[0]

    def options_from(request: Any) -> SimulationOptions:
        return SimulationOptions(
            request.scenario,
            request.quality,
            request.dosage,
            request.horizon_months,
        )

    @app.get("/")
    def root_endpoint():
        return {
            "name": "Korea Educational Opportunity Model API",
            "docs": "/docs",
            "health": "/health",
            "methodology": "/api/methodology",
        }

    @app.get("/health")
    def health():
        missing = [str(path) for path in paths.missing_visual_files()]
        return {"status": "ok" if not missing else "missing_files", "missing": missing}

    @app.get("/api/methodology")
    def methodology():
        return {
            "baseline": "OECD PISA 2022 public-use student and school microdata for South Korea.",
            "simulation_inspiration": "Transparent scenario-planning approach inspired by UNESCO SimuED; this model is not an official UNESCO product.",
            "narratives": "Supports anonymised user-supplied real-life narratives; included demonstration narratives are synthetic.",
            "limitations": [
                "PISA is cross-sectional.",
                "Vector scores are Korea-relative percentiles.",
                "Intervention outputs are scenario estimates with explicit assumptions.",
                "Automatic narrative coding is a proposal requiring human review and validation.",
            ],
        }

    @app.get("/api/summary")
    def summary():
        project = data()
        profiles = project.profiles
        return json_safe(
            {
                "country": project.run_summary.get("country", "KOR"),
                "profiles": len(profiles),
                "assigned_profiles": int(
                    (profiles["ANALYSIS_GROUP"] != "not_in_four_group_comparison").sum()
                ),
                "dimensions": DIMENSIONS,
                "groups": [
                    {"code": code, "label": group_display(code), "n": int(count)}
                    for code, count in profiles["ANALYSIS_GROUP"].value_counts().items()
                ],
            }
        )

    @app.get("/api/groups")
    def groups():
        project = data()
        wide = archetypes_wide(project.archetypes)
        records = []
        for _, row in wide.iterrows():
            group_code = str(row["group"])
            detail = project.archetypes.loc[project.archetypes["group"] == group_code]
            records.append(
                {
                    "group": group_code,
                    "label": group_display(group_code),
                    "vector": {dimension: row.get(dimension) for dimension in DIMENSIONS},
                    "dimensions": detail[
                        [
                            "dimension",
                            "weighted_median",
                            "standard_error",
                            "ci95_lower",
                            "ci95_upper",
                            "unweighted_n",
                            "effective_n",
                        ]
                    ].to_dict(orient="records"),
                }
            )
        return json_safe({"items": records})

    @app.get("/api/profiles")
    def profiles(
        group: str | None = None,
        assigned_only: bool = True,
        limit: int = Query(default=100, ge=1, le=1000),
        offset: int = Query(default=0, ge=0),
    ):
        project = data()
        frame = project.profiles
        if assigned_only:
            frame = frame.loc[frame["ANALYSIS_GROUP"] != "not_in_four_group_comparison"]
        if group:
            frame = frame.loc[frame["ANALYSIS_GROUP"] == group]
        total = len(frame)
        selected = frame.iloc[offset : offset + limit]
        columns = ["PROFILE_ID", "ANALYSIS_GROUP", "GROUP_LABEL", *DIMENSIONS]
        return json_safe({"total": total, "offset": offset, "limit": limit, "items": selected[columns].to_dict(orient="records")})

    @app.get("/api/profiles/{profile_id}")
    def profile(profile_id: str):
        project = data()
        row = selected_profile(profile_id)
        return json_safe(
            {
                "profile_id": profile_id,
                "analysis_group": row["ANALYSIS_GROUP"],
                "group_label": row["GROUP_LABEL"],
                "vector": profile_vector(row),
                "indicators": profile_indicator_table(row, project.model_manifest).to_dict(orient="records"),
            }
        )

    @app.get("/api/interventions")
    def interventions():
        project = data()
        table = list_interventions(project.intervention_manifest)
        details = project.intervention_manifest["interventions"]
        items = []
        for _, row in table.iterrows():
            key = row["intervention"]
            item = row.to_dict()
            item.update(
                {
                    "method": details[key].get("method_explanation", ""),
                    "assumptions": details[key].get("assumptions", []),
                    "warnings": details[key].get("warnings", []),
                    "time_note": details[key].get("time_note", ""),
                }
            )
            items.append(item)
        return json_safe({"items": items})

    @app.get("/api/packages")
    def packages():
        project = data()
        return json_safe({"items": list_policy_packages(project.intervention_manifest).to_dict(orient="records")})

    @app.get("/api/evidence")
    def evidence():
        return json_safe({"items": data().evidence.to_dict(orient="records")})

    @app.post("/api/simulate")
    def simulate(request: SimulationRequest):
        project = data()
        try:
            result = simulate_intervention(
                profile=selected_profile(request.profile_id),
                reference=project.profiles,
                model_manifest=project.model_manifest,
                intervention_manifest=project.intervention_manifest,
                intervention_key=request.intervention,
                options=options_from(request),
            )
        except (KeyError, ValueError) as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        result["dimension_statuses"] = vector_change_statuses(result)
        return json_safe(result)

    @app.post("/api/simulate-package")
    def simulate_package(request: PackageSimulationRequest):
        project = data()
        try:
            result = simulate_policy_package(
                profile=selected_profile(request.profile_id),
                reference=project.profiles,
                model_manifest=project.model_manifest,
                intervention_manifest=project.intervention_manifest,
                package_key=request.package,
                options=options_from(request),
            )
        except (KeyError, ValueError) as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        return json_safe(result)

    @app.post("/api/compare")
    def compare(request: ComparisonRequest):
        project = data()
        try:
            table, results = compare_policies(
                selected_profile(request.profile_id),
                project.profiles,
                project.model_manifest,
                project.intervention_manifest,
                options=options_from(request),
                intervention_keys=request.interventions,
                package_keys=request.packages,
            )
        except (KeyError, ValueError) as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        return json_safe({"items": table.to_dict(orient="records"), "results": results})

    @app.post("/api/narratives/propose")
    def narrative_propose(request: NarrativeProposalRequest):
        project = data()
        proposals = propose_narrative_codes(request.text, project.narrative_schema)
        return json_safe({
            "proposals": proposals,
            "table": proposals_to_frame(proposals, project.narrative_schema).to_dict(orient="records"),
            "warning": "Automatic codes are proposals only and require human review.",
        })

    @app.post("/api/narratives/score")
    def narrative_score(request: NarrativeScoreRequest):
        project = data()
        try:
            result = narrative_codes_to_profile(
                request.codes,
                project.profiles,
                project.model_manifest,
                project.narrative_schema,
                narrative_id=request.narrative_id,
            )
        except (KeyError, ValueError) as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        result.pop("profile_row", None)
        return json_safe(result)

    @app.get("/api/population-map")
    def population_map(
        components: Literal[2, 3] = 2,
        limit: int = Query(default=2000, ge=100, le=7000),
        assigned_only: bool = False,
        include_profile_id: str | None = None,
    ):
        project = data()
        embedding, explained, axis_metadata = compute_population_embedding(
            project.profiles,
            components=components,
            max_points=limit,
            include_profile_id=include_profile_id,
            assigned_only=assigned_only,
            include_metadata=True,
        )
        return json_safe(
            {
                "components": components,
                "explained_variance_ratio": explained,
                "axis_metadata": axis_metadata,
                "items": embedding.to_dict(orient="records"),
            }
        )

    return app


app = create_app()
