# Apply this update to your existing project

1. Back up your current project folder.
2. Unzip this update.
3. Copy the following into your existing `education_model_phase1` folder and allow replacement:
   - `src/`
   - `config/`
   - `tests/`
   - `pyproject.toml`
   - `requirements.txt`
   - `PHASE2_GUIDE.md`
   - `INTERVENTION_METHOD.md`
4. Keep your existing `data/raw/` and `outputs/` folders. Do not copy or redownload the 2 GB PISA file.
5. In the VS Code terminal, activate `.venv`, run `python -m pip install -e .`, run `python -m pytest -q`, and rerun the baseline pipeline once.
