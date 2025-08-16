
import re
import io
from pathlib import Path

import numpy as np
import pandas as pd
import plotly.express as px
import plotly.io as pio
import streamlit as st

# Optional exports
HAS_PPTX = False
HAS_KALEIDO = False
try:
    import kaleido  # noqa: F401
    HAS_KALEIDO = True
except Exception:
    HAS_KALEIDO = False

try:
    from pptx import Presentation
    from pptx.util import Inches
    HAS_PPTX = True
except Exception:
    HAS_PPTX = False

APP_TITLE = "UKCEH NC Labour Explorer"
DEFAULT_DATA_FILE = "NC_analysis_dash.xlsx"  # included in repo; can be replaced/updated

st.set_page_config(page_title=APP_TITLE, layout="wide")
st.title(APP_TITLE)
st.caption("Default data is preloaded from **NC_analysis_dash.xlsx** in the repo. You can override it by uploading a new file below.")

# ------------------------------- Data loading -------------------------------
def read_default_dataset():
    path = Path(__file__).parent / DEFAULT_DATA_FILE
    if path.exists():
        try:
            return pd.read_excel(path, sheet_name=0)
        except Exception:
            pass
    return None

uploaded = st.file_uploader("Upload Excel (.xlsx) or CSV to override the default dataset", type=["xlsx","csv"])

df_raw = None
if uploaded is not None:
    try:
        if uploaded.name.lower().endswith(".csv"):
            df_raw = pd.read_csv(uploaded)
        else:
            df_raw = pd.read_excel(uploaded, sheet_name=0)
        st.success(f"Using uploaded file: {uploaded.name}")
    except Exception as e:
        st.error(f"Could not read uploaded file: {e}")

if df_raw is None:
    df_raw = read_default_dataset()
    if df_raw is not None:
        st.info(f"Using default data from repository: {DEFAULT_DATA_FILE}")
    else:
        st.error("No data available. Please upload a valid Excel/CSV file.")
        st.stop()

if df_raw.shape[1] < 2:
    st.error("Expected at least 2 columns in the dataset.")
    st.stop()

# ------------------------------- Schema detect ------------------------------
cols_lower = {c.lower().strip(): c for c in df_raw.columns}
has_project_col = "project" in cols_lower
has_person_col = "person" in cols_lower
has_nc_type_col = "nc_type" in cols_lower or "nc type" in cols_lower
nc_col_name = cols_lower.get("nc_type", cols_lower.get("nc type", None))

exclude = set(filter(None, [cols_lower.get("project"), cols_lower.get("person"), nc_col_name]))
value_cols = [c for c in df_raw.columns if c not in exclude and c.lower().strip() not in ("grand total","total","grand_total")]

if not value_cols:
    st.error("Could not find any science area columns (numeric).")
    st.stop()

df = df_raw.copy()
for c in value_cols + [c for c in df_raw.columns if c.lower() in ("grand total","total","grand_total")]:
    if c in df.columns:
        df[c] = pd.to_numeric(df[c], errors="coerce")
df[value_cols] = df[value_cols].fillna(0.0)

def is_project_id(x: str) -> bool:
    if not isinstance(x, str):
        return False
    return bool(re.match(r"^\s*\d", x))

def is_total_like(x: str) -> bool:
    if not isinstance(x, str):
        return False
    return bool(re.match(r"^\s*(grand\s+)?totals?$", x.strip().lower()))

# Build long
if has_project_col:
    proj_col = cols_lower["project"]
    pers_col = cols_lower["person"] if has_person_col else None
    id_vars = [proj_col] + ([pers_col] if pers_col else [])
    if has_nc_type_col and nc_col_name not in id_vars:
        id_vars.append(nc_col_name)
    long = df.melt(id_vars=id_vars, value_vars=value_cols, var_name="Science Area", value_name="Hours")
    long = long.rename(columns={proj_col: "Project"})
    if pers_col and pers_col != "Person":
        long = long.rename(columns={pers_col: "Person"})
    if "Person" not in long.columns:
        long["Person"] = None
    if has_nc_type_col and nc_col_name != "NC_type":
        long = long.rename(columns={nc_col_name: "NC_type"})
    if "NC_type" not in long.columns and has_nc_type_col:
        long["NC_type"] = df[nc_col_name]
    long = long[~long["Project"].astype(str).apply(is_total_like)]
