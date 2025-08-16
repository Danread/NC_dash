
import re
import io
import pandas as pd
import numpy as np
import plotly.express as px
import plotly.io as pio  # <-- use plotly.io, not px.io
import streamlit as st

# --- Optional imports for exports ---
try:
    import kaleido  # noqa: F401  # needed by plotly.io/fig.to_image
    HAS_KALEIDO = True
except Exception:
    HAS_KALEIDO = False

try:
    from pptx import Presentation  # python-pptx
    from pptx.util import Inches
    HAS_PPTX = True
except Exception:
    HAS_PPTX = False

st.set_page_config(page_title="UKCEH NC Labour Explorer", layout="wide")
st.title("UKCEH NC Labour Explorer")
st.caption("Upload your data; view everything as **percentages** or **absolute hours** with a single toggle.")

with st.expander("📦 Accepted layouts", expanded=False):
    st.markdown("- **Layout A**: Columns `Project`, `Person` (optional), optional `NC_type`, plus one column per science area (numeric).")
    st.markdown("- **Layout B**: First column alternates between project headers (start with digits) and staff rows underneath. (If present, an `NC_type` column will be carried across project and staff rows.)")

uploaded = st.file_uploader("Upload Excel (.xlsx) or CSV with labour data", type=["xlsx","csv"])

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
    st.error("Expected at least 2 columns.")
    st.stop()

# ---- Determine schema
cols_lower = {c.lower().strip(): c for c in df_raw.columns}
has_project_col = "project" in cols_lower
has_person_col = "person" in cols_lower
has_nc_type_col = "nc_type" in cols_lower or "nc type" in cols_lower
nc_col_name = cols_lower.get("nc_type", cols_lower.get("nc type", None))

# Identify value columns (science areas) while dropping any total/grand total columns and known id cols
exclude = set(filter(None, [cols_lower.get("project"), cols_lower.get("person"), nc_col_name]))
value_cols = [c for c in df_raw.columns if c not in exclude and c.lower().strip() not in ("grand total","total","grand_total")]
if not value_cols:
    st.error("Could not find any science area columns (numeric).")
    st.stop()

# Coerce numeric
df = df_raw.copy()
for c in value_cols + [c for c in df_raw.columns if c.lower() in ("grand total","total","grand_total")]:
    if c in df.columns:
        df[c] = pd.to_numeric(df[c], errors="coerce")
df[value_cols] = df[value_cols].fillna(0.0)

# ---- Build long table
def is_project_id(x: str) -> bool:
    if not isinstance(x, str):
        return False
    return bool(re.match(r"^\s*\d", x))

def is_total_like(x: str) -> bool:
    if not isinstance(x, str):
        return False
    return bool(re.match(r"^\s*(grand\s+)?totals?$", x.strip().lower()))

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
    # drop total-like project rows
    long = long[~long["Project"].astype(str).apply(is_total_like)]
else:
    # Layout B
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

# Clean
if "NC_type" not in long.columns:
    long["NC_type"] = None

long["Hours"] = pd.to_numeric(long["Hours"], errors="coerce")
long = long.replace({np.inf: np.nan, -np.inf: np.nan})
long = long[long["Hours"].fillna(0) > 0.0]

# Validate essentials
if "Project" not in long.columns or long.empty:
    st.error("Could not construct a Project × Science Area table from the upload. Check column names.")
    st.stop()
if "Person" not in long.columns:
    long["Person"] = None

# Remove any lingering total-like Science Areas
long = long[~long["Science Area"].astype(str).str.strip().str.lower().isin(["grand total","total","grand_total"])]

# Totals
proj_totals = long.groupby(["Project"], as_index=False)["Hours"].sum().rename(columns={"Hours":"Project Hours"})
area_totals = long.groupby(["Science Area"], as_index=False)["Hours"].sum().rename(columns={"Hours":"Area Hours"})
long = long.merge(proj_totals, on="Project", how="left").merge(area_totals, on="Science Area", how="left")

