from __future__ import annotations

import argparse
import json
from pathlib import Path

import pandas as pd

from .audit import run_audit
from .io import find_sav, load_manifest, read_korea_school, read_korea_student_chunks
from .profiles import four_group_archetypes, representative_prototypes
from .math_utils import weighted_correlation
from .scoring import build_dimension_scores, create_background_groups, save_validation


def selected_columns(manifest: dict, audit_csv: Path):
    audit = pd.read_csv(audit_csv)
    available = audit[audit["available"].astype(str).str.lower().eq("true")]
    student = available.loc[available["level"] == "student", "variable"].tolist()
    school = available.loc[available["level"] == "school", "variable"].tolist()
    return list(dict.fromkeys(student)), list(dict.fromkeys(school))


def run_pipeline(data_dir: Path, manifest_path: Path, output_dir: Path, prototypes_per_group: int = 3) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    manifest = load_manifest(manifest_path)

    audit_result = run_audit(data_dir, manifest_path, output_dir)
    if not audit_result["passes"]:
        raise RuntimeError("Variable audit failed. Review variable_audit.csv; no scores were generated.")

    student_path = find_sav(data_dir, "student")
    school_path = find_sav(data_dir, "school")
    student_cols, school_cols = selected_columns(manifest, output_dir / "variable_audit.csv")
    country = manifest["dataset"]["country_code"]

    students = read_korea_student_chunks(student_path, student_cols, country_code=country)
    schools = read_korea_school(school_path, school_cols, country_code=country)
    join_keys = manifest["dataset"]["join_keys"]
    merged = students.merge(schools, on=join_keys, how="left", validate="many_to_one", suffixes=("", "_SCHOOL"))

    location = manifest["dataset"]["school_location"]
    if merged[location].isna().all():
        raise ValueError("School location failed to merge; inspect CNT and CNTSCHID key types.")

    grouped, cuts = create_background_groups(merged, manifest)
    grouped = grouped.reset_index(drop=True)
    grouped['PROFILE_ID'] = [f"KOR{i + 1:06d}" for i in range(len(grouped))]
    scored, validation = build_dimension_scores(grouped, manifest)
    validation["grouping"] = {
        "method": "Equal-weight mean of Korea-weighted z-scores for PAREDINT and HISEI; bottom/top quartiles only.",
        "reason": "HOMEPOS is deliberately excluded from grouping to avoid circularly defining the resources score.",
        **cuts
    }
    weight_name = manifest["dataset"]["student_weight"]
    dimension_correlations = {}
    for left_i, left in enumerate(dimensions := list(manifest["dimensions"])):
        for right in dimensions[left_i + 1:]:
            correlation = weighted_correlation(scored[left], scored[right], scored[weight_name])
            dimension_correlations[f"{left}__{right}"] = None if pd.isna(correlation) else float(correlation)
    validation["between_dimension_correlations"] = dimension_correlations
    validation["scoring"] = {
        "indicator_preprocessing": "Direction-aligned, survey-weighted 0.5/99.5% winsorisation, Korea-weighted z-score.",
        "composite": "Equal-weight mean, requiring each dimension's configured minimum non-missing indicators.",
        "display_scale": "Survey-weighted empirical percentile rank from 0 to 100 within Korea.",
        "sensitivity": "Weighted PCA comparison, descriptive Cronbach alpha, leave-one-indicator-out rank correlations, and between-dimension correlations.",
        "measurement_warning": "The dimensions are formative composites. Alpha and PCA are diagnostics, not proof of reliability or construct validity.",
        "important_limit": "PISA is cross-sectional. These scores are descriptive population-relative indices, not individual diagnoses or causal effects."
    }
    save_validation(validation, output_dir / "validation_report.json")

    archetypes = four_group_archetypes(scored, dimensions, manifest)
    prototypes = representative_prototypes(scored, dimensions, manifest, prototypes_per_group)

    public_columns = ['PROFILE_ID', "ANALYSIS_GROUP", *dimensions, manifest["dataset"]["student_weight"]]
    scored[public_columns].to_csv(output_dir / "korea_scored_anonymous.csv.gz", index=False, compression="gzip")

    trace_columns = ['PROFILE_ID', 'ANALYSIS_GROUP', *dimensions, manifest['dataset']['student_weight']]
    for dimension, specification in manifest['dimensions'].items():
        trace_columns.append(f"{dimension.upper()}__RAW")
        trace_columns.extend(
            f"{dimension.upper()}__{item['variable']}__Z"
            for item in specification['indicators']
            if f"{dimension.upper()}__{item['variable']}__Z" in scored.columns
        )
    trace_columns = list(dict.fromkeys(trace_columns))
    scored[trace_columns].to_csv(
        output_dir / 'korea_model_profiles.csv.gz', index=False, compression='gzip'
    )
    archetypes.to_csv(output_dir / "four_group_archetypes.csv", index=False)
    prototypes.to_csv(output_dir / "representative_prototypes.csv", index=False)

    summary = {
        "country": country,
        "student_records_after_filter": int(len(students)),
        "school_records_after_filter": int(len(schools)),
        "merged_records": int(len(merged)),
        "eligible_four_group_records": int(scored["ANALYSIS_GROUP"].notna().sum()),
        "groups": scored["ANALYSIS_GROUP"].value_counts(dropna=True).to_dict(),
        "outputs": [
            "variable_audit.csv",
            "audit_summary.json",
            "validation_report.json",
            "korea_scored_anonymous.csv.gz",
            "four_group_archetypes.csv",
            "representative_prototypes.csv",
            "korea_model_profiles.csv.gz"
        ]
    }
    with (output_dir / "run_summary.json").open("w", encoding="utf-8") as handle:
        json.dump(summary, handle, indent=2)
    print(json.dumps(summary, indent=2))


def main() -> None:
    parser = argparse.ArgumentParser(description="Run Korea PISA phase-1 steps 1–5.")
    parser.add_argument("--data-dir", type=Path, default=Path("data/raw"))
    parser.add_argument("--manifest", type=Path, default=Path("config/indicator_manifest.json"))
    parser.add_argument("--output-dir", type=Path, default=Path("outputs"))
    parser.add_argument("--prototypes-per-group", type=int, default=3)
    args = parser.parse_args()
    run_pipeline(args.data_dir, args.manifest, args.output_dir, args.prototypes_per_group)


if __name__ == "__main__":
    main()