else:
    project_col_src = df.columns[0]
    records = []
    current_project = None
    for _, row in df.iterrows():
        name = row[project_col_src]
        if pd.isna(name):
            continue
        if is_total_like(str(name)):
            continue
        current_nc = row[nc_col_name] if has_nc_type_col else None
        if is_project_id(str(name)):
            current_project = str(name).strip()
            for area in value_cols:
                val = row.get(area, np.nan)
                if pd.notna(val) and float(val) != 0.0:
                    records.append({"Project": current_project, "Person": None, "NC_type": current_nc,
                                    "Science Area": area, "Hours": float(val)})
        else:
            person = str(name).strip()
            for area in value_cols:
                val = row.get(area, np.nan)
                if pd.notna(val) and float(val) != 0.0:
                    records.append({"Project": current_project, "Person": person, "NC_type": current_nc,
                                    "Science Area": area, "Hours": float(val)})
    long = pd.DataFrame.from_records(records)

if "NC_type" not in long.columns: long["NC_type"] = None
if "Person" not in long.columns:  long["Person"]  = None

long["Hours"] = pd.to_numeric(long["Hours"], errors="coerce")
long = long.replace({np.inf: np.nan, -np.inf: np.nan})
long = long[long["Hours"].fillna(0) > 0.0]
long = long[~long["Science Area"].astype(str).str.strip().str.lower().isin(["grand total","total","grand_total"])]

proj_tot = long.groupby("Project", as_index=False)["Hours"].sum().rename(columns={"Hours":"Project Hours"})
area_tot = long.groupby("Science Area", as_index=False)["Hours"].sum().rename(columns={"Hours":"Area Hours"})
long = long.merge(proj_tot, on="Project", how="left").merge(area_tot, on="Science Area", how="left")

person_tot = long.dropna(subset=["Person"]).groupby("Person", as_index=False)["Hours"].sum().rename(columns={"Hours":"Person Hours"})
if not person_tot.empty:
    long = long.merge(person_tot, on="Person", how="left")
else:
    long["Person Hours"] = np.nan

# ------------------------------- Sidebar -----------------------------------
with st.sidebar:
    st.header("Filters")
    if st.button("🔄 Reset filters to defaults"):
        for k in ["selected_areas","selected_projects","selected_people","selected_nc_types",
                  "hide_ps","min_total","global_view_mode","split_view_choice",
                  "selected_area_single","selected_staff_single","selected_project_single"]:
            if k in st.session_state:
                del st.session_state[k]
        st.rerun()

    hide_ps = st.checkbox("Hide 'Professional Services'", value=st.session_state.get("hide_ps", True), key="hide_ps")

    st.markdown("**Display values as**")
    st.radio("Display mode", ["Percent","Absolute hours"], horizontal=True, key="global_view_mode", label_visibility="collapsed")

    if long["NC_type"].notna().any():
        nc_all = sorted([str(x) for x in long["NC_type"].dropna().unique().tolist()])
        prev_nc = [x for x in st.session_state.get("selected_nc_types", nc_all) if x in nc_all] or nc_all
        st.multiselect("NC_type (optional)", nc_all, default=prev_nc, key="selected_nc_types")
    else:
        st.session_state["selected_nc_types"] = None

    areas_all = sorted(long["Science Area"].dropna().unique().tolist())
    default_areas = [a for a in areas_all if not (hide_ps and str(a).strip().lower()=="professional services")]
    prev_areas = [a for a in st.session_state.get("selected_areas", default_areas) if a in areas_all] or default_areas
    st.multiselect("Science Areas", areas_all, default=prev_areas, key="selected_areas")

    projects_all = sorted(long["Project"].dropna().unique().tolist())
    prev_projects = [p for p in st.session_state.get("selected_projects", projects_all) if p in projects_all] or projects_all
    st.multiselect("Projects", projects_all, default=prev_projects, key="selected_projects")

    people_all = sorted(long["Person"].dropna().unique().tolist())
    default_people = people_all if people_all else []
    prev_people = [p for p in st.session_state.get("selected_people", default_people) if p in people_all] or default_people
    st.multiselect("Staff (optional)", people_all, default=prev_people, key="selected_people")

    max_total_candidate = pd.to_numeric(proj_tot["Project Hours"], errors="coerce").max() if not proj_tot.empty else 0
    max_total = float(max_total_candidate) if pd.notna(max_total_candidate) and np.isfinite(max_total_candidate) else 0.0
    if max_total <= 0:
        st.info("Minimum-hours filter disabled (no nonzero totals detected).")
        st.session_state["min_total"] = 0.0
    else:
        default_val = st.session_state.get("min_total", 0.0)
        try: default_val = float(default_val)
        except Exception: default_val = 0.0
        default_val = max(0.0, min(default_val, max_total))
        st.slider("Minimum total project hours", 0.0, max_total, default_val, step=1.0, key="min_total")

