
import re
import io
import json
import pandas as pd
import numpy as np
import plotly.express as px
import streamlit as st

# --- Optional imports for exports ---
try:
    from pptx import Presentation  # python-pptx
    from pptx.util import Inches
    HAS_PPTX = True
except Exception:
    HAS_PPTX = False

# Kaleido is used behind the scenes by Plotly for static image export.
# If it's not present, PNG export will be disabled but the app still works.
try:
    import kaleido  # noqa: F401
    HAS_KALEIDO = True
except Exception:
    HAS_KALEIDO = False

st.set_page_config(page_title="Labour Portfolio Explorer (Projects + Staff)", layout="wide")
st.title("Labour Portfolio Explorer")
st.caption("GitHub/Streamlit-ready. Upload your data; exports are optional and enabled only if dependencies are installed.")

# ---------------- Utilities for saving/loading defaults ----------------
def apply_loaded_defaults(defaults: dict):
    ss = st.session_state
    for k, v in defaults.items():
        ss[k] = v
    st.success("Defaults loaded. Rebuilding view…")
    st.rerun()

def current_defaults_dict():
    keys = ["selected_areas", "selected_projects", "selected_people", "hide_ps", "min_total", "view_mode"]
    return {k: st.session_state.get(k) for k in keys}

# ------------ Data input (upload-first for GitHub safety) -------------
with st.expander("📦 Template & example data", expanded=False):
    st.write("Required: first column = **Project** (or staff name under a project), remaining columns = numeric hours by science area.")
    demo = pd.DataFrame({
        "Project": ["07949 LTSM-DEF-AgZero+", "Abigail Lowe", "07960 LTSM-DEF-CHAMFER", "Aidan Keith"],
        "Environmental Pressures and Responses (SA)": [1676.3, 0, 822.0, 0],
        "Water and Climate Science (SA)": [926.4, 0, 0, 0],
        "Biodiversity and Land Use (SA)": [8926.69, 37, 95, 0],
        "National Capability and Digital Research (SA)": [63.5, 0, 0, 0],
        "Professional Services": [162.8, 0, 0, 0],
        "Land Atmosphere Interactions (SA)": [2508.8, 0, 0, 300.0]
    })
    st.download_button("Download CSV template (with example rows)",
                       data=demo.to_csv(index=False).encode("utf-8"),
                       file_name="labour_template.csv",
                       mime="text/csv")
    st.write("Optional metadata CSV columns: `Project`, `Funder Type` (or `FunderType`).")

uploaded = st.file_uploader("Upload Excel (.xlsx) or CSV with labour data", type=["xlsx","csv"])
meta_file = st.file_uploader("Upload optional Project → Funder Type CSV", type=["csv"], help="Columns: Project, Funder Type (or FunderType)")

if not uploaded:
    st.info("Upload a labour file to begin. No data is stored by this app.")
    st.stop()

# ---- Load labour
try:
    if uploaded.name.lower().endswith(".csv"):
        df_raw = pd.read_csv(uploaded)
    else:
        df_raw = pd.read_excel(uploaded, sheet_name=0)
except Exception as e:
    st.error(f"Could not read the labour file: {e}")
    st.stop()

if df_raw.shape[1] < 2:
    st.error("Expected at least 2 columns (Project + one science area).")
    st.stop()

project_col_src = df_raw.columns[0]
value_cols = [c for c in df_raw.columns[1:] if c.lower() not in ("grand total","total")]

# Ensure numeric in hour columns
df = df_raw.copy()
for c in value_cols + [c for c in df_raw.columns if c.lower() in ("grand total","total")]:
    if c in df.columns:
        df[c] = pd.to_numeric(df[c], errors="coerce")
df[value_cols] = df[value_cols].fillna(0.0)

