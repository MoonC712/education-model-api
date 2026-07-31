# Phase 3.1 — Separate Current and Projected Five-Vector Panels

This is a small interface update for the existing Streamlit dashboard. It does not change the baseline model, PISA data, intervention mathematics, API, or output files.

## What changes

The Intervention Simulator now works in this order:

1. Select an anonymous student.
2. See a permanent **Current state** section with:
   - its own five-axis radar chart;
   - its own five-value bar chart;
   - five exact numerical values.
3. Choose one intervention, evidence scenario, implementation quality, and dosage.
4. Press **Apply intervention**.
5. A separate **Projected state after intervention** section appears with:
   - a second independent radar chart;
   - a second independent five-value bar chart;
   - five projected values and changes.
6. A comparison chart and Current/Projected/Change table appear underneath.

The projected state does not appear before the button is pressed. Changing the student clears the previous projected state.

---

## Step 1 — Back up the current dashboard file

Inside your existing `education_model_phase1` project, duplicate:

```text
src/education_model/dashboard.py
```

Rename the duplicate:

```text
src/education_model/dashboard_before_phase3_1.py
```

---

## Step 2 — Copy the update

Unzip `education_model_phase3_1_intervention_ui.zip`.

Copy its `src` folder into the main `education_model_phase1` folder.

When macOS asks whether to replace `dashboard.py`, choose **Replace**.

You may also replace `LOVABLE_PROMPT.md`; it now asks Lovable to reproduce the same separate current/projected layout later.

Do not change or delete:

```text
.venv/
data/raw/
outputs/
config/
```

---

## Step 3 — Open the project terminal

Make sure the terminal is inside your existing project folder:

```bash
pwd
```

The final folder name should be:

```text
education_model_phase1
```

Activate the virtual environment:

```bash
source .venv/bin/activate
```

---

## Step 4 — No model rerun is required

You do not need to:

- download PISA again;
- rerun the baseline pipeline;
- rerun intervention calculations;
- recreate output files.

This update changes only the Streamlit interface.

Run the tests:

```bash
python -m pytest -q
```

The same test count as before should pass.

---

## Step 5 — Restart Streamlit

If Streamlit is already running, return to its terminal and press:

```text
Control + C
```

Then restart it:

```bash
python -m streamlit run src/education_model/dashboard.py
```

Open:

```text
http://localhost:8501
```

---

## Step 6 — Test the new Intervention Simulator

1. Open the **Intervention simulator** tab.
2. Select a comparison group and anonymous profile.
3. Confirm that **Current state** appears immediately.
4. Confirm that no projected panel appears yet.
5. Select `Laptop + reliable home internet`.
6. Keep scenario `central`, quality `1.0`, and dosage `1.0`.
7. Press **Apply intervention**.
8. Confirm that a separate **Projected state after** section appears below.

The page should now show:

```text
CURRENT STATE
[Current radar] [Current bars]
[5 current values]

CHOOSE INTERVENTION
[controls]
[Apply intervention]

PROJECTED STATE AFTER INTERVENTION
[Projected radar] [Projected bars]
[5 projected values + changes]

DIRECT BEFORE-AND-AFTER COMPARISON
[grouped bars] [current/projected/change table]
```

---

## Expected behaviour

For a responsive laptop profile, Digital access should change while unrelated dimensions stay fixed.

For example:

```text
Current digital access:   18.7
Projected digital access: 54.9
Change:                  +36.2
```

The exact values will depend on the chosen anonymous profile.

If no dimension changes, the projected panel still appears and explains the reason, such as:

- the student is already above the target;
- the relevant indicator is missing;
- quality or dosage is zero.

---

## Important interpretation

The current panel is the PISA-derived descriptive baseline.

The projected panel is a scenario generated under the selected intervention assumptions. It is not a guaranteed causal prediction for an identifiable child.
