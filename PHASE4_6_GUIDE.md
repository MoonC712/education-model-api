# Phase 4–6 Guide: Policy Comparison, Narratives, and Validation

This update starts from your existing working Phase 3.1 project. It does **not** replace your PISA data or outputs.

## What this update adds

### Phase 4 — Complete intervention simulator

- Clear reasons for zero movement: already covered, missing baseline, zero implementation, or tiny percentile change.
- Comparison of every enabled intervention for one profile.
- Separate need alignment, evidence statement, expected movement, and unaddressed needs.
- Two sequential policy packages.
- Time horizons: 1 month, 6 months, 1 year, and a 3-year persistence scenario.
- Downloadable policy-comparison CSV.

### Phase 5 — Narrative-to-vector layer

- Synthetic demonstration narratives.
- Template for anonymised real-life narratives.
- Transparent phrase-based coding proposals.
- Human review of every indicator.
- Unknown information stays unknown.
- Reviewed codes map to the fixed Korean PISA reference distribution.
- Downloadable narrative result JSON.

### Phase 6 — Narrative validation

- Two independent human-coder templates.
- Automatic-code export.
- Human inter-rater exact agreement and Cohen’s kappa.
- Algorithm-versus-human-consensus agreement.
- Unknown-detection accuracy.
- Optional vector mean absolute error and Spearman correlation functions.
- Downloadable validation report.

### Credibility footer

The bottom of the site now states:

> Baseline calibrated with OECD PISA 2022 public-use microdata for South Korea. Transparent policy-scenario design is inspired by UNESCO SimuED; this is an independent student project, not an OECD or UNESCO product. Narrative layer supports anonymised user-supplied real-life cases; included demo cases are synthetic. Outputs are descriptive scenarios, not diagnoses or guaranteed individual predictions.

This wording is deliberately accurate. The app only says it includes real-life narratives after `data/narratives/real_narratives.csv` exists.

---

# Part A — Install the update

## 1. Stop the dashboard

In the terminal running Streamlit, press:

```text
Control + C
```

## 2. Back up the current project

Duplicate your current folder and rename the copy:

```text
education_model_phase1_backup_before_phase46
```

## 3. Unzip the Phase 4–6 update

Copy these items into your existing `education_model_phase1` folder:

```text
src/
config/
data/narratives/
tests/
requirements.txt
pyproject.toml
PHASE4_6_GUIDE.md
NARRATIVE_VALIDATION_METHOD.md
API_CONTRACT.md
LOVABLE_PROMPT.md
```

Choose **Replace** when macOS asks about matching code/config files.

Do not delete or replace:

```text
.venv/
data/raw/
outputs/
```

## 4. Activate the project environment

```bash
source .venv/bin/activate
```

## 5. Reinstall the updated project

```bash
python -m pip install -r requirements.txt
python -m pip install -e .
```

## 6. Run all tests

```bash
python -m pytest -q
```

Expected result:

```text
24 passed
```

You do **not** need to download PISA again or rerun the baseline pipeline.

## 7. Start the dashboard

```bash
python -m streamlit run src/education_model/dashboard.py
```

Open:

```text
http://localhost:8501
```

---

# Part B — Phase 4: Complete the policy simulator

## 1. Test the improved intervention screen

Open:

```text
Intervention simulator
```

Select a student and apply `Laptop + reliable home internet`.

The page now shows:

1. Current vector.
2. Projected vector in a separate shape.
3. A status for each dimension.
4. Underlying indicator movement.
5. Evidence, assumptions, and warnings.

Possible statuses:

```text
Measurable movement
Already covered
Cannot estimate
Small underlying change
No implemented change
```

## 2. Test a policy package

Change `Simulation type` to:

```text
Policy package
```

Try:

```text
Digital inclusion package
```

It applies, in order:

```text
Laptop + reliable home internet
→ School ICT quality upgrade
→ Guided digital-learning integration
```

The components are applied sequentially to the underlying indicators. Later components act on the remaining gap.

The model does **not** calculate:

```text
package effect = laptop effect + ICT effect + teaching effect
```

as one causal total.

## 3. Understand the time calculation

For each intervention:

```text
time factor = min(selected horizon / implementation months, 1)
```

Then:

```text
implemented strength = quality × dosage × time factor
```

Example: a school ICT upgrade takes six months in the programme design.

At one month:

```text
time factor = 1/6
```

At six months:

```text
time factor = 1
```

This is a transparent implementation-ramp assumption. It is not a universal law of educational development.

At three years, the endpoint is held constant and the page warns that long-term persistence has not been proved.

## 4. Compare all policies

Open:

```text
Policy comparison
```

Select one profile and press:

```text
Compare all enabled policies
```

You will see:

- Need alignment.
- Evidence statement and simplified badge.
- Total positive vector movement.
- Unaddressed below-median dimensions.
- Movement by dimension.

### Need alignment mathematics

For a dimension score below the Korean median:

```text
gap = (50 - current score) / 50
```

For scores at or above 50, the measured below-median gap is zero.

The policy’s need alignment is the mean gap across the dimensions it directly targets.

It is **not** a success probability. Evidence strength remains a separate field.

## 5. Export the comparison

Press:

```text
Download comparison CSV
```

This file can later be used in your paper or Lovable frontend.

---

# Part C — Phase 5: Add narratives

## 1. Test with the synthetic demos

