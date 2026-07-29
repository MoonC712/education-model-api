from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable
import json

import numpy as np
import pandas as pd

from .model_reference import percentile_from_weighted_reference, weighted_reference_quantile


@dataclass(frozen=True)
class SimulationOptions:
    scenario: str = "central"
    quality: float = 1.0
    dosage: float = 1.0
    horizon_months: int | None = None

    def validate(self) -> None:
        if self.scenario not in {"conservative", "central", "optimistic"}:
            raise ValueError("scenario must be conservative, central, or optimistic")
        if not 0 <= self.quality <= 1:
            raise ValueError("quality must be between 0 and 1")
        if not 0 <= self.dosage <= 1:
            raise ValueError("dosage must be between 0 and 1")
        if self.horizon_months is not None and self.horizon_months < 0:
            raise ValueError("horizon_months must be non-negative or None")


def load_intervention_manifest(path: Path | str) -> dict:
    with Path(path).open("r", encoding="utf-8") as handle:
        return json.load(handle)


def _effect_value(target: dict, scenario: str) -> float:
    key = f"{scenario}_effect_sd"
    if key not in target:
        raise KeyError(f"Missing {key} in standardized-shift intervention target")
    return float(target[key])


def _dimension_for_indicator(indicator_column: str, indicator_to_dimension: dict[str, str]) -> str:
    if indicator_column not in indicator_to_dimension:
        raise KeyError(f"Intervention targets unknown indicator column: {indicator_column}")
    return indicator_to_dimension[indicator_column]


def _safe_float(value: Any) -> float:
    try:
        converted = float(value)
    except (TypeError, ValueError):
        return float("nan")
    return converted


def _recalculate_dimension(
    working: dict[str, float],
    dimension: str,
    model_manifest: dict,
    reference: pd.DataFrame,
) -> tuple[float, float]:
    specification = model_manifest["dimensions"][dimension]
    columns = [f"{dimension.upper()}__{item['variable']}__Z" for item in specification["indicators"]]
    values = [_safe_float(working.get(column, np.nan)) for column in columns]
    finite = [value for value in values if np.isfinite(value)]
    if len(finite) < specification["minimum_nonmissing"]:
        return float("nan"), float("nan")
    raw = float(np.mean(finite))
    weight_name = model_manifest["dataset"]["student_weight"]
    reference_raw = reference[f"{dimension.upper()}__RAW"]
    percentile = percentile_from_weighted_reference(raw, reference_raw, reference[weight_name])
    return raw, percentile


def time_response_factor(intervention: dict, horizon_months: int | None) -> tuple[float, list[str]]:
    """Return the programme's saturating implementation/adoption response.

    The curve is G(t) = 1 - 2^(-t / h), where h is the intervention-specific half-time.
    At t=h, half of the modelled endpoint is realised. The curve is strictly increasing for
    positive time and approaches, but never exceeds, 1. It is a transparent scenario assumption
    about implementation and adoption—not proof of a causal developmental law.
    """
    if horizon_months is None:
        return 1.0, []
    months = max(float(horizon_months), 0.0)
    half_time = max(
        float(intervention.get("time_half_life_months", intervention.get("implementation_months", 6.0))),
        1e-9,
    )
    multiplier = 1.0 - 2.0 ** (-months / half_time)
    warnings: list[str] = []
    follow_up = intervention.get("evidence_followup_months")
    if follow_up is not None and months > float(follow_up):
        warnings.append(
            f"The selected {int(months)}-month horizon extends beyond the {follow_up}-month evidence window. "
            "The additional trajectory is an explicit persistence/adoption scenario, not a proven long-term effect."
        )
    return float(np.clip(multiplier, 0.0, 1.0)), warnings


def _time_multiplier(intervention: dict, horizon_months: int | None) -> tuple[float, list[str]]:
    """Backward-compatible alias for the public time-response function."""
    return time_response_factor(intervention, horizon_months)


def list_interventions(intervention_manifest: dict) -> pd.DataFrame:
    rows = []
    for key, item in intervention_manifest["interventions"].items():
        rows.append({
            "intervention": key,
            "label": item["label"],
            "enabled": item.get("enabled", True),
            "kind": item["kind"],
            "evidence_level": item.get("evidence_level", "not rated"),
            "direct_vector_claim": item.get("direct_vector_claim", ""),
            "implementation_months": item.get("implementation_months"),
        })
    return pd.DataFrame(rows)


