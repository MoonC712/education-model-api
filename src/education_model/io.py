from __future__ import annotations

import json
from pathlib import Path
from typing import Iterable

import pandas as pd
import pyreadstat


def load_manifest(path: Path) -> dict:
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def sav_metadata(path: Path):
    _, metadata = pyreadstat.read_sav(str(path), metadataonly=True)
    labels = metadata.column_names_to_labels or {}
    return {name.upper(): labels.get(name, "") for name in metadata.column_names}


def find_sav(data_dir: Path, kind: str) -> Path:
    patterns = {
        "student": ["*STU*QQQ*.sav", "*student*.sav"],
        "school": ["*SCH*QQQ*.sav", "*school*.sav"]
    }
    found = []
    for pattern in patterns[kind]:
        found.extend(data_dir.rglob(pattern))
    unique = sorted(set(found))
    if not unique:
        raise FileNotFoundError(f"No {kind} .sav found under {data_dir}")
    if len(unique) > 1:
        exact = [p for p in unique if ("STU_QQQ" in p.name.upper() if kind == "student" else "SCH_QQQ" in p.name.upper())]
        if len(exact) == 1:
            return exact[0]
        raise RuntimeError(f"Multiple candidate {kind} files found: {unique}")
    return unique[0]


def read_korea_student_chunks(path: Path, usecols: Iterable[str], country_code="KOR", chunksize=25_000) -> pd.DataFrame:
    usecols = list(dict.fromkeys(c.upper() for c in usecols))
    chunks = []
    iterator = pyreadstat.read_file_in_chunks(
        pyreadstat.read_sav,
        str(path),
        chunksize=chunksize,
        usecols=usecols
    )
    for frame, _ in iterator:
        frame.columns = [c.upper() for c in frame.columns]
        country = frame["CNT"].astype(str).str.strip().str.upper()
        selected = frame.loc[country.eq(country_code.upper())].copy()
        if not selected.empty:
            chunks.append(selected)
    if not chunks:
        raise ValueError(f"No student records found for country {country_code}")
    return pd.concat(chunks, ignore_index=True)


def read_korea_school(path: Path, usecols: Iterable[str], country_code="KOR") -> pd.DataFrame:
    frame, _ = pyreadstat.read_sav(str(path), usecols=list(dict.fromkeys(c.upper() for c in usecols)))
    frame.columns = [c.upper() for c in frame.columns]
    country = frame["CNT"].astype(str).str.strip().str.upper()
    selected = frame.loc[country.eq(country_code.upper())].copy()
    if selected.empty:
        raise ValueError(f"No school records found for country {country_code}")
    return selected
