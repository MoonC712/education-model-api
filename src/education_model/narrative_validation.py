from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd
from scipy.stats import spearmanr
from sklearn.metrics import cohen_kappa_score

from .narratives import UNKNOWN


REQUIRED_ANNOTATION_COLUMNS = {"narrative_id", "coder_id", "indicator", "level"}


def validate_annotation_frame(frame: pd.DataFrame) -> None:
    missing = REQUIRED_ANNOTATION_COLUMNS.difference(frame.columns)
    if missing:
        raise ValueError(f"Annotation file is missing columns: {sorted(missing)}")
    if frame.duplicated(["narrative_id", "coder_id", "indicator"]).any():
        raise ValueError("Each coder must provide at most one level per narrative and indicator.")


def _safe_kappa(a: pd.Series, b: pd.Series) -> float | None:
    mask = a.notna() & b.notna()
    if mask.sum() == 0:
        return None
    if len(set(a[mask]).union(set(b[mask]))) <= 1:
        return 1.0 if (a[mask] == b[mask]).all() else 0.0
    value = cohen_kappa_score(a[mask], b[mask])
    return None if not np.isfinite(value) else float(value)


def pairwise_human_reliability(annotations: pd.DataFrame) -> dict[str, Any]:
    validate_annotation_frame(annotations)
    coders = sorted(annotations["coder_id"].dropna().astype(str).unique())
    if len(coders) < 2:
        raise ValueError("At least two human coders are required.")
    coder_a, coder_b = coders[:2]
    left = annotations.loc[annotations["coder_id"].astype(str) == coder_a]
    right = annotations.loc[annotations["coder_id"].astype(str) == coder_b]
    merged = left.merge(
        right,
        on=["narrative_id", "indicator"],
        suffixes=("_a", "_b"),
        how="inner",
    )
    if merged.empty:
        raise ValueError("The two coder files have no overlapping narrative/indicator rows.")

    per_indicator = []
    for indicator, group in merged.groupby("indicator"):
        per_indicator.append({
            "indicator": indicator,
            "n_pairs": int(len(group)),
            "cohens_kappa": _safe_kappa(group["level_a"], group["level_b"]),
            "exact_agreement": float((group["level_a"] == group["level_b"]).mean()),
        })
    return {
        "coder_a": coder_a,
        "coder_b": coder_b,
        "overall_cohens_kappa": _safe_kappa(merged["level_a"], merged["level_b"]),
        "overall_exact_agreement": float((merged["level_a"] == merged["level_b"]).mean()),
        "per_indicator": per_indicator,
        "n_pairs": int(len(merged)),
    }


def consensus_annotations(annotations: pd.DataFrame) -> pd.DataFrame:
    """Create conservative two-coder consensus.

    Exact agreement becomes the consensus level. Disagreement remains unresolved and is not silently
    broken by majority voting when there are only two coders.
    """
    reliability = pairwise_human_reliability(annotations)
    coder_a, coder_b = reliability["coder_a"], reliability["coder_b"]
    left = annotations.loc[annotations["coder_id"].astype(str) == coder_a]
    right = annotations.loc[annotations["coder_id"].astype(str) == coder_b]
    merged = left.merge(right, on=["narrative_id", "indicator"], suffixes=("_a", "_b"), how="inner")
    merged["consensus_level"] = np.where(
        merged["level_a"] == merged["level_b"], merged["level_a"], np.nan
    )
    merged["resolved"] = merged["level_a"] == merged["level_b"]
    return merged[["narrative_id", "indicator", "consensus_level", "resolved", "level_a", "level_b"]]


