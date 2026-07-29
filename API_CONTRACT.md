# API additions — time and PCA labels

## `POST /api/simulate`

Use one of these `horizon_months` values:

```json
1
6
12
24
```

The result now includes:

```json
{
  "horizon_months": 12,
  "time_factor": 0.875,
  "time_half_life_months": 4,
  "time_formula": "G(t) = 1 - 2^(-t / h)",
  "baseline_vector": {},
  "projected_vector": {},
  "vector_change": {}
}
```

For a responsive profile, the four horizons follow a strictly increasing saturating response. Missing indicators, already-met targets, caps, or zero quality/dosage can correctly produce no movement.

## `GET /api/population-map`

Example response:

```json
{
  "components": 2,
  "explained_variance_ratio": [0.42, 0.21],
  "axis_metadata": [
    {
      "axis": "PC1",
      "display_name": "Axis 1 — Overall opportunity",
      "short_label": "Overall opportunity",
      "positive_direction": "higher across most of the five dimensions",
      "negative_direction": "lower across most of the five dimensions",
      "explained_variance_ratio": 0.42,
      "loadings": {
        "resources": 0.46,
        "human_support": 0.41,
        "digital_access": 0.48,
        "learning_agency": 0.44,
        "wellbeing": 0.43
      }
    }
  ],
  "items": []
}
```

The frontend should use `display_name` for axis titles and show the positive/negative direction descriptions near the map.
