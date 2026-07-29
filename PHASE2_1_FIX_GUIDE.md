# Phase 2.1 Fix: unassigned groups and zero intervention movement

## Why `ANALYSIS_GROUP` was NaN

This was expected for profiles outside the deliberately narrow four-group comparison. A profile is unassigned when:

- its family-background index is in the middle 50%;
- its school location is PISA category 3 (`town`), which was excluded from the rural/urban contrast; or
- a required grouping variable is missing.

The profile still has valid vector scores. It is simply not used in the four extreme comparison groups.

The updated inspector hides unassigned profiles by default. Use `--include-unassigned` only when you deliberately want to see them.

## Why a laptop simulation could show zero movement

A zero result is valid in either of these cases:

1. `ICTHOME` is missing. Missing means unknown, not low, so the model refuses to invent a baseline gap.
2. The profile is already at or above the Korean 90th-percentile `ICTHOME` target.
3. Quality or dosage is zero.

The updated simulator now prints the exact reason.

## Install the fix

Copy the update into the existing project folder, activate the virtual environment, and run:

```bash
python -m pip install -e .
python -m pytest -q
```

The baseline data do not need to be downloaded or recalculated.

## Show random profiles from the four comparison groups only

```bash
python -m education_model.inspect_profiles --mode random --n 8
```

## Deliberately include unassigned profiles

```bash
python -m education_model.inspect_profiles --mode random --n 8 --include-unassigned
```

## Find profiles that will respond to the laptop package

```bash
python -m education_model.inspect_profiles \
  --intervention laptop_internet_package \
  --n 8
```

The table includes the expected digital-access movement. Copy any displayed `PROFILE_ID` into the simulation command.

## Automatically select a responsive profile

```bash
python -m education_model.simulate \
  --profile-id auto \
  --intervention laptop_internet_package
```

## Simulate a particular responsive profile

```bash
python -m education_model.simulate \
  --profile-id KOR000123 \
  --intervention laptop_internet_package
```

Replace `KOR000123` with an ID returned by the responsive-profile command.
