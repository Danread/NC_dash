# UKCEH NC Labour Explorer (with NC_type filter)

Adds an **NC_type** multiselect that filters all visuals. The column is optional; if present (exact header `NC_type`, case-insensitive), it will be used in Layout A or B.

## Local run
```bash
python3 -m pip install -r requirements.txt
streamlit run app.py
```
Optional for exports:
```bash
python3 -m pip install kaleido python-pptx
```

## Streamlit Community Cloud
Push to GitHub (app.py, requirements.txt) and deploy. Set main file to `app.py`.
