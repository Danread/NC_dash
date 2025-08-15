# Labour Portfolio Explorer — GitHub/Streamlit-ready (optional exports)

This build is ready for **Streamlit Community Cloud** (share.streamlit.io). It does **not** include any data files; users will upload a CSV/XLSX at runtime.

## Features
- Project + Staff parsing (project rows start with a digit; staff rows follow).
- Filters: projects, science areas, staff, hide Professional Services (default), min-hours threshold.
- Optional **Funder Type** filter via a small metadata CSV (columns: `Project`, `Funder Type`).
- Project split chart with **%/hours toggle** (100% normalised after filters).
- Staff workload views.
- **Save/Load defaults** as a JSON file.
- **Optional exports** (only shown if dependency is available):
  - PNG export (requires `kaleido`)
  - PPTX export (requires `python-pptx` + `kaleido`)

## Deploy on Streamlit Community Cloud
1. Create a new GitHub repo and add:
   - `app.py`
   - `requirements.txt`
   - `README.md`
   - `.gitignore` (optional)
2. Go to https://share.streamlit.io, connect your GitHub, and deploy the repo.
3. Upload your labour file (and optional funder CSV) in the app UI.

## Local run
```bash
pip install -r requirements.txt
streamlit run app.py
```
If you want PNG/PPT exports locally:
```bash
pip install kaleido python-pptx
```

## Data format
- Column 1: **Project** ID (e.g., starts with digits). Rows under a project are treated as **staff** names.
- Columns 2..n: science area/business unit **hours** (numeric). Empty cells are treated as 0.
