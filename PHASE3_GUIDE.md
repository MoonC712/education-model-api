# Phase 3 beginner guide: visualization, API, and Lovable

This phase uses the **derived output files you already created**. You do not download or process the 2 GB PISA file again.

## What you will build

```text
Existing Python model
        ↓
Local Streamlit + Plotly dashboard
        ↓
FastAPI data and simulation endpoints
        ↓
Public API deployment
        ↓
Lovable frontend
```

The local dashboard is the first checkpoint. Do not move to Lovable until the local charts and simulation are correct.

---

## Part A — Install the Phase 3 update

1. Duplicate your current `education_model_phase1` folder as a backup.
2. Unzip `education_model_phase3_update.zip`.
3. Copy its contents into your existing project folder.
4. Choose **Replace** for matching source/config/test files.
5. Do not delete `.venv`, `data/raw`, or `outputs`.

Open the project folder in VS Code and activate the environment:

```bash
source .venv/bin/activate
```

Install the new packages and the updated project:

```bash
python -m pip install -r requirements.txt
python -m pip install -e .
```

Run all tests:

```bash
python -m pytest -q
```

Expected result: the earlier tests plus six Phase 3 tests pass.

---

## Part B — Check that visualization data are ready

Run:

```bash
python -m education_model.check_visualization
```

A successful result ends with:

```text
Phase 3 files are ready.
```

If it says `korea_model_profiles.csv.gz` is missing, rerun the updated pipeline:

```bash
python -m education_model.pipeline \
  --data-dir data/raw \
  --manifest config/indicator_manifest.json \
  --output-dir outputs
```

Do not rerun the downloader.

---

## Part C — Start the local dashboard

Run:

```bash
python -m streamlit run src/education_model/dashboard.py
```

Your browser should open a local page, normally:

```text
http://localhost:8501
```

Keep the terminal open while using the dashboard. To stop it later, click the terminal and press `Control + C`.

### Checkpoint 1: Group overview

Confirm that:

- four group labels appear;
- every chart uses a 0–100 vertical or radial scale;
- the grouped bars match `outputs/four_group_archetypes.csv`;
- error bars appear where standard errors are available.

### Checkpoint 2: Student explorer

Select a profile. Confirm that:

- radar and bar values agree;
- the indicator table appears;
- the profile ID matches a row in `outputs/korea_model_profiles.csv.gz`.

### Checkpoint 3: Intervention simulator

Choose:

- a profile with low digital access;
- `Laptop + reliable home internet`;
- central scenario;
- quality 1.0;
- dosage 1.0.

Confirm that digital access changes while unrelated dimensions remain unchanged. The indicator table should explain the underlying ICTHOME z-score movement.

### Checkpoint 4: Population map

Try both 2D and 3D. The highlighted profile should remain visible. PCA axes are visualization coordinates, not additional educational constructs.

---

## Part D — Start the local FastAPI server

Open a **second VS Code terminal**. Activate the same environment:

```bash
source .venv/bin/activate
```

Start the API:

```bash
uvicorn education_model.api:app --reload --host 127.0.0.1 --port 8000
```

Open this in your browser:

```text
http://127.0.0.1:8000/docs
```

FastAPI automatically shows an interactive endpoint page.

Test the API from a third terminal:

```bash
python scripts/smoke_test_api.py
```

You should see `/health`, `/api/summary`, and `/api/interventions` followed by `OK`.

To test a simulation inside `/docs`:

1. Open `POST /api/simulate`.
2. Click **Try it out**.
3. Paste:

```json
{
  "profile_id": "REPLACE_WITH_A_REAL_ID",
  "intervention": "laptop_internet_package",
  "scenario": "central",
  "quality": 1,
  "dosage": 1
}
```

4. Replace the ID with one from the dashboard.
5. Click **Execute**.

---

## Part E — Prepare a small GitHub repository

Do **not** upload the raw `.sav` or ZIP files. They are large and unnecessary for the app.

The included `.gitignore` keeps `data/raw` excluded while allowing these derived outputs:

```text
outputs/korea_model_profiles.csv.gz
outputs/korea_scored_anonymous.csv.gz
outputs/four_group_archetypes.csv
outputs/representative_prototypes.csv
outputs/run_summary.json
outputs/validation_report.json
```

Before committing, check:

```bash
git status
```

If a 2 GB `.sav` file appears, stop and check `.gitignore` before pushing.

Create the repository:

```bash
git init
git add .
git commit -m "Add educational opportunity model API and dashboard"
```

Create an empty GitHub repository in your browser, then follow GitHub's displayed commands to add the remote and push.

---

## Part F — Deploy the API on Render

The project contains `render.yaml`.

1. Sign in to Render.
2. Create a new Blueprint or Web Service from your GitHub repository.
3. Use the included settings:
   - Build: `pip install -r requirements.txt && pip install -e .`
   - Start: `uvicorn education_model.api:app --host 0.0.0.0 --port $PORT`
   - Health path: `/health`
4. After deployment, open your Render URL followed by `/health`.
5. Then open the URL followed by `/docs`.

The first version permits all CORS origins because the API is anonymous, contains no credentials, and has no write endpoints. After Lovable is published, replace `EDU_MODEL_CORS_ORIGINS=*` with the exact Lovable origin.

Do not deploy the Streamlit dashboard unless you specifically want it as a separate public prototype. Lovable will become the final frontend.

---

## Part G — Build the Lovable frontend

Open `LOVABLE_PROMPT.md`.

1. Copy the full prompt.
2. Replace `YOUR_PUBLIC_API_URL` with your Render API URL.
3. Paste it into a new Lovable project.
4. Let Lovable build the first interface.
5. Test every page against the API.
6. Connect Lovable to GitHub after the first working version, so frontend changes are backed up and editable locally.

Lovable should not store or reproduce the raw PISA files. It should call the API and render the returned JSON.

---

## Final validation checklist

Before calling the visualization complete:

- Group charts match the CSV output.
- Student radar and bar values match each other.
- Intervention changes match the terminal simulation for the same profile and settings.
- Zero movement displays its reason.
- Missing values are shown as unknown, never converted to zero.
- Outcome evidence remains separate from vector movement.
- PCA is labelled as dimensionality reduction.
- Every intervention displays assumptions and warnings.
- The interface never calls results guaranteed predictions.