# Staff totals (for % of person mode)
person_totals = long.dropna(subset=["Person"]).groupby(["Person"], as_index=False)["Hours"].sum().rename(columns={"Hours":"Person Hours"})
if not person_totals.empty:
    long = long.merge(person_totals, on="Person", how="left")
else:
    long["Person Hours"] = np.nan

# ------------- Sidebar & filters -------------
with st.sidebar:
    st.header("Filters")
    if st.button("🔄 Reset filters to defaults"):
        for k in ["selected_areas", "selected_projects", "selected_people", "selected_nc_types",
                  "hide_ps", "min_total", "global_view_mode", "split_view_choice"]:
            if k in st.session_state:
                del st.session_state[k]
        st.rerun()

    hide_ps = st.checkbox("Hide 'Professional Services'", value=st.session_state.get("hide_ps", True), key="hide_ps")

    # Global display toggle (applies to all tabs)
    st.markdown("**Display values as**")
    st.radio(
        "Display mode",
        options=["Percent", "Absolute hours"],
        horizontal=True,
        key="global_view_mode",
        label_visibility="collapsed"
    )

    # NC_type filter (optional)
    if "NC_type" in long.columns and long["NC_type"].notna().any():
        nc_all = sorted([str(x) for x in long["NC_type"].dropna().unique().tolist()])
        prev_nc = [x for x in st.session_state.get("selected_nc_types", nc_all) if x in nc_all] or nc_all
        st.multiselect("NC_type (optional)", nc_all, default=prev_nc, key="selected_nc_types")
    else:
        st.session_state["selected_nc_types"] = None

    # Core filters
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

    # Robust slider
    max_total_candidate = pd.to_numeric(proj_totals["Project Hours"], errors="coerce").max() if not proj_totals.empty else 0
    max_total = float(max_total_candidate) if pd.notna(max_total_candidate) and np.isfinite(max_total_candidate) else 0.0
    if max_total <= 0:
        st.info("All projects have 0 total hours (or not detected). Minimum-hours filter is disabled.")
        st.session_state["min_total"] = 0.0
    else:
        default_val = st.session_state.get("min_total", 0.0)
        try:
            default_val = float(default_val)
        except Exception:
            default_val = 0.0
        default_val = max(0.0, min(default_val, max_total))
        st.slider("Minimum total project hours", 0.0, max_total, default_val, step=1.0, key="min_total")

# Apply filters
mask = long["Science Area"].isin(st.session_state["selected_areas"]) & long["Project"].isin(st.session_state["selected_projects"])
if "selected_nc_types" in st.session_state and st.session_state["selected_nc_types"]:
    mask &= long["NC_type"].astype(str).isin(st.session_state["selected_nc_types"])

if people_all and st.session_state["selected_people"]:
    mask &= long["Person"].fillna("__none__").isin(st.session_state["selected_people"] + ["__never__"])
filtered = long[mask].copy()

# Enforce min_total
if st.session_state.get("min_total", 0.0) > 0 and "Project" in filtered.columns:
    proj_hours_now = filtered.groupby("Project")["Hours"].sum().reset_index()
    keep_projects = proj_hours_now[proj_hours_now["Hours"] >= st.session_state["min_total"]]["Project"].tolist()
    filtered = filtered[filtered["Project"].isin(keep_projects)]

if filtered.empty:
    st.warning("No data after filtering. Try clicking 'Reset filters to defaults' in the sidebar and ensure the science area columns contain numeric hours.")
    st.stop()

# Precompute totals for percent calculations
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

# ------------ Tabs
tab1, tab2, tab3, tab4 = st.tabs([
    "Project split by science area",
    "Distribution within a science area",
    "Staff workload (by project)",
    "Export"
])

