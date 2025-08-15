# Labour Portfolio Explorer (with Professional Services toggle & Funder filter)

This version adds:
- A sidebar checkbox to **Hide 'Professional Services'** (enabled by default).
- An optional **Funder Type** filter (upload a metadata CSV with columns: `Project`, `Funder Type`).

## Deploy on Streamlit Community Cloud
1. Add `app.py`, `requirements.txt`, `README.md`, `.gitignore` to a GitHub repo.
2. Deploy from https://share.streamlit.io
3. Users upload their Excel/CSV; optionally upload a project→funder CSV to enable the funder filter.

## Local run
```bash
pip install -r requirements.txt
streamlit run app.py
```

## Data format
- Labour file: Column 1 = Project name/ID; Columns 2..n = science areas (numeric hours)
- Optional metadata CSV: Columns = `Project`, `Funder Type` (or `FunderType`)
