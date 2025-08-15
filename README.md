# Labour Portfolio Explorer — staff view fix

- Fixes `NameError` caused by `dict(ticksuffix,"%")` → now `dict(ticksuffix="%")`.
- Removes the staff pie chart. The **Staff** tab now shows **only** "% distribution of a staff member's hours across projects".
- Keeps all previous hardening (layout auto-detect, reset filters, robust slider, optional exports, %↔hours toggle).

## Deploy on Streamlit Community Cloud
Add these files to a GitHub repo and deploy via share.streamlit.io.