# ---- Optional metadata: project → funder type
meta = None
if meta_file is not None:
    try:
        meta = pd.read_csv(meta_file)
        meta_cols = {c.lower().strip(): c for c in meta.columns}
        proj_col_meta = next((meta_cols[k] for k in meta_cols if k == "project"), None)
        funder_col_meta = next((meta_cols[k] for k in meta_cols if k in ("funder type","fundertype","funder")), None)
        if proj_col_meta is None or funder_col_meta is None:
            st.warning("Metadata CSV must include 'Project' and 'Funder Type' (or 'FunderType'). Ignoring metadata.")
            meta = None
        else:
            meta = meta.rename(columns={proj_col_meta: "Project", funder_col_meta: "Funder Type"})
    except Exception as e:
        st.warning(f"Could not read metadata file: {e}")
        meta = None

# ------------ Detect structure and expand to long with optional Person column
def is_project_id(x: str) -> bool:
    if not isinstance(x, str):
        return False
    return bool(re.match(r"^\s*\d", x))  # starts with a digit

records = []
current_project = None

for _, row in df.iterrows():
    name = row[project_col_src]
    if pd.isna(name):
        continue
    if is_project_id(str(name)):
        current_project = str(name).strip()
        for area in value_cols:
            val = row.get(area, np.nan)
            if pd.notna(val) and float(val) != 0.0:
                records.append({"Project": current_project, "Person": None, "Science Area": area, "Hours": float(val)})
    else:
        person = str(name).strip()
        for area in value_cols:
            val = row.get(area, np.nan)
            if pd.notna(val) and float(val) != 0.0:
                records.append({"Project": current_project, "Person": person, "Science Area": area, "Hours": float(val)})

long = pd.DataFrame.from_records(records)

if long.empty:
    long = df.melt(id_vars=[project_col_src], value_vars=value_cols, var_name="Science Area", value_name="Hours")
    long = long.rename(columns={project_col_src:"Project"})
    long["Person"] = None
    long = long[long["Hours"].fillna(0) > 0.0]

# Totals and percentages (overall, pre-filter – useful for tables)
proj_totals = long.groupby(["Project"], as_index=False)["Hours"].sum().rename(columns={"Hours":"Project Hours"})
area_totals = long.groupby(["Science Area"], as_index=False)["Hours"].sum().rename(columns={"Hours":"Area Hours"})
long = long.merge(proj_totals, on="Project", how="left").merge(area_totals, on="Science Area", how="left")
long["Pct of Project"] = np.where(long["Project Hours"]>0, long["Hours"]/long["Project Hours"], np.nan)
long["Pct of Area"] = np.where(long["Area Hours"]>0, long["Hours"]/long["Area Hours"], np.nan)

# Staff totals (within-person)
person_totals = long.dropna(subset=["Person"]).groupby(["Person"], as_index=False)["Hours"].sum().rename(columns={"Hours":"Person Hours"})
if not person_totals.empty:
    long = long.merge(person_totals, on="Person", how="left")
    long["Pct of Person"] = np.where(long["Person Hours"]>0, long["Hours"]/long["Person Hours"], np.nan)
else:
    long["Person Hours"] = np.nan
    long["Pct of Person"] = np.nan

