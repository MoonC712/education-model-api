from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any
import json
import re

import numpy as np
import pandas as pd

from .model_reference import percentile_from_weighted_reference, weighted_reference_quantile


UNKNOWN = "unknown"


@dataclass(frozen=True)
class NarrativeCode:
    indicator: str
    level: str
    evidence_quote: str | None = None
    confidence: str = "unreviewed"
    source: str = "automatic_proposal"


def load_narrative_schema(path: Path | str) -> dict[str, Any]:
    with Path(path).open("r", encoding="utf-8") as handle:
        return json.load(handle)


def split_sentences(text: str) -> list[str]:
    cleaned = re.sub(r"\s+", " ", str(text or "")).strip()
    if not cleaned:
        return []
    return [part.strip() for part in re.split(r"(?<=[.!?])\s+", cleaned) if part.strip()]


def _pattern_match(sentence: str, pattern: str) -> bool:
    return re.search(r"\b" + re.escape(pattern.lower()) + r"\b", sentence.lower()) is not None


def propose_narrative_codes(text: str, schema: dict[str, Any]) -> dict[str, dict[str, Any]]:
    """Produce conservative, review-required coding proposals.

    The function only codes explicit phrase matches from the transparent schema. It never treats
    silence as low or high evidence. If conflicting levels appear, the proposal remains unknown and
    preserves the conflicting evidence for human review.
    """
    sentences = split_sentences(text)
    proposals: dict[str, dict[str, Any]] = {}
    for indicator, spec in schema["indicators"].items():
        matches: list[tuple[str, str, str]] = []
        for level, patterns in spec.get("patterns", {}).items():
            for pattern in patterns:
                for sentence in sentences:
                    if _pattern_match(sentence, pattern):
                        matches.append((level, sentence, pattern))
        levels = list(dict.fromkeys(level for level, _, _ in matches))
        if not matches:
            proposals[indicator] = {
                "indicator": indicator,
                "level": UNKNOWN,
                "evidence_quote": None,
                "confidence": "none",
                "source": "automatic_proposal",
                "status": "No explicit evidence detected; remains unknown.",
            }
        elif len(levels) > 1:
            proposals[indicator] = {
                "indicator": indicator,
                "level": UNKNOWN,
                "evidence_quote": " | ".join(dict.fromkeys(sentence for _, sentence, _ in matches)),
                "confidence": "conflict",
                "source": "automatic_proposal",
                "status": f"Conflicting explicit cues detected ({', '.join(levels)}); human review required.",
            }
        else:
            level = levels[0]
            proposals[indicator] = {
                "indicator": indicator,
                "level": level,
                "evidence_quote": matches[0][1],
                "confidence": "high" if len(matches) == 1 else "high_multiple_matches",
                "source": "automatic_proposal",
                "status": f"Matched explicit {level} evidence. Human confirmation is still required.",
            }
    return proposals


def normalise_codes(codes: dict[str, Any], schema: dict[str, Any]) -> dict[str, dict[str, Any]]:
    allowed = set(schema["levels"])
    output: dict[str, dict[str, Any]] = {}
    for indicator in schema["indicators"]:
        value = codes.get(indicator, UNKNOWN)
        if isinstance(value, dict):
            level = value.get("level", UNKNOWN)
            evidence = value.get("evidence_quote")
            confidence = value.get("confidence", "human_reviewed")
            source = value.get("source", "human_reviewed")
        else:
            level = str(value)
            evidence = None
            confidence = "human_reviewed"
            source = "human_reviewed"
        if level not in allowed:
            raise ValueError(f"Unknown narrative level {level!r} for {indicator}")
        output[indicator] = {
            "indicator": indicator,
            "level": level,
            "evidence_quote": evidence,
            "confidence": confidence,
            "source": source,
        }
    return output


