# UKCEH NC Labour Explorer (default dataset + upload override)

Features:
- Default dataset hard-coded: **NC_analysis_dash.xlsx** (included).
- Upload box to override data at runtime.
- Filters: Science Area, Project, Staff, NC_type, Hide Professional Services, Min total project hours.
- Global **Percent ↔ Hours** toggle.
- Tab 1: Radio toggle between **Projects stacked by Science Area** and **Science Areas stacked by Project**.
- Tab 2: Distribution within a science area (horizontal bars).
- Tab 3: Staff workload (by project).
- Tab 4: **Project → staff distribution (single project)**.
- Tab 5: Exports (PNG via kaleido, PowerPoint via python-pptx).

## Run locally
```bash
python3 -m venv .venv
source .venv/bin/activate           # Windows: .venv\Scripts\activate
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
streamlit run app.py
```

If PNG/PPT exports warn about dependencies, install:
```bash
python -m pip install -U kaleido python-pptx
```