# ------------ Sidebar filters & defaults
with st.sidebar:
    st.header("Filters")

    # Load defaults (JSON)
    st.markdown("**Load saved defaults**")
    defaults_file = st.file_uploader("Upload defaults JSON", type=["json"], key="defaults_uploader")
    if defaults_file is not None:
        try:
            defaults = json.load(defaults_file)
            apply_loaded_defaults(defaults)
        except Exception as e:
            st.error(f"Could not read defaults JSON: {e}")

    hide_ps = st.checkbox("Hide 'Professional Services'", value=st.session_state.get("hide_ps", True), key="hide_ps")

    areas_all = sorted(long["Science Area"].dropna().unique().tolist())
    default_areas = [a for a in areas_all if not (hide_ps and str(a).strip().lower()=="professional services")]
    selected_areas = st.multiselect("Science Areas", areas_all, default=st.session_state.get("selected_areas", default_areas), key="selected_areas")

    projects_all = sorted(long["Project"].dropna().unique().tolist())
    selected_projects = st.multiselect("Projects", projects_all, default=st.session_state.get("selected_projects", projects_all), key="selected_projects")

    people_all = sorted(long["Person"].dropna().unique().tolist())
    selected_people_default = people_all if people_all else []
    selected_people = st.multiselect("Staff (optional)", people_all, default=st.session_state.get("selected_people", selected_people_default), key="selected_people")

    # Funder filter if metadata provided
    if meta is not None:
        long = long.merge(meta, on="Project", how="left")
        funders_all = sorted([str(x) for x in long["Funder Type"].dropna().unique().tolist()]) if "Funder Type" in long.columns else []
        selected_funders = st.multiselect("Funder Type", funders_all, default=funders_all, key="selected_funders")
    else:
        selected_funders = None

    min_total = st.slider("Minimum total project hours", 0.0, float(proj_totals["Project Hours"].max()) if not proj_totals.empty else 0.0, float(st.session_state.get("min_total", 0.0)), step=1.0, key="min_total")

    st.markdown("---")
    st.markdown("**Save current filters**")
    defaults_json = json.dumps(current_defaults_dict(), indent=2)
    st.download_button("Download defaults JSON", data=defaults_json.encode("utf-8"), file_name="labour_dashboard_defaults.json", mime="application/json")

# Apply filters
mask = long["Science Area"].isin(st.session_state["selected_areas"]) & long["Project"].isin(st.session_state["selected_projects"])
if people_all and st.session_state["selected_people"]:
    mask &= long["Person"].fillna("__none__").isin(st.session_state["selected_people"] + ["__never__"])
if selected_funders is not None and "Funder Type" in long.columns:
    mask &= long["Funder Type"].astype(str).isin(selected_funders)

filtered = long[mask].copy()

# Enforce project-hours threshold after filters
proj_hours_now = filtered.groupby("Project")["Hours"].sum().reset_index()
keep_projects = proj_hours_now[proj_hours_now["Hours"] >= st.session_state["min_total"]]["Project"].tolist()
filtered = filtered[filtered["Project"].isin(keep_projects)]

if filtered.empty:
    st.warning("No data after filtering. Relax your filters.")
    st.stop()

# KPIs
k1, k2, k3, k4 = st.columns(4)
k1.metric("Total Hours (filtered)", f"{filtered['Hours'].sum():,.0f}")
k2.metric("Projects (filtered)", f"{filtered['Project'].nunique():,}")
k3.metric("Science Areas (filtered)", f"{filtered['Science Area'].nunique():,}")
k4.metric("Staff in view", f"{filtered['Person'].dropna().nunique():,}")

st.divider()

# ------------ Tabs for views
tab1, tab2, tab3, tab4 = st.tabs([
    "% split by area for each project",
    "% distribution within a science area",
    "Staff workload views",
    "Export"
])

with tab1:
    st.subheader("% labour split by science area for each project")
    view_mode = st.radio("View mode", options=["Percent (normalised to 100%)", "Absolute hours"], horizontal=True, key="view_mode")

    # Aggregate on filtered data
    pa = filtered.groupby(["Project","Science Area"], as_index=False)["Hours"].sum()
    proj_sum = pa.groupby("Project", as_index=False)["Hours"].sum().rename(columns={"Hours":"ProjHoursFiltered"})
    pa = pa.merge(proj_sum, on="Project", how="left")
    proj_order = proj_sum.sort_values("ProjHoursFiltered", ascending=False)["Project"].tolist()
    pa["Project"] = pd.Categorical(pa["Project"], categories=proj_order, ordered=True)

    if view_mode.startswith("Percent"):
        pa["Value"] = np.where(pa["ProjHoursFiltered"]>0, pa["Hours"]/pa["ProjHoursFiltered"]*100.0, np.nan)
        y_title = "% of project labour (filtered)"
        yaxis = dict(ticksuffix="%")
    else:
        pa["Value"] = pa["Hours"]
        y_title = "Hours (filtered)"
        yaxis = dict()

    fig1 = px.bar(pa.sort_values(["Project","Science Area"]), x="Project", y="Value", color="Science Area")
    fig1.update_layout(barmode="stack", yaxis_title=y_title, xaxis_title="Project", yaxis=yaxis, height=520, margin=dict(t=40, r=10, b=0, l=10))
    st.plotly_chart(fig1, use_container_width=True)