def narrative_codes_to_profile(
    codes: dict[str, Any],
    reference: pd.DataFrame,
    model_manifest: dict[str, Any],
    narrative_schema: dict[str, Any],
    narrative_id: str = "NARRATIVE_CASE",
) -> dict[str, Any]:
    """Map reviewed ordinal narrative codes to the fixed Korean PISA reference.

    A level maps to a declared Korean reference quantile (10/25/50/75/90). This is a transparent
    calibration rule, not a learned causal or diagnostic mapping. Dimensions are only returned when
    the baseline model's minimum number of indicators is present.
    """
    reviewed = normalise_codes(codes, narrative_schema)
    weight_name = model_manifest["dataset"]["student_weight"]
    working: dict[str, Any] = {"PROFILE_ID": narrative_id, "ANALYSIS_GROUP": "narrative_case"}
    indicator_records: list[dict[str, Any]] = []

    for indicator, record in reviewed.items():
        spec = narrative_schema["indicators"][indicator]
        dimension = spec["dimension"]
        column = f"{dimension.upper()}__{indicator}__Z"
        level = record["level"]
        if level == UNKNOWN:
            z_value = float("nan")
            quantile = None
        else:
            quantile = float(narrative_schema["level_quantiles"][level])
            if column not in reference.columns:
                raise KeyError(f"Reference profiles do not contain {column}")
            z_value = weighted_reference_quantile(reference[column], reference[weight_name], quantile)
        working[column] = z_value
        indicator_records.append({
            "indicator": indicator,
            "dimension": dimension,
            "label": spec["label"],
            "level": level,
            "reference_quantile": quantile,
            "aligned_z_score": None if not np.isfinite(z_value) else float(z_value),
            "evidence_quote": record.get("evidence_quote"),
            "confidence": record.get("confidence"),
            "source": record.get("source"),
        })

    vector: dict[str, float | None] = {}
    raw: dict[str, float | None] = {}
    coverage: dict[str, dict[str, Any]] = {}
    for dimension, specification in model_manifest["dimensions"].items():
        columns = [f"{dimension.upper()}__{item['variable']}__Z" for item in specification["indicators"]]
        values = [float(working.get(column, np.nan)) for column in columns]
        finite = [value for value in values if np.isfinite(value)]
        minimum = int(specification["minimum_nonmissing"])
        coverage[dimension] = {
            "observed_indicators": len(finite),
            "total_indicators": len(columns),
            "minimum_required": minimum,
            "complete_enough": len(finite) >= minimum,
        }
        if len(finite) < minimum:
            vector[dimension] = None
            raw[dimension] = None
            working[dimension] = np.nan
            working[f"{dimension.upper()}__RAW"] = np.nan
            continue
        raw_value = float(np.mean(finite))
        percentile = percentile_from_weighted_reference(
            raw_value,
            reference[f"{dimension.upper()}__RAW"],
            reference[weight_name],
        )
        vector[dimension] = percentile
        raw[dimension] = raw_value
        working[dimension] = percentile
        working[f"{dimension.upper()}__RAW"] = raw_value

    known_count = sum(record["level"] != UNKNOWN for record in reviewed.values())
    return {
        "profile_id": narrative_id,
        "vector": vector,
        "raw_composites": raw,
        "indicator_codes": indicator_records,
        "coverage": coverage,
        "known_indicator_count": known_count,
        "total_indicator_count": len(reviewed),
        "evidence_coverage_percent": 100.0 * known_count / len(reviewed) if reviewed else 0.0,
        "warnings": [
            "Narrative scores are calibrated scenarios based on reviewed explicit evidence, not individual diagnoses.",
            "Unknown evidence remains missing; it is never treated as low opportunity.",
            "Ordinal narrative levels are mapped to declared Korean PISA reference quantiles and require validation against independent human coding.",
        ],
        "profile_row": working,
    }


def proposals_to_frame(proposals: dict[str, dict[str, Any]], schema: dict[str, Any]) -> pd.DataFrame:
    rows = []
    for indicator, record in proposals.items():
        spec = schema["indicators"][indicator]
        rows.append({
            "indicator": indicator,
            "label": spec["label"],
            "dimension": spec["dimension"],
            "proposed_level": record["level"],
            "evidence_quote": record.get("evidence_quote"),
            "confidence": record.get("confidence"),
            "status": record.get("status"),
        })
    return pd.DataFrame(rows)


def narrative_annotation_template(narrative_ids: list[str], schema: dict[str, Any], coder_id: str) -> pd.DataFrame:
    rows = []
    for narrative_id in narrative_ids:
        for indicator in schema["indicators"]:
            rows.append({
                "narrative_id": narrative_id,
                "coder_id": coder_id,
                "indicator": indicator,
                "level": UNKNOWN,
                "evidence_quote": "",
            })
    return pd.DataFrame(rows)