def list_policy_packages(intervention_manifest: dict) -> pd.DataFrame:
    rows = []
    for key, item in intervention_manifest.get("policy_packages", {}).items():
        rows.append({
            "package": key,
            "label": item["label"],
            "enabled": item.get("enabled", True),
            "components": item.get("components", []),
            "rationale": item.get("rationale", ""),
        })
    return pd.DataFrame(rows)


def _indicator_dimension_map(model_manifest: dict) -> dict[str, str]:
    mapping: dict[str, str] = {}
    for dimension, specification in model_manifest["dimensions"].items():
        for item in specification["indicators"]:
            mapping[f"{dimension.upper()}__{item['variable']}__Z"] = dimension
    return mapping


def simulate_intervention(
    profile: pd.Series,
    reference: pd.DataFrame,
    model_manifest: dict,
    intervention_manifest: dict,
    intervention_key: str,
    options: SimulationOptions | None = None,
) -> dict[str, Any]:
    options = options or SimulationOptions()
    options.validate()

    interventions = intervention_manifest["interventions"]
    if intervention_key not in interventions:
        raise KeyError(f"Unknown intervention: {intervention_key}")
    intervention = interventions[intervention_key]
    if not intervention.get("enabled", True):
        raise ValueError(
            f"{intervention_key} is disabled: {intervention.get('disabled_reason', 'method not approved')}"
        )

    working = profile.to_dict()
    baseline = {
        dimension: _safe_float(profile.get(dimension, np.nan))
        for dimension in model_manifest["dimensions"]
    }
    baseline_raw = {
        dimension: _safe_float(profile.get(f"{dimension.upper()}__RAW", np.nan))
        for dimension in model_manifest["dimensions"]
    }

    indicator_to_dimension = _indicator_dimension_map(model_manifest)
    indicator_changes = []
    affected_dimensions: set[str] = set()
    no_change_reasons: list[str] = []
    time_factor, time_warnings = time_response_factor(intervention, options.horizon_months)
    strength = options.quality * options.dosage * time_factor
    weight_name = model_manifest["dataset"]["student_weight"]

    if strength == 0:
        no_change_reasons.append(
            "Quality × dosage × time-response factor equals zero, so the intervention has zero implemented strength."
        )

    for target in intervention.get("targets", []):
        column = target["indicator"]
        dimension = _dimension_for_indicator(column, indicator_to_dimension)
        old = _safe_float(working.get(column, np.nan))
        if not np.isfinite(old):
            message = (
                f"{column} is missing for this profile. Missing means unknown—not low—so the model "
                "will not invent a baseline gap."
            )
            no_change_reasons.append(message)
            indicator_changes.append({
                "indicator": column,
                "dimension": dimension,
                "before_z": None,
                "after_z": None,
                "change_z": None,
                "status": message,
                "reason_code": "missing_baseline_indicator",
                "proxy": bool(target.get("proxy", False)),
            })
            continue

        if intervention["kind"] in {"direct_target", "proxy_target"}:
            target_quantile = float(target["target_percentile"])
            target_z = weighted_reference_quantile(reference[column], reference[weight_name], target_quantile)
            if not np.isfinite(target_z):
                raise ValueError(f"Cannot calculate a reference target for {column}; check its coverage and weights.")
            gap = target_z - old
            if gap <= 1e-12:
                new = old
                method_note = (
                    f"no change: baseline is already at or above the Korean {target_quantile:.0%} "
                    f"reference target (baseline z={old:.3f}, target z={target_z:.3f})"
                )
                no_change_reasons.append(f"{column}: {method_note}")
                reason_code = "already_at_or_above_target"
            elif strength == 0:
                new = old
                method_note = "no change because implemented strength is zero"
                reason_code = "zero_strength"
            else:
                new = old + strength * gap
                method_note = (
                    f"closed {strength:.1%} of the gap toward the Korean {target_quantile:.0%} "
                    f"reference target (target z={target_z:.3f})"
                )
                reason_code = "changed"
        elif intervention["kind"] == "standardized_shift":
            shift = _effect_value(target, options.scenario) * strength
            cap_quantile = float(target.get("cap_percentile", 0.95))
            cap = weighted_reference_quantile(reference[column], reference[weight_name], cap_quantile)
            if not np.isfinite(cap):
                raise ValueError(f"Cannot calculate a reference cap for {column}; check its coverage and weights.")
            new = min(old + shift, cap)
            if shift == 0:
                method_note = "no change because the implemented shift is zero"
                reason_code = "zero_strength"
                no_change_reasons.append(f"{column}: {method_note}")
            elif new <= old + 1e-12:
                method_note = (
                    f"no change: baseline is already at the {cap_quantile:.0%} reference cap "
                    f"(baseline z={old:.3f}, cap z={cap:.3f})"
                )
                reason_code = "already_at_cap"
                no_change_reasons.append(f"{column}: {method_note}")
            else:
                method_note = (
                    f"added {new - old:.3f} SD under the {options.scenario} scenario, "
                    f"capped at the {cap_quantile:.0%} reference percentile"
                )
                reason_code = "changed"
        else:
            raise ValueError(f"Unsupported intervention kind: {intervention['kind']}")

        working[column] = float(new)
        if abs(float(new) - old) > 1e-12:
            affected_dimensions.add(dimension)
        indicator_changes.append({
            "indicator": column,
            "dimension": dimension,
            "before_z": old,
            "after_z": float(new),
            "change_z": float(new - old),
            "status": method_note,
            "reason_code": reason_code,
            "proxy": bool(target.get("proxy", False)),
        })

    projected = baseline.copy()
    projected_raw = baseline_raw.copy()
    for dimension in affected_dimensions:
        raw, score = _recalculate_dimension(working, dimension, model_manifest, reference)
        projected_raw[dimension] = raw
        projected[dimension] = score
        working[f"{dimension.upper()}__RAW"] = raw
        working[dimension] = score

    outcome_effects = []
    for outcome in intervention.get("outcome_effects", []):
        central = float(outcome["central_effect_sd"])
        selected = float(outcome.get(f"{options.scenario}_effect_sd", central))
        outcome_effects.append({
            "outcome": outcome["outcome"],
            "effect_sd": selected * strength,
            "source_estimate_sd": central,
            "note": outcome.get("note", ""),
        })

    vector_change = {}
    for dimension in baseline:
        before = baseline[dimension]
        after = projected[dimension]
        vector_change[dimension] = float(after - before) if np.isfinite(before) and np.isfinite(after) else float("nan")

    responsive = any(np.isfinite(value) and abs(value) > 1e-9 for value in vector_change.values())
    warnings = [*intervention.get("warnings", []), *time_warnings]
    if not responsive:
        warnings.append(
            "No vector changed for this profile under these settings. Read the indicator-level status and "
            "no-change reasons; this is usually caused by a missing target indicator, an already-met target, "
            "or zero implementation strength."
        )

    group_value = profile.get("ANALYSIS_GROUP")
    analysis_group = None if pd.isna(group_value) else str(group_value)
    projected_indicator_values = {
        change["indicator"]: change["after_z"]
        for change in indicator_changes
        if change.get("after_z") is not None
    }

    return {
        "profile_id": profile.get("PROFILE_ID"),
        "analysis_group": analysis_group,
        "intervention": intervention_key,
        "label": intervention["label"],
        "scenario": options.scenario,
        "quality": options.quality,
        "dosage": options.dosage,
        "horizon_months": options.horizon_months,
        "time_factor": time_factor,
        "time_half_life_months": float(intervention.get("time_half_life_months", intervention.get("implementation_months", 6.0))),
        "time_formula": "G(t) = 1 - 2^(-t / h)",
        "implemented_strength": strength,
        "responsive": responsive,
        "baseline_vector": baseline,
        "projected_vector": projected,
        "vector_change": vector_change,
        "baseline_raw": baseline_raw,
        "projected_raw": projected_raw,
        "projected_indicator_values": projected_indicator_values,
        "indicator_changes": indicator_changes,
        "no_change_reasons": no_change_reasons,
        "outcome_effects": outcome_effects,
        "evidence_level": intervention.get("evidence_level"),
        "assumptions": intervention.get("assumptions", []),
        "warnings": warnings,
        "method": intervention.get("method_explanation", ""),
    }


