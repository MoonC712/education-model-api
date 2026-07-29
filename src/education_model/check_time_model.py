from __future__ import annotations

import argparse
import json
from pathlib import Path

from .interventions import time_response_factor


def main() -> None:
    parser = argparse.ArgumentParser(description="Show intervention time-response factors.")
    parser.add_argument("--manifest", default="config/intervention_manifest.json")
    args = parser.parse_args()

    path = Path(args.manifest)
    with path.open("r", encoding="utf-8") as handle:
        manifest = json.load(handle)

    horizons = [int(item["months"]) for item in manifest["time_horizons"]]
    header = ["intervention", "half-time"] + [f"{month}m" for month in horizons]
    print(" | ".join(header))
    print("-" * 100)
    for key, intervention in manifest["interventions"].items():
        if not intervention.get("enabled", True):
            continue
        factors = [time_response_factor(intervention, month)[0] for month in horizons]
        values = [
            intervention["label"],
            f"{intervention.get('time_half_life_months')}m",
            *[f"{value:.4f}" for value in factors],
        ]
        print(" | ".join(values))


if __name__ == "__main__":
    main()