# ------------------------------- Filtering ---------------------------------
mask = long["Science Area"].isin(st.session_state["selected_areas"]) & long["Project"].isin(st.session_state["selected_projects"])
if st.session_state.get("selected_nc_types"):
    mask &= long["NC_type"].astype(str).isin(st.session_state["selected_nc_types"])
if st.session_state.get("selected_people"):
    mask &= long["Person"].fillna("__none__").isin(st.session_state["selected_people"] + ["__never__"])

filtered = long[mask].copy()

if st.session_state.get("min_total", 0.0) > 0 and "Project" in filtered.columns:
    proj_hours_now = filtered.groupby("Project")["Hours"].sum().reset_index()
    keep_projects = proj_hours_now[proj_hours_now["Hours"] >= st.session_state["min_total"]]["Project"].tolist()
    filtered = filtered[filtered["Project"].isin(keep_projects)]

if filtered.empty:
    st.warning("No data after filtering. Try 'Reset filters to defaults'.")
    st.stop()

proj_sum_filtered = filtered.groupby("Project", as_index=False)["Hours"].sum().rename(columns={"Hours":"ProjHoursFiltered"})
filtered = filtered.merge(proj_sum_filtered, on="Project", how="left")

area_sum_filtered = filtered.groupby("Science Area", as_index=False)["Hours"].sum().rename(columns={"Hours":"AreaHoursFiltered"})
filtered = filtered.merge(area_sum_filtered, on="Science Area", how="left")

person_sum_filtered = filtered[filtered["Person"].notna()].groupby("Person", as_index=False)["Hours"].sum().rename(columns={"Hours":"PersonHoursFiltered"})
if not person_sum_filtered.empty:
    filtered = filtered.merge(person_sum_filtered, on="Person", how="left")

# KPIs
k1, k2, k3, k4, k5 = st.columns(5)
k1.metric("Total Hours (filtered)", f"{filtered['Hours'].sum():,.0f}")
k2.metric("Projects (filtered)", f"{filtered['Project'].nunique():,}")
k3.metric("Science Areas (filtered)", f"{filtered['Science Area'].nunique():,}")
k4.metric("Staff in view", f"{filtered['Person'].dropna().nunique():,}")
k5.metric("NC_type in view", f"{filtered['NC_type'].dropna().nunique():,}")

st.divider()

# ------------------------------- Tabs --------------------------------------
tab1, tab2, tab3, tab4, tab5 = st.tabs([
    "Project split by science area",
    "Distribution within a science area",
    "Staff workload (by project)",
    "Project → staff distribution",
    "Export"
])

