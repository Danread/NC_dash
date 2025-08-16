# UKCEH NC Labour Explorer (with NC_type & Area stacks)

- Adds **NC_type** global filter (optional).
- New plot in **Project split** tab: **B. Stacked by Project within each Science Area**, with Percent ↔ Hours toggle.
- Existing plots remain, all filters apply (Areas, Projects, Staff, NC_type, min-hours).
- Layout auto-detect (explicit `Project`/`Person`/`NC_type` columns or header+staff format).

## Local run
```bash
python3 -m pip install -r requirements.txt
streamlit run app.py
```
(Optional for exports)
```bash
python3 -m pip install kaleido python-pptx
```

## Streamlit Community Cloud
Push to GitHub and deploy `app.py`.
