# Phase 4.7 — Time trajectories and readable population-map axes

This update does two things:

1. fixes the intervention time horizons so 1 month, 6 months, 1 year, and 2 years create distinct projected states for responsive students;
2. replaces unexplained PC1/PC2/PC3 axis titles with dynamically generated plain-language labels.

It also removes these dashboard tabs:

- Policy comparison;
- Narrative lab;
- Narrative validation.

The underlying files remain in the project but are not shown in the main website.

---

## Part A — Install the update

### 1. Stop Streamlit

In the terminal running the website, press:

```text
Control + C
```

### 2. Back up the current project

Duplicate your current project folder and rename the copy:

```text
education_model_backup_before_time_fix
```

### 3. Unzip the update

Unzip:

```text
education_model_phase4_7_time_pca_update.zip
```

Copy the contents into your existing project folder. Choose **Replace** for matching files.

Do not delete or replace:

```text
.venv
data/raw
outputs
```

You do not need to download PISA again or rerun the baseline pipeline.

### 4. Reinstall the local package

Open the VS Code terminal inside the project folder:

```bash
source .venv/bin/activate
```

```bash
python -m pip install -r requirements.txt
```

```bash
python -m pip install -e .
```

### 5. Run the tests

```bash
python -m pytest -q
```

Expected result:

```text
28 passed
```

---

## Part B — Verify the time mathematics

Run:

```bash
python -m education_model.check_time_model
```

The table should contain four different factors for every enabled intervention:

```text
1m | 6m | 12m | 24m
```

For the laptop package, the default factors are approximately:

```text
0.2063 | 0.7500 | 0.9375 | 0.9961
```

These come from:

\[
G(t)=1-2^{-t/h}
\]

For the laptop package, \(h=3\) months.

The number means the fraction of the modelled endpoint that has been realised—not the probability that the intervention succeeds.

---

## Part C — Restart the website

```bash
python -m streamlit run src/education_model/dashboard.py
```

Open:

```text
http://localhost:8501
```

The dashboard now has five tabs:

```text
Group overview
Student explorer
Intervention simulator
Population map
Methods & evidence
```

---

## Part D — Test the intervention time pathway

### 1. Open `Intervention simulator`

Choose a student who responds to the laptop intervention.

### 2. Select

```text
Laptop + reliable home internet
```

Keep:

```text
Evidence scenario: central
Implementation quality: 1.0
Programme dosage: 1.0
```

### 3. Choose one projected time

You can choose:

```text
1 month
6 months
1 year
2 years
```

Press:

```text
Apply intervention
```

### 4. Inspect the result

The page now displays:

- the current vector;
- the separate projected vector at the selected time;
- exact values to two decimal places;
- a line chart showing all four time horizons simultaneously;
- a table with all five vector values at 1, 6, 12, and 24 months;
- the time half-life and formula;
- indicator-level changes and zero-change explanations.

For a responsive student, the targeted vector should progress across all four horizons.

### 5. When the values can correctly remain unchanged

The four horizons should not be forced to differ when:

- the relevant baseline indicator is missing;
- the student already meets the policy target;
- the standardised-shift cap has already been reached;
- quality or dosage is zero.

In these cases the website explains the reason.

---

## Part E — Understand the time equation

The intervention-specific response is:

\[
G_a(t)=1-2^{-t/h_a}
\]

where:

- \(t\) = months since the intervention begins;
- \(h_a\) = the intervention's half-time;
- \(G_a(t)\) = fraction of the endpoint realised.

Overall implemented strength is:

\[
q\times d\times G_a(t)
\]

where:

- \(q\) = implementation quality;
- \(d\) = dosage.

The half-times are stored in:

```text
config/intervention_manifest.json
```

under:

```json
"time_half_life_months"
```

They are transparent scenario assumptions and may be revised when stronger longitudinal evidence is available.

---

## Part F — Test the population map labels

Open:

```text
Population map
```

Try both:

```text
2D
3D
```

The axes should no longer be labelled only `PC1`, `PC2`, and `PC3`.

They will appear in forms such as:

```text
Axis 1 — Overall opportunity
Axis 2 — Wellbeing & Human support vs Digital access & Resources
Axis 3 — Learning agency vs Wellbeing
```

The exact labels depend on the loadings calculated from your real Korean profile data.

Below the graph, inspect:

```text
What the axes mean
```

This table explains:

- the positive direction;
- the negative direction;
- the share of profile variation represented.

You can expand:

```text
See exact dimension loadings
```

for the numerical PCA loadings.

Remember: these axes are summaries of the five existing vectors. They are not new educational indicators.

---

## Part G — API change

The endpoint:

```text
GET /api/population-map
```

now includes:

```json
"axis_metadata": []
```

Each axis includes its display label, directions, explained variance, and loadings. This allows a future Lovable frontend to use the same human-readable labels.
