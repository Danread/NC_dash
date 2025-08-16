# UKCEH NC Labour Explorer — Exports enabled

- First tab has a **radio toggle**: Projects↔Areas stacked views.
- **PNG & PowerPoint exports enabled** (kaleido + python-pptx included).
- Global %↔Hours toggle; filters for Science Area, Project, Staff, NC_type; min-hours slider; Hide PS.

## Run locally
```bash
python3 -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate
python3 -m pip install --upgrade pip
python3 -m pip install -r requirements.txt
streamlit run app.py
```

## Streamlit Community Cloud
Push `app.py` + `requirements.txt` and deploy. No special config required for exports.
