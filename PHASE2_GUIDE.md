# Phase 2 beginner guide: inspect profiles and simulate interventions

This guide assumes Phase 1 already runs successfully and your original PISA `.sav` files remain inside `data/raw`.

## A. Replace the project code safely

1. Make a backup copy of your current `education_model_phase1` folder.
2. Unzip the updated package.
3. Copy these updated items into your existing project, replacing the older versions when prompted:
   - `src/education_model/`
   - `config/`
   - `tests/`
   - `pyproject.toml`
   - `requirements.txt`
4. Do **not** delete or replace your existing `data/raw` folder.

## B. Open the terminal in the project

```bash
cd /path/to/education_model_phase1
source .venv/bin/activate
```

Confirm:

```bash
pwd
ls
```

## C. Reinstall the updated local package

```bash
python -m pip install -e .
```

Then run all tests:

```bash
python -m pytest -q
```

Expected result: nine tests pass.

## D. Rerun the baseline pipeline once

The updated pipeline creates an additional file containing anonymous profile IDs, raw composite scores, and aligned indicator z-scores.

```bash
python -m education_model.pipeline \
  --data-dir data/raw \
  --manifest config/indicator_manifest.json \
  --output-dir outputs
```

After completion:

```bash
ls -lh outputs
```

Confirm this new file exists:

```text
outputs/korea_model_profiles.csv.gz
```

## E. View real anonymous student vectors

Show representative profiles:

```bash
python -m education_model.inspect_profiles
```

The table displays anonymous IDs such as `KOR000123` and their five vector values.

Show eight random profiles:

```bash
python -m education_model.inspect_profiles --mode random --n 8
```

Show the complete calculation for one profile:

```bash
python -m education_model.inspect_profiles \
  --profile-id KOR000123 \
  --details
```

Replace `KOR000123` with an ID that appeared in your table.

The detailed output shows:

- every aligned indicator z-score;
- the equal-weight raw average;
- the final Korea-relative percentile;
- the exact roles of each indicator.

## F. See the code behind the initial vectors

Open these files in this order:

1. `config/indicator_manifest.json` — indicator recipe
2. `src/education_model/scoring.py` — alignment, winsorisation, z-scores, composites
3. `src/education_model/math_utils.py` — weighted statistical functions
4. `src/education_model/pipeline.py` — full workflow and exported profile file
5. `src/education_model/inspect_profiles.py` — readable explanation tool

## G. List available interventions

```bash
python -m education_model.simulate --list
```

Enabled interventions include:

- `laptop_internet_package`
- `school_ict_upgrade`
- `school_resource_upgrade`
- `growth_mindset_workshop`
- `whole_school_belonging_program`
- `structured_tutoring`

`generic_hagwon_access` is deliberately disabled until it is precisely defined.

## H. Simulate one intervention

Example laptop package:

```bash
python -m education_model.simulate \
  --profile-id KOR000123 \
  --intervention laptop_internet_package
```

Example growth-mindset workshop:

```bash
python -m education_model.simulate \
  --profile-id KOR000123 \
  --intervention growth_mindset_workshop \
  --scenario central
```

Example tutoring:

```bash
python -m education_model.simulate \
  --profile-id KOR000123 \
  --intervention structured_tutoring \
  --scenario central
```

The output separates:

- baseline vector;
- projected vector;
- vector change;
- targeted indicator change;
- evidence-based learning-outcome effect, when relevant;
- assumptions and warnings.

## I. Use quality and dosage

Both range from 0 to 1.

Example: 70% implementation quality and half of the intended dosage:

```bash
python -m education_model.simulate \
  --profile-id KOR000123 \
  --intervention laptop_internet_package \
  --quality 0.7 \
  --dosage 0.5
```

These controls should describe real programme delivery. Do not tune them simply to obtain a preferred result.

## J. Save one simulation as JSON

```bash
python -m education_model.simulate \
  --profile-id KOR000123 \
  --intervention laptop_internet_package \
  --json-output outputs/example_simulation.json
```

This JSON is the format a future FastAPI endpoint or Lovable frontend can consume.

## K. Where the intervention algorithm lives

- `config/intervention_manifest.json` — exact intervention parameters and warnings
- `config/intervention_evidence.csv` — evidence registry
- `src/education_model/interventions.py` — mathematical engine
- `src/education_model/simulate.py` — terminal interface
- `INTERVENTION_METHOD.md` — methodological justification
- `tests/test_interventions.py` — tests preventing accidental changes

## L. Do not move to the website yet

First run at least three different interventions on three different profiles. Confirm that:

1. untouched dimensions remain unchanged;
2. low-access profiles usually move more under direct gap-closing interventions;
3. all scores remain between 0 and 100;
4. tutoring outcome effects remain separate from vector effects;
5. assumptions and proxy warnings appear in the terminal.