with tab1:
    st.subheader("Project split by science area")
    split_choice = st.radio("Choose view", ["Projects stacked by Science Area", "Science Areas stacked by Project"],
                            horizontal=True, key="split_view_choice")

    if split_choice == "Projects stacked by Science Area":
        pa = filtered.groupby(["Project","Science Area"], as_index=False)["Hours"].sum()
        pa = pa.merge(proj_sum_filtered, on="Project", how="left")
        proj_order = proj_sum_filtered.sort_values("ProjHoursFiltered", ascending=False)["Project"].tolist()
        pa["Project"] = pd.Categorical(pa["Project"], categories=proj_order, ordered=True)
        if st.session_state["global_view_mode"] == "Percent":
            pa["Value"] = np.where(pa["ProjHoursFiltered"]>0, pa["Hours"]/pa["ProjHoursFiltered"]*100.0, np.nan)
            y_title = "% of project labour (filtered)"; yaxis = dict(ticksuffix="%")
        else:
            pa["Value"] = pa["Hours"]; y_title = "Hours (filtered)"; yaxis = dict()
        split_fig = px.bar(pa.sort_values(["Project","Science Area"]), x="Project", y="Value", color="Science Area")
        split_fig.update_layout(barmode="stack", yaxis_title=y_title, xaxis_title="Project", yaxis=yaxis, height=520, margin=dict(t=40, r=10, b=0, l=10))
    else:
        sa = filtered.groupby(["Science Area","Project"], as_index=False)["Hours"].sum()
        sa = sa.merge(area_sum_filtered, on="Science Area", how="left")
        area_order = area_sum_filtered.sort_values("AreaHoursFiltered", ascending=False)["Science Area"].tolist()
        sa["Science Area"] = pd.Categorical(sa["Science Area"], categories=area_order, ordered=True)
        if st.session_state["global_view_mode"] == "Percent":
            sa["Value"] = np.where(sa["AreaHoursFiltered"]>0, sa["Hours"]/sa["AreaHoursFiltered"]*100.0, np.nan)
            y_title = "% of science area labour (filtered)"; yaxis = dict(ticksuffix="%")
        else:
            sa["Value"] = sa["Hours"]; y_title = "Hours (filtered)"; yaxis = dict()
        split_fig = px.bar(sa.sort_values(["Science Area","Project"]), x="Science Area", y="Value", color="Project")
        split_fig.update_layout(barmode="stack", yaxis_title=y_title, xaxis_title="Science Area", yaxis=yaxis, height=520, margin=dict(t=40, r=10, b=0, l=10), legend_title_text="Project")
    st.plotly_chart(split_fig, use_container_width=True)

with tab2:
    st.subheader("Distribution of labour within a selected science area")
    areas_sorted = sorted(filtered["Science Area"].unique().tolist())
    area_choice = st.selectbox("Choose a science area", options=areas_sorted, key="selected_area_single")
    area_df = filtered[filtered["Science Area"] == area_choice].copy()
    if area_df.empty:
        st.info("No rows for the selected area.")
    else:
        area_total = float(area_df["Hours"].sum())
        area_df = area_df.groupby("Project", as_index=False)["Hours"].sum().sort_values("Hours", ascending=False)
        if st.session_state["global_view_mode"] == "Percent":
            area_df["Value"] = np.where(area_total>0, area_df["Hours"]/area_total*100.0, np.nan)
            x_title = "% of science area labour"; xaxis = dict(ticksuffix="%"); txt = area_df["Value"].map(lambda v: f"{v:.1f}%")
        else:
            area_df["Value"] = area_df["Hours"]; x_title = "Hours in selected science area (filtered)"; xaxis = dict(); txt = area_df["Value"].map(lambda v: f"{v:,.0f}")
        area_fig = px.bar(area_df, x="Value", y="Project", orientation="h", text=txt)
        area_fig.update_layout(xaxis_title=x_title, yaxis_title="Project", xaxis=xaxis, height=600, margin=dict(t=40, r=10, b=10, l=10))
        st.plotly_chart(area_fig, use_container_width=True)

with tab3:
    st.subheader("Staff workload — distribution of a staff member's hours across projects")
    staff_available = filtered["Person"].notna().any()
    if not staff_available:
        st.info("No staff rows detected.")
        staff_fig = None
    else:
        staff_list = sorted(filtered["Person"].dropna().unique().tolist())
        staff_choice = st.selectbox("Choose staff member", options=staff_list, key="selected_staff_single")
        s_proj = filtered[(filtered["Person"]==staff_choice)].groupby("Project", as_index=False)["Hours"].sum().sort_values("Hours", ascending=False)
        s_total = float(s_proj["Hours"].sum())
        if st.session_state["global_view_mode"] == "Percent":
            s_proj["Value"] = np.where(s_total>0, s_proj["Hours"]/s_total*100.0, np.nan)
            x_title = "% of person's hours"; xaxis = dict(ticksuffix="%"); txt = s_proj["Value"].map(lambda v: f"{v:.1f}%")
        else:
            s_proj["Value"] = s_proj["Hours"]; x_title = "Hours (person)"; xaxis = dict(); txt = s_proj["Value"].map(lambda v: f"{v:,.0f}")
        staff_fig = px.bar(s_proj, x="Value", y="Project", orientation="h", text=txt)
        staff_fig.update_layout(xaxis_title=x_title, yaxis_title="Project", xaxis=xaxis, height=520, margin=dict(t=40, r=10, b=10, l=10))
        st.plotly_chart(staff_fig, use_container_width=True)