def _series_after_result(profile: pd.Series, result: dict[str, Any]) -> pd.Series:
    updated = profile.copy()
    for column, value in result.get("projected_indicator_values", {}).items():
        updated[column] = value
    for dimension, value in result.get("projected_vector", {}).items():
        updated[dimension] = value
    for dimension, value in result.get("projected_raw", {}).items():
        updated[f"{dimension.upper()}__RAW"] = value
    return updated


def simulate_policy_package(
    profile: pd.Series,
    reference: pd.DataFrame,
    model_manifest: dict,
    intervention_manifest: dict,
    package_key: str,
    options: SimulationOptions | None = None,
) -> dict[str, Any]:
    options = options or SimulationOptions()
    options.validate()
    packages = intervention_manifest.get("policy_packages", {})
    if package_key not in packages:
        raise KeyError(f"Unknown policy package: {package_key}")
    package = packages[package_key]
    if not package.get("enabled", True):
        raise ValueError(f"{package_key} is disabled: {package.get('disabled_reason', 'method not approved')}")

    baseline_vector = {
        dimension: _safe_float(profile.get(dimension, np.nan))
        for dimension in model_manifest["dimensions"]
    }
    working = profile.copy()
    component_results: list[dict[str, Any]] = []
    warnings = list(package.get("warnings", []))
    assumptions = list(package.get("assumptions", []))

    for component in package.get("components", []):
        result = simulate_intervention(
            profile=working,
            reference=reference,
            model_manifest=model_manifest,
            intervention_manifest=intervention_manifest,
            intervention_key=component,
            options=options,
        )
        component_results.append(result)
        working = _series_after_result(working, result)
        warnings.extend(result.get("warnings", []))

    projected_vector = {
        dimension: _safe_float(working.get(dimension, np.nan))
        for dimension in model_manifest["dimensions"]
    }
    vector_change = {
        dimension: (
            float(projected_vector[dimension] - baseline_vector[dimension])
            if np.isfinite(projected_vector[dimension]) and np.isfinite(baseline_vector[dimension])
            else float("nan")
        )
        for dimension in baseline_vector
    }
    responsive = any(np.isfinite(value) and abs(value) > 1e-9 for value in vector_change.values())
    return {
        "profile_id": profile.get("PROFILE_ID"),
        "package": package_key,
        "label": package["label"],
        "scenario": options.scenario,
        "quality": options.quality,
        "dosage": options.dosage,
        "horizon_months": options.horizon_months,
        "responsive": responsive,
        "baseline_vector": baseline_vector,
        "projected_vector": projected_vector,
        "vector_change": vector_change,
        "component_results": component_results,
        "assumptions": assumptions,
        "warnings": list(dict.fromkeys(warnings)),
        "method": (
            "Package components are applied sequentially to the underlying indicators. Later components act on "
            "the remaining gap; effect estimates are not blindly added. Outcome effects from different studies "
            "are reported component-by-component and are not summed into one causal total."
        ),
    }