with tab1:
    st.subheader("Project split by science area")

    split_view_choice = st.radio(
        "Choose view",
        options=["Projects stacked by Science Area", "Science Areas stacked by Project"],
        horizontal=False,
        key="split_view_choice"
    )

    if split_view_choice == "Projects stacked by Science Area":
        pa = filtered.groupby(["Project","Science Area"], as_index=False)["Hours"].sum()
        pa = pa.merge(proj_sum_filtered, on="Project", how="left")
        proj_order = proj_sum_filtered.sort_values("ProjHoursFiltered", ascending=False)["Project"].tolist()
        pa["Project"] = pd.Categorical(pa["Project"], categories=proj_order, ordered=True)

        if st.session_state["global_view_mode"] == "Percent":
            pa["Value"] = np.where(pa["ProjHoursFiltered"]>0, pa["Hours"]/pa["ProjHoursFiltered"]*100.0, np.nan)
            y_title = "% of project labour (filtered)"
            yaxis = dict(ticksuffix="%")
        else:
            pa["Value"] = pa["Hours"]
            y_title = "Hours (filtered)"
            yaxis = dict()

        fig_split = px.bar(pa.sort_values(["Project","Science Area"]), x="Project", y="Value", color="Science Area")
        fig_split.update_layout(barmode="stack", yaxis_title=y_title, xaxis_title="Project", yaxis=yaxis, height=520, margin=dict(t=40, r=10, b=0, l=10))
        st.plotly_chart(fig_split, use_container_width=True)

    else:
        sa = filtered.groupby(["Science Area","Project"], as_index=False)["Hours"].sum()
        sa = sa.merge(area_sum_filtered, on="Science Area", how="left")
        area_order = area_sum_filtered.sort_values("AreaHoursFiltered", ascending=False)["Science Area"].tolist()
        sa["Science Area"] = pd.Categorical(sa["Science Area"], categories=area_order, ordered=True)

        if st.session_state["global_view_mode"] == "Percent":
            sa["Value"] = np.where(sa["AreaHoursFiltered"]>0, sa["Hours"]/sa["AreaHoursFiltered"]*100.0, np.nan)
            y_title_b = "% of science area labour (filtered)"
            yaxis_b = dict(ticksuffix="%")
        else:
            sa["Value"] = sa["Hours"]
            y_title_b = "Hours (filtered)"
            yaxis_b = dict()

        fig_split = px.bar(sa.sort_values(["Science Area","Project"]), x="Science Area", y="Value", color="Project")
        fig_split.update_layout(barmode="stack", yaxis_title=y_title_b, xaxis_title="Science Area", yaxis=yaxis_b, height=520, margin=dict(t=40, r=10, b=0, l=10), legend_title_text="Project")
        st.plotly_chart(fig_split, use_container_width=True)

with tab2:
    st.subheader("Distribution of labour within a selected science area")
    areas_sorted = sorted(filtered["Science Area"].unique().tolist())
    area_choice = st.selectbox("Choose a science area", options=areas_sorted, key="area_choice2")
    area_df = filtered[filtered["Science Area"] == area_choice].copy()
    if area_df.empty:
        st.info("No rows for the selected area.")
        fig_area = None
    else:
        area_total = float(area_df["Hours"].sum())
        area_df = area_df.groupby("Project", as_index=False)["Hours"].sum().sort_values("Hours", ascending=False)
        if st.session_state["global_view_mode"] == "Percent":
            area_df["Value"] = np.where(area_total>0, area_df["Hours"]/area_total*100.0, np.nan)
            x_title = "% of science area labour"
            xaxis = dict(ticksuffix="%")
        else:
            area_df["Value"] = area_df["Hours"]
            x_title = "Hours in selected science area (filtered)"
            xaxis = dict()
        fig_area = px.bar(area_df, x="Value", y="Project", orientation="h",
                          text=area_df["Value"].map(lambda v: f"{v:.1f}%" if st.session_state["global_view_mode"]=="Percent" else f"{v:,.0f}"))
        fig_area.update_layout(xaxis_title=x_title, yaxis_title="Project", xaxis=xaxis, height=600, margin=dict(t=40, r=10, b=10, l=10))
        st.plotly_chart(fig_area, use_container_width=True)

