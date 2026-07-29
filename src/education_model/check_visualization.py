from __future__ import annotations

import argparse
from pathlib import Path

from .project_paths import ProjectPaths
from .visualization import DIMENSIONS, load_project_data


def main() -> None:
    parser = argparse.ArgumentParser(description="Check files needed for the Phase 3 dashboard and API.")
    parser.add_argument("--root", type=Path, default=Path("."))
    args = parser.parse_args()

    paths = ProjectPaths.from_root(args.root)
    print(f"Project root: {paths.root}")
    missing = paths.missing_visual_files()
    if missing:
        print("\nMissing files:")
        for path in missing:
            print(f"  - {path}")
        raise SystemExit(1)

    data = load_project_data(paths)
    print("\nAll required files exist.")
    print(f"Profiles: {len(data.profiles):,}")
    print(f"Assigned to four groups: {(data.profiles['ANALYSIS_GROUP'] != 'not_in_four_group_comparison').sum():,}")
    print(f"Group archetype rows: {len(data.archetypes):,}")
    print(f"Enabled interventions: {sum(bool(v.get('enabled', True)) for v in data.intervention_manifest['interventions'].values())}")
    print("Dimensions:", ", ".join(DIMENSIONS))
    print("\nPhase 3 files are ready.")


if __name__ == "__main__":
    main()
