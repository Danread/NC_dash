# Labour Portfolio Explorer — GitHub/Streamlit-ready (optional exports, robust slider)

This build fixes a slider-bound issue seen on Streamlit Cloud and keeps PNG/PPT exports optional.

## Deploy on Streamlit Community Cloud
1. Add `app.py`, `requirements.txt`, `README.md`, `.gitignore` to a new GitHub repo.
2. Deploy from https://share.streamlit.io
3. Upload your labour CSV/XLSX (and optional funder-type CSV).

## Local run
```bash
pip install -r requirements.txt
streamlit run app.py
```

## Optional exports
- Enable PNG export by adding `kaleido` to `requirements.txt`.
- Enable PowerPoint export by adding **both** `kaleido` and `python-pptx`.
