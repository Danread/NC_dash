# Labour Portfolio Explorer (GitHub/Streamlit-ready, bugfix)

This version fixes a KeyError in the '% distribution within a selected science area' chart by calculating the area total directly.

## Deploy on Streamlit Community Cloud
1. Add `app.py`, `requirements.txt`, `README.md`, `.gitignore` to a GitHub repo.
2. Deploy from https://share.streamlit.io
3. Users upload their own Excel/CSV at runtime.

## Local run
```bash
pip install -r requirements.txt
streamlit run app.py
```

## Data format
- Column 1: Project name/ID (string)
- Columns 2..n: Science areas / business units (numeric hours)
- Empty cells are treated as 0
