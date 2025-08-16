# UKCEH NC Labour Explorer (GitHub-ready)

- Funder Type fully removed.
- App renamed to **UKCEH NC Labour Explorer**.
- Global **% ↔ hours** toggle for all charts.
- Layout auto-detect, reset filters, robust slider, defaults save/load.
- Optional PNG/PPT exports (enabled if `kaleido` / `python-pptx` installed).

## Local run
```bash
python3 -m pip install -r requirements.txt
streamlit run app.py
```

## Streamlit Community Cloud
Push these files to a GitHub repo and deploy via share.streamlit.io.
Add to `requirements.txt` if you want exports:
```
kaleido
python-pptx
```
