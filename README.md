# UKCEH NC Labour Explorer (with NC_type & radio toggle for split views)

- Adds **NC_type** global filter (optional).
- **Project split** tab now has a **radio toggle** to switch between:
  - Projects stacked by Science Area (original)
  - Science Areas stacked by Project (new)
- Export tab downloads the **currently selected** split view.
- All filters (Areas, Projects, Staff, NC_type, min-hours, Hide PS) cascade across all tabs.

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