with tab4:
    st.subheader("Project → staff distribution (single project)")
    proj_sorted = sorted(filtered["Project"].unique().tolist())
    proj_choice = st.selectbox("Choose a project", options=proj_sorted, key="selected_project_single")
    proj_df = filtered[filtered["Project"] == proj_choice].copy()
    if proj_df.empty:
        st.info("No rows for the selected project.")
        proj_staff_fig = None
    else:
        proj_total = float(proj_df["Hours"].sum())
        ps = proj_df.groupby("Person", as_index=False)["Hours"].sum().sort_values("Hours", ascending=False)
        ps["Person"] = ps["Person"].fillna("(Unassigned)")
        if st.session_state["global_view_mode"] == "Percent":
            ps["Value"] = np.where(proj_total>0, ps["Hours"]/proj_total*100.0, np.nan)
            x_title = "% of project's hours"; xaxis = dict(ticksuffix="%"); txt = ps["Value"].map(lambda v: f"{v:.1f}%")
        else:
            ps["Value"] = ps["Hours"]; x_title = "Hours on selected project"; xaxis = dict(); txt = ps["Value"].map(lambda v: f"{v:,.0f}")
        proj_staff_fig = px.bar(ps, x="Value", y="Person", orientation="h", text=txt)
        proj_staff_fig.update_layout(xaxis_title=x_title, yaxis_title="Staff", xaxis=xaxis, height=520, margin=dict(t=40, r=10, b=10, l=10))
        st.plotly_chart(proj_staff_fig, use_container_width=True)

with tab5:
    st.subheader("Export current views")
    if not HAS_KALEIDO:
        st.info("PNG export requires the **kaleido** package. It will be installed on Streamlit Cloud from requirements.txt.")
    if not HAS_PPTX:
        st.info("PowerPoint export requires **python-pptx**. It will be installed on Streamlit Cloud from requirements.txt.")

    colL, colR = st.columns(2)

    def fig_to_png_bytes(fig):
        if not HAS_KALEIDO or fig is None:
            return None
        try:
            return pio.to_image(fig, format="png", scale=2)
        except Exception as e:
            st.warning(f"Could not render PNG: {e}")
            return None

    split_png = fig_to_png_bytes(split_fig) if 'split_fig' in locals() else None
    area_png  = fig_to_png_bytes(area_fig) if 'area_fig' in locals() else None
    staff_png = fig_to_png_bytes(staff_fig) if 'staff_fig' in locals() else None
    proj_staff_png = fig_to_png_bytes(proj_staff_fig) if 'proj_staff_fig' in locals() else None

    with colL:
        if split_png: st.download_button("Download PNG — Split view", data=split_png, file_name="split_view.png", mime="image/png")
        if area_png:  st.download_button("Download PNG — Area distribution", data=area_png, file_name="area_distribution.png", mime="image/png")
    with colR:
        if staff_png: st.download_button("Download PNG — Staff workload", data=staff_png, file_name="staff_workload.png", mime="image/png")
        if proj_staff_png: st.download_button("Download PNG — Project → staff", data=proj_staff_png, file_name="project_staff.png", mime="image/png")

    if HAS_PPTX and any([split_png, area_png, staff_png, proj_staff_png]):
        prs = Presentation()
        def add_slide(title, img_bytes):
            slide = prs.slides.add_slide(prs.slide_layouts[5])  # blank
            left = Inches(0.5); top = Inches(0.5); width = Inches(9.0)
            tx = slide.shapes.add_textbox(left, Inches(0.1), width, Inches(0.3))
            tx.text_frame.text = title
            slide.shapes.add_picture(io.BytesIO(img_bytes), left, top+Inches(0.3), width=width)
        if split_png: add_slide("Split view", split_png)
        if area_png: add_slide("Distribution within selected Science Area", area_png)
        if staff_png: add_slide("Staff workload (by project)", staff_png)
        if proj_staff_png: add_slide("Project → staff distribution", proj_staff_png)
        ppt_bytes = io.BytesIO()
        prs.save(ppt_bytes)
        st.download_button("Download PowerPoint with charts", data=ppt_bytes.getvalue(), file_name="ukceh_nc_labour_charts.pptx", mime="application/vnd.openxmlformats-officedocument.presentationml.presentation")
