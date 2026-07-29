from __future__ import annotations

import argparse
import json
from pathlib import Path

import pandas as pd

from .interventions import SimulationOptions, load_intervention_manifest, simulate_intervention


def _indicator_columns(dimension: str, manifest: dict) -> list[tuple[str, str]]:
    result = []
    for item in manifest["dimensions"][dimension]["indicators"]:
        column = f"{dimension.upper()}__{item['variable']}__Z"
        result.append((column, item["role"]))
    return result


def _group_label(value) -> str:
    if pd.isna(value):
        return "not_in_four_group_comparison"
    return str(value)


def explain_profile(row: pd.Series, manifest: dict) -> None:
    print("\n" + "=" * 78)
    print(f"PROFILE {row['PROFILE_ID']}   GROUP: {_group_label(row.get('ANALYSIS_GROUP'))}")
    print("=" * 78)
    print("\nFive-vector state (Korea-relative percentiles):")
    for dimension in manifest["dimensions"]:
        value = row.get(dimension)
        print(f"  {dimension:18s}: {value:6.2f}" if pd.notna(value) else f"  {dimension:18s}: missing")

    print("\nHow each score was produced:")
    for dimension in manifest["dimensions"]:
        print(f"\n{dimension.upper()}")
        for column, role in _indicator_columns(dimension, manifest):
            value = row.get(column)
            if pd.notna(value):
                print(f"  {column:38s} {float(value):8.3f}   {role}")
            else:
                print(f"  {column:38s} {'missing':>8s}   {role}")
        raw = row.get(f"{dimension.upper()}__RAW")
        print(
            f"  Equal-weight raw mean of available aligned z-scores: {raw:.3f}"
            if pd.notna(raw)
            else "  Raw mean: missing"
        )
        score = row.get(dimension)
        print(
            f"  Weighted percentile in Korean reference population: {score:.2f}"
            if pd.notna(score)
            else "  Percentile: missing"
        )

    print("\nInterpretation: 70 means this profile is above about 70% of Korea's weighted PISA")
    print("reference population on this constructed dimension. It does not mean '70% sufficient'.")


def _responsive_selection(
    pool: pd.DataFrame,
    reference: pd.DataFrame,
    model_manifest: dict,
    intervention_manifest: dict,
    intervention_key: str,
    options: SimulationOptions,
    n: int,
    seed: int,
) -> pd.DataFrame:
    shuffled = pool.sample(frac=1, random_state=seed)
    rows = []
    for _, row in shuffled.iterrows():
        result = simulate_intervention(
            row,
            reference,
            model_manifest,
            intervention_manifest,
            intervention_key,
            options,
        )
        if not result["responsive"]:
            continue
        record = row.copy()
        for dimension, change in result["vector_change"].items():
            record[f"EXPECTED_{dimension.upper()}_CHANGE"] = change
        rows.append(record)
        if len(rows) >= n:
            break
    return pd.DataFrame(rows)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Inspect anonymous Korea PISA vectors and their indicator-level calculation trace."
    )
    parser.add_argument("--profiles", type=Path, default=Path("outputs/korea_model_profiles.csv.gz"))
    parser.add_argument("--manifest", type=Path, default=Path("config/indicator_manifest.json"))
    parser.add_argument("--prototypes", type=Path, default=Path("outputs/representative_prototypes.csv"))
    parser.add_argument(
        "--intervention-manifest", type=Path, default=Path("config/intervention_manifest.json")
    )
    parser.add_argument("--profile-id", type=str)
    parser.add_argument("--n", type=int, default=8)
    parser.add_argument("--mode", choices=["representative", "first", "random"], default="representative")
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--details", action="store_true")
    parser.add_argument(
        "--include-unassigned",
        action="store_true",
        help="Include students outside the four extreme comparison groups.",
    )
    parser.add_argument(
        "--intervention",
        type=str,
        help="Show only profiles expected to move under this intervention.",
    )
    parser.add_argument("--scenario", choices=["conservative", "central", "optimistic"], default="central")
    parser.add_argument("--quality", type=float, default=1.0)
    parser.add_argument("--dosage", type=float, default=1.0)
    args = parser.parse_args()

    if not args.profiles.exists():
        raise FileNotFoundError(
            f"{args.profiles} does not exist. Install the updated package and rerun the Phase 1 pipeline first."
        )
    with args.manifest.open("r", encoding="utf-8") as handle:
        manifest = json.load(handle)
    profiles = pd.read_csv(args.profiles)

    if args.profile_id:
        matches = profiles.loc[profiles["PROFILE_ID"] == args.profile_id]
        if matches.empty:
            raise ValueError(f"Unknown profile id: {args.profile_id}")
        explain_profile(matches.iloc[0], manifest)
        return

    pool = profiles.copy()
    if not args.include_unassigned:
        pool = pool.loc[pool["ANALYSIS_GROUP"].notna()].copy()
    if pool.empty:
        raise ValueError("No profiles remain after filtering.")

    if args.intervention:
        intervention_manifest = load_intervention_manifest(args.intervention_manifest)
        options = SimulationOptions(args.scenario, args.quality, args.dosage)
        selected = _responsive_selection(
            pool,
            profiles,
            manifest,
            intervention_manifest,
            args.intervention,
            options,
            args.n,
            args.seed,
        )
        if selected.empty:
            print("No responsive profiles were found under these settings.")
            print("Try a different intervention or increase quality/dosage.")
            return
    elif args.mode == "representative" and args.prototypes.exists():
        prototypes = pd.read_csv(args.prototypes)
        ids = prototypes.get("PROFILE_ID", pd.Series(dtype=str)).dropna().astype(str).head(args.n).tolist()
        selected = pool.loc[pool["PROFILE_ID"].isin(ids)].copy()
        selected["_order"] = selected["PROFILE_ID"].map({value: i for i, value in enumerate(ids)})
        selected = selected.sort_values("_order")
        if selected.empty:
            selected = pool.head(args.n)
    elif args.mode == "random":
        selected = pool.sample(n=min(args.n, len(pool)), random_state=args.seed)
    else:
        selected = pool.head(args.n)

    selected = selected.copy()
    selected["ANALYSIS_GROUP"] = selected["ANALYSIS_GROUP"].map(_group_label)
    dimensions = list(manifest["dimensions"])
    columns = ["PROFILE_ID", "ANALYSIS_GROUP", *dimensions]
    expected_columns = [column for column in selected.columns if column.startswith("EXPECTED_")]
    print(selected[columns + expected_columns].to_string(index=False))

    print("\nTo see the complete calculation for one row, run:")
    first_id = selected.iloc[0]["PROFILE_ID"]
    print(f"python -m education_model.inspect_profiles --profile-id {first_id} --details")
    if args.intervention:
        print("\nTo simulate the first responsive profile, run:")
        print(
            f"python -m education_model.simulate --profile-id {first_id} "
            f"--intervention {args.intervention}"
        )

    if args.details:
        for _, row in selected.iterrows():
            explain_profile(row, manifest)


if __name__ == "__main__":
    main()