with tab3:
    st.subheader("Staff workload — distribution of a staff member's hours across projects")
    staff_available = filtered["Person"].notna().any()
    if not staff_available:
        st.info("No staff rows detected.")
        fig_staff = None
    else:
        staff_list = sorted(filtered["Person"].dropna().unique().tolist())
        staff_choice = st.selectbox("Choose staff member", options=staff_list, key="staff_choice")
        s_proj = filtered[(filtered["Person"]==staff_choice)].groupby("Project", as_index=False)["Hours"].sum().sort_values("Hours", ascending=False)
        s_total2 = float(s_proj["Hours"].sum())
        if st.session_state["global_view_mode"] == "Percent":
            s_proj["Value"] = np.where(s_total2>0, s_proj["Hours"]/s_total2*100.0, np.nan)
            x_title = "% of person's hours"
            xaxis = dict(ticksuffix="%")
            text_fmt = lambda v: f"{v:.1f}%"
        else:
            s_proj["Value"] = s_proj["Hours"]
            x_title = "Hours (person)"
            xaxis = dict()
            text_fmt = lambda v: f"{v:,.0f}"
        fig_staff = px.bar(s_proj, x="Value", y="Project", orientation="h",
                           text=s_proj["Value"].map(text_fmt))
        fig_staff.update_layout(xaxis_title=x_title, yaxis_title="Project",
                                xaxis=xaxis, height=520, margin=dict(t=40, r=10, b=10, l=10))
        st.plotly_chart(fig_staff, use_container_width=True)

with tab4:
    st.subheader("Export current views")
    if not HAS_KALEIDO:
        st.warning("PNG/PPT export requires the 'kaleido' package. Install it via: `pip install kaleido`")
    # Export functions using plotly.io
    def fig_to_png_bytes(fig):
        if fig is None:
            return None
        try:
            # Either fig.to_image(...) or pio.to_image(fig, ...). Use pio for clarity.
            return pio.to_image(fig, format="png", scale=2)  # requires kaleido
        except Exception as e:
            st.error(f"Could not render PNG: {e}")
            return None

    col1, col2 = st.columns(2)
    with col1:
        st.markdown("**Split view (selected)**")
        split_png = fig_to_png_bytes(globals().get("fig_split", None))
        if split_png:
            st.download_button("Download PNG — Split view", data=split_png, file_name="split_view.png", mime="image/png")

        st.markdown("**Area distribution**")
        area_png = fig_to_png_bytes(globals().get("fig_area", None))
        if area_png:
            st.download_button("Download PNG — Area distribution", data=area_png, file_name="area_distribution.png", mime="image/png")

    with col2:
        st.markdown("**Staff distribution**")
        staff_png = fig_to_png_bytes(globals().get("fig_staff", None))
        if staff_png:
            st.download_button("Download PNG — Staff by project", data=staff_png, file_name="staff_by_project.png", mime="image/png")

        if HAS_PPTX and HAS_KALEIDO:
            # Build a PPTX
            prs = Presentation()

            def add_slide_with_image(prs, title_text, img_bytes):
                slide = prs.slides.add_slide(prs.slide_layouts[5])  # blank
                left = Inches(0.5); top = Inches(0.5); width = Inches(9.0)
                txBox = slide.shapes.add_textbox(left, Inches(0.1), width, Inches(0.3))
                tf = txBox.text_frame
                tf.text = title_text
                slide.shapes.add_picture(io.BytesIO(img_bytes), left, top+Inches(0.3), width=width)

            imgs = []
            if split_png: imgs.append(("Split view", split_png))
            if area_png:  imgs.append(("Area distribution", area_png))
            if staff_png: imgs.append(("Staff by project", staff_png))

            if imgs:
                for title, img in imgs:
                    add_slide_with_image(prs, title, img)
                ppt_bytes = io.BytesIO()
                prs.save(ppt_bytes)
                st.download_button("Download PowerPoint with charts", data=ppt_bytes.getvalue(),
                                   file_name="ukceh_nc_labour_charts.pptx",
                                   mime="application/vnd.openxmlformats-officedocument.presentationml.presentation")
            else:
                st.info("Generate at least one chart to enable the PowerPoint download.")
        elif not HAS_PPTX:
            st.info("Install **python-pptx** to enable the PowerPoint export: `pip install python-pptx`")
