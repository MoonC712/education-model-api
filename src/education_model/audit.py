from __future__ import annotations

import argparse
import json
from pathlib import Path

import pandas as pd

from .io import find_sav, load_manifest, sav_metadata


def run_audit(data_dir: Path, manifest_path: Path, output_dir: Path) -> dict:
    manifest = load_manifest(manifest_path)
    student_path = find_sav(data_dir, "student")
    school_path = find_sav(data_dir, "school")
    student_meta = sav_metadata(student_path)
    school_meta = sav_metadata(school_path)

    rows = []
    required_base = {
        "student": ["CNT", "CNTSCHID", manifest["dataset"]["student_weight"], *manifest["dataset"]["background_components"]],
        "school": ["CNT", "CNTSCHID", manifest["dataset"]["school_location"]]
    }
    prefix = manifest["dataset"]["replicate_weight_prefix"]
    replicate_count = manifest["dataset"]["replicate_count"]
    required_base["student"].extend([f"{prefix}{i}" for i in range(1, replicate_count + 1)])

    for level, variables in required_base.items():
        metadata = student_meta if level == "student" else school_meta
        for variable in variables:
            rows.append({
                "category": "base",
                "dimension": "",
                "variable": variable,
                "level": level,
                "direction": "",
                "role": "required pipeline field",
                "available": variable in metadata,
                "label": metadata.get(variable, "")
            })

    for dimension, specification in manifest["dimensions"].items():
        for item in specification["indicators"]:
            metadata = student_meta if item["level"] == "student" else school_meta
            rows.append({
                "category": "indicator",
                "dimension": dimension,
                "variable": item["variable"],
                "level": item["level"],
                "direction": item["direction"],
                "role": item["role"],
                "available": item["variable"] in metadata,
                "label": metadata.get(item["variable"], "")
            })

    audit = pd.DataFrame(rows)
    output_dir.mkdir(parents=True, exist_ok=True)
    audit.to_csv(output_dir / "variable_audit.csv", index=False)

    base_missing = audit.query("category == 'base' and available == False")["variable"].tolist()
    dimension_summary = {}
    for dimension, specification in manifest["dimensions"].items():
        part = audit[(audit["category"] == "indicator") & (audit["dimension"] == dimension)]
        available = part.loc[part["available"], "variable"].tolist()
        dimension_summary[dimension] = {
            "available": available,
            "missing": part.loc[~part["available"], "variable"].tolist(),
            "minimum_nonmissing": specification["minimum_nonmissing"],
            "passes": len(available) >= specification["minimum_nonmissing"]
        }

    result = {
        "student_file": str(student_path.resolve()),
        "school_file": str(school_path.resolve()),
        "base_missing": base_missing,
        "dimensions": dimension_summary,
        "passes": not base_missing and all(d["passes"] for d in dimension_summary.values())
    }
    with (output_dir / "audit_summary.json").open("w", encoding="utf-8") as handle:
        json.dump(result, handle, indent=2)
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description="Audit PISA files against the phase-1 indicator manifest.")
    parser.add_argument("--data-dir", type=Path, default=Path("data/raw"))
    parser.add_argument("--manifest", type=Path, default=Path("config/indicator_manifest.json"))
    parser.add_argument("--output-dir", type=Path, default=Path("outputs"))
    args = parser.parse_args()
    result = run_audit(args.data_dir, args.manifest, args.output_dir)
    print(json.dumps(result, indent=2))
    if not result["passes"]:
        raise SystemExit("Audit failed. Review outputs/variable_audit.csv before changing the manifest.")


if __name__ == "__main__":
    main()
