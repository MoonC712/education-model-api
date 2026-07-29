Build the frontend around five pages only: Group overview, Student explorer, Intervention simulator, Population map, and Methods & evidence.

For the Intervention simulator:

- offer exactly four times: 1 month, 6 months, 1 year, and 2 years;
- show the original five-vector chart permanently;
- after simulation, show a separate projected five-vector chart;
- show exact values to two decimal places;
- show a line chart and table containing all four time-horizon vectors;
- use the API's `time_factor`, `time_half_life_months`, and `time_formula` in the method explanation;
- never fabricate movement if the API reports missing data, an already-met target, a cap, or zero strength.

For the Population map:

- use `axis_metadata[].display_name` as the 2D and 3D axis titles;
- show `positive_direction`, `negative_direction`, and explained variance below the chart;
- provide an expandable table of loadings;
- do not display unexplained labels such as PC1/PC2/PC3 as the main user-facing axis names.

Do not build Policy comparison, Narrative lab, or Narrative validation pages.

Keep a small footer stating that the baseline is calibrated with OECD PISA 2022 public-use microdata for South Korea, the transparent scenario approach is inspired by UNESCO SimuED, the app is an independent student project, and outputs are scenarios rather than guaranteed predictions.
