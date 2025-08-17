
# UKCEH NC Labour Explorer — GitHub-ready (Regenerated)

Interactive Streamlit app for exploring NC labour allocation.

## Deploy on Streamlit Community Cloud
1. Push this folder to a GitHub repo (public or private).
2. Go to https://share.streamlit.io → **New app** → select your repo/branch → set main file to `app.py` → Deploy.
3. (Optional, recommended) Add login:
   - In the app’s **Settings → Secrets**, paste content like:
     ```toml
     [auth_cookie]
     name = "ukceh_nc_labour_cookie"
     key = "some-long-random-string"
     expiry_days = 7

     [credentials.usernames.daniel]
     name = "Daniel Read"
     email = "daniel.read@ceh.ac.uk"
     password = "$2b$12$your_bcrypt_hash_here"
     ```
   - Generate password hash locally:
     ```python
     import streamlit_authenticator as stauth
     print(stauth.Hasher(["YourPasswordHere"]).generate()[0])
     ```

## Run locally
```bash
python3 -m venv .venv
source .venv/bin/activate           # Windows: .venv\Scripts\activate
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
streamlit run app.py
```

## Data
- Default dataset: `NC_analysis_dash.xlsx` (included). You can also upload a new file at runtime.