with tab2:
    st.subheader("% distribution of labour within a selected science area")
    areas_sorted = sorted(filtered["Science Area"].unique().tolist())
    area_choice = st.selectbox("Choose a science area", options=areas_sorted, key="area_choice2")
    area_df = filtered[filtered["Science Area"] == area_choice].copy()
    if area_df.empty:
        st.info("No rows for the selected area.")
    else:
        area_total = float(area_df["Hours"].sum())
        area_df = area_df.groupby("Project", as_index=False)["Hours"].sum().sort_values("Hours", ascending=False)
        area_df["Pct of Area"] = np.where(area_total>0, area_df["Hours"]/area_total*100.0, np.nan)
        fig2 = px.bar(area_df, x="Pct of Area", y="Project", orientation="h",
                      text=area_df["Pct of Area"].map(lambda v: f"{v:.1f}%"))
        fig2.update_layout(xaxis_title="% of science area labour", yaxis_title="Project",
                           xaxis=dict(ticksuffix="%"), height=600, margin=dict(t=40, r=10, b=10, l=10))
        st.plotly_chart(fig2, use_container_width=True)

with tab3:
    st.subheader("Staff workload views")
    staff_available = filtered["Person"].notna().any()
    if not staff_available:
        st.info("No staff rows detected. Upload a file with staff allocations to enable these views.")
        staff_fig_pie = None
        staff_fig_bar = None
    else:
        left, right = st.columns(2)
        with left:
            st.markdown("**% split of a staff member across science areas**")
            staff_list = sorted(filtered["Person"].dropna().unique().tolist())
            staff_choice = st.selectbox("Choose staff member", options=staff_list)
            s_df = filtered[(filtered["Person"]==staff_choice)].groupby("Science Area", as_index=False)["Hours"].sum()
            s_total = float(s_df["Hours"].sum())
            s_df["Pct of Person"] = np.where(s_total>0, s_df["Hours"]/s_total*100.0, np.nan)
            staff_fig_pie = px.pie(s_df, values="Pct of Person", names="Science Area", hole=0.35)
            staff_fig_pie.update_layout(legend_title="Science Area")
            st.plotly_chart(staff_fig_pie, use_container_width=True)

        with right:
            st.markdown("**% distribution of a staff member's hours across projects**")
            s_proj = filtered[(filtered["Person"]==staff_choice)].groupby("Project", as_index=False)["Hours"].sum().sort_values("Hours", ascending=False)
            s_total2 = float(s_proj["Hours"].sum())
            s_proj["Pct of Person"] = np.where(s_total2>0, s_proj["Hours"]/s_total2*100.0, np.nan)
            staff_fig_bar = px.bar(s_proj, x="Pct of Person", y="Project", orientation="h",
                                   text=s_proj["Pct of Person"].map(lambda v: f"{v:.1f}%"))
            staff_fig_bar.update_layout(xaxis_title="% of person's hours", yaxis_title="Project", xaxis=dict(ticksuffix="%"), height=500)
            st.plotly_chart(staff_fig_bar, use_container_width=True)

        st.markdown("**Staff table (filtered)**")
        staff_tbl = filtered[filtered["Person"].notna()].copy()
        staff_tbl = staff_tbl[["Person","Project","Science Area","Hours"]]
        st.dataframe(staff_tbl.sort_values(["Person","Project","Science Area"]).reset_index(drop=True), use_container_width=True)