Open:

```text
Narrative lab
```

Choose:

```text
Synthetic demo
```

Select a demo and press:

```text
Propose evidence codes
```

The automatic system only matches explicit phrases from:

```text
config/narrative_schema.json
```

It does not infer information that was not stated.

Example:

```text
“completes homework on her mother’s phone”
```

may propose low `ICTHOME`.

No statement about school belonging leaves `BELONG` as:

```text
unknown
```

## 2. Review every proposal

For each indicator, confirm or change:

```text
unknown
very_low
low
typical
high
very_high
```

Also check the evidence quotation.

Then press:

```text
Calculate reviewed narrative vector
```

## 3. Understand the narrative mathematics

Reviewed levels map to declared Korean reference quantiles:

```text
very_low  → 10th percentile indicator value
low       → 25th percentile indicator value
typical   → 50th percentile indicator value
high      → 75th percentile indicator value
very_high → 90th percentile indicator value
unknown   → missing
```

The indicators are then combined using the same baseline vector formula.

A vector dimension only appears when it meets the same minimum-indicator rule as the PISA model.

This mapping is a transparent calibration rule. It must be tested in Phase 6; it is not claimed to be an objective diagnosis.

## 4. Add anonymised real-life narratives

Open:

```text
data/narratives/narratives_template.csv
```

Make a copy called:

```text
data/narratives/real_narratives.csv
```

Use columns:

```text
narrative_id
narrative_text
source_type
consent_status
synthetic
```

Example:

```csv
narrative_id,narrative_text,source_type,consent_status,synthetic
CASE001,"Anonymous narrative here",interview,confirmed,false
```

### Privacy rules

Do not include:

- Names.
- Addresses.
- Phone numbers or email addresses.
- Exact school names.
- Student numbers.
- Details that make a child identifiable.
- Narratives collected without appropriate permission.

For a school research project, obtain teacher/supervisor approval and use the consent process required by your school before collecting personal accounts.

Once `real_narratives.csv` exists, the footer changes from “supports real-life narratives” to “includes anonymised user-supplied real-life cases.”

## 5. Export a narrative result

After human review, press:

```text
Download narrative result JSON
```

This includes:

- Reviewed codes.
- Evidence quotations.
- Indicator reference quantiles.
- Five-vector output.
- Evidence coverage.
- Missing dimensions.
- Warnings.

---

# Part D — Phase 6: Validate narrative coding

## 1. Prepare the narratives

A useful pilot is approximately 30–50 varied narratives, if you can obtain them ethically. More important than the number is that they cover different combinations of resources, support, digital access, agency, wellbeing, and missing information.

Do not let human coders see the automatic proposal before coding.

## 2. Download two coder templates

Open:

```text
Narrative validation
```

Press:

```text
Download coder A template
Download coder B template
```

Give them to two independent coders.

Each coder fills:

```text
narrative_id
coder_id
indicator
level
evidence_quote
```

## 3. Generate automatic codes

Create a CSV containing:

```text
narrative_id,narrative_text
```

Upload it under:

```text
Optional: generate automatic codes for a narrative CSV
```

Download:

```text
algorithm_codes.csv
```

## 4. Run validation

Upload both completed human files.

Optionally upload `algorithm_codes.csv`.

Press:

```text
Run narrative validation
```

The report calculates:

### Human inter-rater agreement

- Exact agreement.
- Cohen’s kappa overall.
- Cohen’s kappa per indicator.
- Number of overlapping coding decisions.

### Algorithm versus human consensus

- Exact agreement.
- Cohen’s kappa.
- Unknown-detection accuracy.
- Per-indicator results.
- Number of unresolved human disagreements excluded.

With two coders, only exact agreement becomes consensus. Disagreements remain unresolved.

## 5. Interpret the report correctly

Do not say:

```text
Kappa above one chosen threshold proves validity.
```

Instead inspect:

- Sample size per indicator.
- Exact agreement.
- Kappa.
- Which labels are confused.
- Whether the algorithm correctly keeps missing information unknown.
- The actual disagreement examples and evidence quotations.

If one indicator performs badly, revise only that indicator’s definition and phrase rules, then rerun the validation.

## 6. Save the report

Press:

```text
Download validation report JSON
```

Store it in:

```text
outputs/narrative_validation_report.json
```

---

# Part E — Test the updated API

Start FastAPI:

```bash
uvicorn education_model.api:app --reload --host 127.0.0.1 --port 8000
```

Open:

```text
http://127.0.0.1:8000/docs
```

New endpoints include:

```text
GET  /api/methodology
GET  /api/packages
POST /api/simulate-package
POST /api/compare
POST /api/narratives/propose
POST /api/narratives/score
```

The local Streamlit dashboard remains the scientific reference interface. Reproduce the same outputs in Lovable only after these endpoints match the dashboard.

---

# What is now complete

```text
[✓] Baseline PISA vectors
[✓] Student-specific interventions
[✓] Clear zero-change explanations
[✓] Policy comparison
[✓] Need-alignment analysis
[✓] Sequential policy packages
[✓] Time-horizon implementation scenarios
[✓] Evidence-first narrative coding
[✓] Human review
[✓] Narrative-to-vector mapping
[✓] Two-coder validation toolkit
[✓] Credibility footer
```

The next phase after this is deployment and the Lovable frontend, followed by the research paper.