def targeted_dimensions(intervention: dict, model_manifest: dict) -> list[str]:
    mapping = _indicator_dimension_map(model_manifest)
    dimensions: list[str] = []
    for target in intervention.get("targets", []):
        dimension = mapping.get(target.get("indicator"))
        if dimension and dimension not in dimensions:
            dimensions.append(dimension)
    return dimensions


def policy_fit_summary(
    baseline_vector: dict[str, float],
    result: dict[str, Any],
    target_dimensions: Iterable[str],
    benchmark_percentile: float = 50.0,
) -> dict[str, Any]:
    targets = list(dict.fromkeys(target_dimensions))
    gaps = {}
    for dimension, score in baseline_vector.items():
        value = _safe_float(score)
        gaps[dimension] = (
            max(0.0, benchmark_percentile - value) / benchmark_percentile
            if np.isfinite(value)
            else float("nan")
        )
    target_gaps = [gaps[d] for d in targets if d in gaps and np.isfinite(gaps[d])]
    alignment = float(100 * np.mean(target_gaps)) if target_gaps else float("nan")
    changes = result.get("vector_change", {})
    expected_movement = float(
        sum(max(0.0, _safe_float(value)) for value in changes.values() if np.isfinite(_safe_float(value)))
    )
    unaddressed = [
        dimension
        for dimension, gap in gaps.items()
        if np.isfinite(gap)
        and gap > 0
        and (not np.isfinite(_safe_float(changes.get(dimension))) or _safe_float(changes.get(dimension)) < 0.1)
    ]
    return {
        "need_alignment_percent": alignment,
        "benchmark_percentile": benchmark_percentile,
        "expected_total_positive_movement": expected_movement,
        "target_dimensions": targets,
        "unaddressed_needs": unaddressed,
        "dimension_gaps": gaps,
        "note": (
            "Need alignment measures how strongly the policy targets dimensions below the Korean median. "
            "It is not a probability of success and is kept separate from evidence strength."
        ),
    }