with tab4:
    st.subheader("Export current views")
    # PNG exports (optional: requires kaleido)
    if HAS_KALEIDO:
        try:
            fig1_png = fig1.to_image(format="png", scale=2)
        except Exception:
            fig1_png = None
        try:
            fig2_png = fig2.to_image(format="png", scale=2)
        except Exception:
            fig2_png = None
        staff_pie_png = None
        staff_bar_png = None
        try:
            if 'staff_fig_pie' in locals() and staff_fig_pie is not None:
                staff_pie_png = staff_fig_pie.to_image(format="png", scale=2)
            if 'staff_fig_bar' in locals() and staff_fig_bar is not None:
                staff_bar_png = staff_fig_bar.to_image(format="png", scale=2)
        except Exception:
            pass

        colA, colB = st.columns(2)
        with colA:
            if fig1_png:
                st.download_button("Download PNG — Project split", data=fig1_png, file_name="project_split.png", mime="image/png")
            if fig2_png:
                st.download_button("Download PNG — Area distribution", data=fig2_png, file_name="area_distribution.png", mime="image/png")
        with colB:
            if staff_pie_png:
                st.download_button("Download PNG — Staff split (areas)", data=staff_pie_png, file_name="staff_area_split.png", mime="image/png")
            if staff_bar_png:
                st.download_button("Download PNG — Staff distribution (projects)", data=staff_bar_png, file_name="staff_project_distribution.png", mime="image/png")
    else:
        st.info("PNG export disabled (optional). To enable, add `kaleido` to requirements.")

    # PPTX export (optional: requires python-pptx and ideally kaleido for images)
    if HAS_PPTX and HAS_KALEIDO:
        prs = Presentation()
        title_slide_layout = prs.slide_layouts[5]  # blank

        def add_slide_with_image(prs, title_text, img_bytes):
            slide = prs.slides.add_slide(title_slide_layout)
            left = Inches(0.5); top = Inches(0.5); width = Inches(9.0)
            txBox = slide.shapes.add_textbox(left, Inches(0.1), width, Inches(0.3))
            tf = txBox.text_frame
            tf.text = title_text
            slide.shapes.add_picture(io.BytesIO(img_bytes), left, top+Inches(0.3), width=width)

        # Regenerate PNGs if needed
        try:
            fig1_png = fig1.to_image(format="png", scale=2)
        except Exception:
            fig1_png = None
        try:
            fig2_png = fig2.to_image(format="png", scale=2)
        except Exception:
            fig2_png = None
        staff_pie_png = None
        staff_bar_png = None
        try:
            if 'staff_fig_pie' in locals() and staff_fig_pie is not None:
                staff_pie_png = staff_fig_pie.to_image(format="png", scale=2)
            if 'staff_fig_bar' in locals() and staff_fig_bar is not None:
                staff_bar_png = staff_fig_bar.to_image(format="png", scale=2)
        except Exception:
            pass

        if any([fig1_png, fig2_png, staff_pie_png, staff_bar_png]):
            if fig1_png:
                add_slide_with_image(prs, "Project %/Hours split by Science Area", fig1_png)
            if fig2_png:
                add_slide_with_image(prs, "Distribution within selected Science Area", fig2_png)
            if staff_pie_png:
                add_slide_with_image(prs, "Staff % split across Science Areas", staff_pie_png)
            if staff_bar_png:
                add_slide_with_image(prs, "Staff % distribution across Projects", staff_bar_png)

            ppt_bytes = io.BytesIO()
            prs.save(ppt_bytes)
            st.download_button("Download PowerPoint with charts", data=ppt_bytes.getvalue(), file_name="labour_dashboard_charts.pptx", mime="application/vnd.openxmlformats-officedocument.presentationml.presentation")
        else:
            st.info("Generate charts to enable PowerPoint download.")
    else:
        st.info("PowerPoint export disabled (optional). To enable, add **python-pptx** and **kaleido** to requirements.")
