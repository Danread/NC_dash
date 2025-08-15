# Labour Portfolio Explorer (GitHub/Streamlit-ready)

A Streamlit app to explore labour hours across projects and science areas.

## Deploy on Streamlit Community Cloud (no sensitive data committed)
1. Create a new GitHub repo and add these files: `app.py`, `requirements.txt`, `README.md`.
2. Go to https://share.streamlit.io, connect your GitHub, and deploy the repo.
3. When the app opens, **upload your Excel/CSV** from your computer. The app does not store data.

## Local run
```bash
pip install -r requirements.txt
streamlit run app.py
```

## Data format
- Column 1: Project name/ID (string)
- Columns 2..n: Science areas / business units (numeric hours)
- Empty cells are treated as 0
