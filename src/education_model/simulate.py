from __future__ import annotations

import argparse
import json
from pathlib import Path

import pandas as pd

from .interventions import (
    SimulationOptions,
    list_interventions,
    load_intervention_manifest,
    simulate_intervention,
)


def _print_result(result: dict) -> None:
    print("\n" + "=" * 78)
    print(f"{result['profile_id']} — {result['label']}")
    print("=" * 78)
    group = result.get("analysis_group") or "not_in_four_group_comparison"
    print(f"Group: {group}")
    print(f"Scenario: {result['scenario']} | quality={result['quality']:.2f} | dosage={result['dosage']:.2f}")
    print(f"Responsive under these settings: {'yes' if result['responsive'] else 'no'}")

    print("\nVector movement:")
    for dimension, before in result["baseline_vector"].items():
        after = result["projected_vector"][dimension]
        delta = result["vector_change"][dimension]
        if pd.isna(before) or pd.isna(after) or pd.isna(delta):
            print(f"  {dimension:18s}: missing")
        else:
            print(f"  {dimension:18s}: {before:6.2f} -> {after:6.2f}   ({delta:+6.2f})")

    print("\nIndicator-level calculation:")
    for change in result["indicator_changes"]:
        if change["before_z"] is None:
            print(f"  {change['indicator']}: {change['status']}")
        else:
            proxy = " [PROXY]" if change.get("proxy") else ""
            print(
                f"  {change['indicator']}: {change['before_z']:.3f} -> "
                f"{change['after_z']:.3f} ({change['change_z']:+.3f}){proxy}\n"
                f"      {change['status']}"
            )

    if result.get("no_change_reasons"):
        print("\nWhy no movement occurred:")
        for item in result["no_change_reasons"]:
            print(f"  - {item}")

    if result["outcome_effects"]:
        print("\nSeparate learning-outcome evidence (not a vector score):")
        for effect in result["outcome_effects"]:
            print(f"  {effect['outcome']}: {effect['effect_sd']:+.3f} SD — {effect['note']}")

    print(f"\nEvidence level: {result['evidence_level']}")
    if result["assumptions"]:
        print("Assumptions:")
        for item in result["assumptions"]:
            print(f"  - {item}")
    if result["warnings"]:
        print("Warnings:")
        for item in result["warnings"]:
            print(f"  - {item}")


def _find_auto_profile(
    profiles: pd.DataFrame,
    model_manifest: dict,
    intervention_manifest: dict,
    intervention_key: str,
    options: SimulationOptions,
) -> pd.Series:
    assigned = profiles.loc[profiles["ANALYSIS_GROUP"].notna()]
    pools = [assigned, profiles] if len(assigned) else [profiles]
    checked: set[str] = set()
    for pool in pools:
        for _, row in pool.iterrows():
            profile_id = str(row.get("PROFILE_ID"))
            if profile_id in checked:
                continue
            checked.add(profile_id)
            result = simulate_intervention(
                row,
                profiles,
                model_manifest,
                intervention_manifest,
                intervention_key,
                options,
            )
            if result["responsive"]:
                return row
    raise ValueError("No responsive profile was found for this intervention under the selected settings.")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Simulate evidence-registered interventions on anonymous Korea PISA profiles."
    )
    parser.add_argument("--profiles", type=Path, default=Path("outputs/korea_model_profiles.csv.gz"))
    parser.add_argument("--model-manifest", type=Path, default=Path("config/indicator_manifest.json"))
    parser.add_argument(
        "--intervention-manifest", type=Path, default=Path("config/intervention_manifest.json")
    )
    parser.add_argument("--list", action="store_true", help="List available interventions and exit.")
    parser.add_argument("--profile-id", type=str, help="Use a PROFILE_ID or the word 'auto'.")
    parser.add_argument("--intervention", type=str)
    parser.add_argument("--scenario", choices=["conservative", "central", "optimistic"], default="central")
    parser.add_argument("--quality", type=float, default=1.0)
    parser.add_argument("--dosage", type=float, default=1.0)
    parser.add_argument("--json-output", type=Path)
    args = parser.parse_args()

    intervention_manifest = load_intervention_manifest(args.intervention_manifest)
    if args.list:
        print(list_interventions(intervention_manifest).to_string(index=False))
        return
    if not args.profile_id or not args.intervention:
        parser.error("--profile-id and --intervention are required unless --list is used")
    if not args.profiles.exists():
        raise FileNotFoundError(
            f"{args.profiles} does not exist. Rerun the updated Phase 1 pipeline to create it."
        )

    profiles = pd.read_csv(args.profiles)
    model_manifest = json.loads(args.model_manifest.read_text(encoding="utf-8"))
    options = SimulationOptions(args.scenario, args.quality, args.dosage)

    if args.profile_id.lower() == "auto":
        row = _find_auto_profile(
            profiles,
            model_manifest,
            intervention_manifest,
            args.intervention,
            options,
        )
        print(f"Automatically selected responsive profile: {row['PROFILE_ID']}")
    else:
        selected = profiles.loc[profiles["PROFILE_ID"] == args.profile_id]
        if selected.empty:
            raise ValueError(f"Unknown profile id: {args.profile_id}")
        row = selected.iloc[0]

    result = simulate_intervention(
        profile=row,
        reference=profiles,
        model_manifest=model_manifest,
        intervention_manifest=intervention_manifest,
        intervention_key=args.intervention,
        options=options,
    )
    _print_result(result)
    if args.json_output:
        args.json_output.parent.mkdir(parents=True, exist_ok=True)
        with args.json_output.open("w", encoding="utf-8") as handle:
            json.dump(result, handle, indent=2, ensure_ascii=False, allow_nan=False)
        print(f"\nSaved: {args.json_output}")


if __name__ == "__main__":
    main()
