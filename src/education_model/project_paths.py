from __future__ import annotations

from dataclasses import dataclass
import os
from pathlib import Path


@dataclass(frozen=True)
class ProjectPaths:
    """All files needed by the local dashboard and API.

    The default root is the current working directory. Set EDUCATION_MODEL_ROOT
    when the API is launched from another directory.
    """

    root: Path

    @classmethod
    def from_root(cls, root: Path | str | None = None) -> "ProjectPaths":
        if root is None:
            root = os.getenv("EDUCATION_MODEL_ROOT", ".")
        return cls(Path(root).expanduser().resolve())

    @property
    def profiles(self) -> Path:
        return self.root / "outputs" / "korea_model_profiles.csv.gz"

    @property
    def public_profiles(self) -> Path:
        return self.root / "outputs" / "korea_scored_anonymous.csv.gz"

    @property
    def archetypes(self) -> Path:
        return self.root / "outputs" / "four_group_archetypes.csv"

    @property
    def prototypes(self) -> Path:
        return self.root / "outputs" / "representative_prototypes.csv"

    @property
    def run_summary(self) -> Path:
        return self.root / "outputs" / "run_summary.json"

    @property
    def model_manifest(self) -> Path:
        return self.root / "config" / "indicator_manifest.json"

    @property
    def intervention_manifest(self) -> Path:
        return self.root / "config" / "intervention_manifest.json"

    @property
    def intervention_evidence(self) -> Path:
        return self.root / "config" / "intervention_evidence.csv"

    @property
    def narrative_schema(self) -> Path:
        return self.root / "config" / "narrative_schema.json"

    @property
    def narrative_demo(self) -> Path:
        return self.root / "data" / "narratives" / "demo_narratives.csv"

    @property
    def narrative_template(self) -> Path:
        return self.root / "data" / "narratives" / "narratives_template.csv"

    def required_visual_files(self) -> list[Path]:
        return [
            self.profiles,
            self.archetypes,
            self.model_manifest,
            self.intervention_manifest,
            self.intervention_evidence,
            self.narrative_schema,
        ]

    def missing_visual_files(self) -> list[Path]:
        return [path for path in self.required_visual_files() if not path.exists()]