def algorithm_vs_consensus(
    annotations: pd.DataFrame,
    algorithm_codes: pd.DataFrame,
) -> dict[str, Any]:
    required = {"narrative_id", "indicator", "level"}
    missing = required.difference(algorithm_codes.columns)
    if missing:
        raise ValueError(f"Algorithm-code file is missing columns: {sorted(missing)}")
    consensus = consensus_annotations(annotations)
    resolved = consensus.loc[consensus["resolved"]].copy()
    merged = resolved.merge(
        algorithm_codes[["narrative_id", "indicator", "level"]].rename(columns={"level": "algorithm_level"}),
        on=["narrative_id", "indicator"],
        how="inner",
    )
    if merged.empty:
        raise ValueError("No resolved human-consensus rows overlap the algorithm output.")

    per_indicator = []
    for indicator, group in merged.groupby("indicator"):
        per_indicator.append({
            "indicator": indicator,
            "n": int(len(group)),
            "cohens_kappa": _safe_kappa(group["consensus_level"], group["algorithm_level"]),
            "exact_agreement": float((group["consensus_level"] == group["algorithm_level"]).mean()),
            "unknown_detection_accuracy": float(
                ((group["consensus_level"] == UNKNOWN) == (group["algorithm_level"] == UNKNOWN)).mean()
            ),
        })
    return {
        "overall_cohens_kappa": _safe_kappa(merged["consensus_level"], merged["algorithm_level"]),
        "overall_exact_agreement": float((merged["consensus_level"] == merged["algorithm_level"]).mean()),
        "unknown_detection_accuracy": float(
            ((merged["consensus_level"] == UNKNOWN) == (merged["algorithm_level"] == UNKNOWN)).mean()
        ),
        "per_indicator": per_indicator,
        "n": int(len(merged)),
        "unresolved_human_rows_excluded": int((~consensus["resolved"]).sum()),
    }


def vector_accuracy(human_vectors: pd.DataFrame, algorithm_vectors: pd.DataFrame, dimensions: list[str]) -> dict[str, Any]:
    required = {"narrative_id", *dimensions}
    for name, frame in [("human", human_vectors), ("algorithm", algorithm_vectors)]:
        missing = required.difference(frame.columns)
        if missing:
            raise ValueError(f"{name} vector file is missing columns: {sorted(missing)}")
    merged = human_vectors.merge(algorithm_vectors, on="narrative_id", suffixes=("_human", "_algorithm"))
    rows = []
    all_errors: list[float] = []
    for dimension in dimensions:
        h = pd.to_numeric(merged[f"{dimension}_human"], errors="coerce")
        a = pd.to_numeric(merged[f"{dimension}_algorithm"], errors="coerce")
        mask = h.notna() & a.notna()
        if mask.sum() == 0:
            rows.append({"dimension": dimension, "n": 0, "mae": None, "spearman": None})
            continue
        errors = (h[mask] - a[mask]).abs()
        all_errors.extend(errors.tolist())
        rho = spearmanr(h[mask], a[mask]).statistic if mask.sum() >= 3 else np.nan
        rows.append({
            "dimension": dimension,
            "n": int(mask.sum()),
            "mae": float(errors.mean()),
            "spearman": None if not np.isfinite(rho) else float(rho),
        })
    return {
        "overall_mae": float(np.mean(all_errors)) if all_errors else None,
        "per_dimension": rows,
        "n_narratives": int(len(merged)),
    }


def full_validation_report(
    human_annotations: pd.DataFrame,
    algorithm_codes: pd.DataFrame | None = None,
    human_vectors: pd.DataFrame | None = None,
    algorithm_vectors: pd.DataFrame | None = None,
    dimensions: list[str] | None = None,
) -> dict[str, Any]:
    report: dict[str, Any] = {
        "human_inter_rater": pairwise_human_reliability(human_annotations),
        "interpretation": {
            "warning": "No single kappa threshold proves validity. Inspect per-indicator sample sizes, disagreements, and evidence quotes.",
            "minimum_design": "Use at least two independent coders who do not see the algorithm proposal before coding.",
        },
    }
    if algorithm_codes is not None:
        report["algorithm_vs_human_consensus"] = algorithm_vs_consensus(human_annotations, algorithm_codes)
    if human_vectors is not None and algorithm_vectors is not None:
        report["vector_accuracy"] = vector_accuracy(
            human_vectors, algorithm_vectors, dimensions or [
                "resources", "human_support", "digital_access", "learning_agency", "wellbeing"
            ]
        )
    return report