def compare_policies(
    profile: pd.Series,
    reference: pd.DataFrame,
    model_manifest: dict,
    intervention_manifest: dict,
    options: SimulationOptions | None = None,
    intervention_keys: Iterable[str] | None = None,
    package_keys: Iterable[str] | None = None,
) -> tuple[pd.DataFrame, dict[str, dict[str, Any]]]:
    options = options or SimulationOptions()
    interventions = intervention_manifest["interventions"]
    if intervention_keys is None:
        intervention_keys = [key for key, item in interventions.items() if item.get("enabled", True)]
    packages = intervention_manifest.get("policy_packages", {})
    if package_keys is None:
        package_keys = [key for key, item in packages.items() if item.get("enabled", True)]

    results: dict[str, dict[str, Any]] = {}
    rows: list[dict[str, Any]] = []
    baseline_vector = {dimension: _safe_float(profile.get(dimension)) for dimension in model_manifest["dimensions"]}

    for key in intervention_keys:
        result = simulate_intervention(
            profile, reference, model_manifest, intervention_manifest, key, options
        )
        results[key] = result
        targets = targeted_dimensions(interventions[key], model_manifest)
        fit = policy_fit_summary(baseline_vector, result, targets)
        row = {
            "policy_key": key,
            "policy_type": "intervention",
            "label": interventions[key]["label"],
            "evidence_level": interventions[key].get("evidence_level", "not rated"),
            **fit,
        }
        for dimension, value in result["projected_vector"].items():
            row[dimension] = value
            row[f"delta_{dimension}"] = result["vector_change"].get(dimension)
        rows.append(row)

    for key in package_keys:
        result = simulate_policy_package(
            profile, reference, model_manifest, intervention_manifest, key, options
        )
        results[key] = result
        component_targets: list[str] = []
        evidence_levels: list[str] = []
        for component in packages[key].get("components", []):
            component_targets.extend(targeted_dimensions(interventions[component], model_manifest))
            evidence_levels.append(interventions[component].get("evidence_level", "not rated"))
        fit = policy_fit_summary(baseline_vector, result, component_targets)
        row = {
            "policy_key": key,
            "policy_type": "package",
            "label": packages[key]["label"],
            "evidence_level": "Mixed package evidence: " + " | ".join(evidence_levels),
            **fit,
        }
        for dimension, value in result["projected_vector"].items():
            row[dimension] = value
            row[f"delta_{dimension}"] = result["vector_change"].get(dimension)
        rows.append(row)

    return pd.DataFrame(rows), results


def vector_change_statuses(result: dict[str, Any], threshold: float = 0.1) -> list[dict[str, str]]:
    statuses: list[dict[str, str]] = []
    all_changes = result.get("indicator_changes", [])
    for dimension, before in result.get("baseline_vector", {}).items():
        after = result.get("projected_vector", {}).get(dimension)
        delta = result.get("vector_change", {}).get(dimension)
        relevant = [item for item in all_changes if item.get("dimension") == dimension]
        reason_codes = {item.get("reason_code") for item in relevant}
        if not relevant and abs(_safe_float(delta)) < threshold:
            status = "Not directly targeted"
            explanation = "This policy does not directly target this dimension, so no spillover was invented."
        elif not np.isfinite(_safe_float(before)) or not np.isfinite(_safe_float(after)):
            status = "Cannot estimate"
            explanation = "The baseline or projected dimension is missing."
        elif abs(_safe_float(delta)) >= threshold:
            status = "Measurable movement"
            explanation = f"The displayed percentile changed by {_safe_float(delta):+.1f} points."
        elif "missing_baseline_indicator" in reason_codes:
            status = "Cannot estimate"
            explanation = "A required target indicator is missing; unknown information was not treated as disadvantage."
        elif reason_codes.intersection({"already_at_or_above_target", "already_at_cap"}):
            status = "Already covered"
            explanation = "The profile already meets the programme target or evidence cap."
        elif any(abs(_safe_float(item.get("change_z"))) > 1e-12 for item in relevant):
            status = "Small underlying change"
            explanation = "A targeted indicator changed, but the Korean percentile movement was below 0.1 points."
        else:
            status = "No implemented change"
            explanation = "The targeted intervention had zero implemented strength."
        statuses.append({"dimension": dimension, "status": status, "explanation": explanation})
    return statuses
