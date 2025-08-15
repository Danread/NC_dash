
import pandas as pd
import numpy as np
import plotly.express as px
import streamlit as st

st.set_page_config(page_title="Labour Portfolio Explorer", layout="wide")
st.title("Labour Portfolio Explorer")
st.caption("Upload a spreadsheet of labour hours by project (rows) and business units/science areas (columns).")

with st.expander("📦 Template & example data", expanded=False):
    st.write("Your file should have a first column called something like 'Project' and the remaining columns numeric (hours).")
    demo = pd.DataFrame({
        "Project": ["Aquila", "Borealis", "Cygnus", "Draco"],
        "Environmental Pressures and Responses (SA)": [1200, 300, 0, 800],
        "Water and Climate Science (SA)": [500, 100, 250, 0],
        "Biodiversity and Land Use (SA)": [0, 400, 350, 200],
        "National Capability and Digital Research (SA)": [60, 0, 10, 20],
        "Professional Services": [90, 40, 35, 50]
    })
    st.download_button("Download CSV template (with example rows)",
                       data=demo.to_csv(index=False).encode("utf-8"),
                       file_name="labour_template.csv",
                       mime="text/csv")

uploaded = st.file_uploader("Upload Excel (.xlsx) or CSV", type=["xlsx", "csv"])

if not uploaded:
    st.info("Upload a file to begin. No data is stored by this app.")
    st.stop()

# ---- Load
try:
    if uploaded.name.lower().endswith(".csv"):
        df_raw = pd.read_csv(uploaded)
    else:
        df_raw = pd.read_excel(uploaded, sheet_name=0)
except Exception as e:
    st.error(f"Could not read the file: {e}")
    st.stop()

if df_raw.shape[1] < 2:
    st.error("Expected at least 2 columns (Project + one science area).")
    st.stop()

project_col = df_raw.columns[0]
value_cols = df_raw.columns[1:]

# Ensure numeric
df = df_raw.copy()
for c in value_cols:
    df[c] = pd.to_numeric(df[c], errors="coerce")
df[value_cols] = df[value_cols].fillna(0.0)

# Long format
long = df.melt(id_vars=[project_col], value_vars=value_cols, var_name="Science Area", value_name="Hours")
long = long[long["Hours"] > 0].copy()

if long.empty:
    st.warning("No positive hours found after parsing. Check your columns are numeric.")
    st.stop()

# Totals and percentages
proj_totals = long.groupby(project_col, as_index=False)["Hours"].sum().rename(columns={"Hours": "Project Hours"})
area_totals = long.groupby("Science Area", as_index=False)["Hours"].sum().rename(columns={"Hours": "Area Hours"})
long = long.merge(proj_totals, on=project_col).merge(area_totals, on="Science Area")
long["Pct of Project"] = np.where(long["Project Hours"]>0, long["Hours"]/long["Project Hours"], np.nan)
long["Pct of Area"] = np.where(long["Area Hours"]>0, long["Hours"]/long["Area Hours"], np.nan)

# ---- Sidebar filters
with st.sidebar:
    st.header("Filters")
    projects = sorted(long[project_col].unique().tolist())
    areas = sorted(long["Science Area"].unique().tolist())
    selected_projects = st.multiselect("Projects", projects, default=projects)
    selected_areas = st.multiselect("Science Areas", areas, default=areas)
    min_total = st.slider("Minimum total project hours", 0.0, float(proj_totals["Project Hours"].max()), 0.0, step=1.0)

filtered = long[long[project_col].isin(selected_projects) & long["Science Area"].isin(selected_areas)].copy()
keep = filtered.groupby(project_col)["Hours"].sum().reset_index()
keep = keep[keep["Hours"] >= min_total][project_col].tolist()
filtered = filtered[filtered[project_col].isin(keep)]

if filtered.empty:
    st.warning("No data after filtering. Relax your filters.")
    st.stop()

# KPIs
k1, k2, k3, k4 = st.columns(4)
k1.metric("Total Hours (filtered)", f"{filtered['Hours'].sum():,.0f}")
k2.metric("Projects (filtered)", f"{filtered[project_col].nunique():,}")
k3.metric("Science Areas (filtered)", f"{filtered['Science Area'].nunique():,}")
k4.metric("Median Hours / Project", f"{filtered.groupby(project_col)['Hours'].sum().median():,.0f}")

st.divider()

# Visual 1: % labour split by science area per project
st.subheader("% labour split by science area for each project")
pp = filtered[[project_col, "Science Area", "Pct of Project"]].copy()
pp["Pct of Project"] = pp["Pct of Project"] * 100.0
proj_order = filtered.groupby(project_col)["Hours"].sum().sort_values(ascending=False).index.tolist()
pp[project_col] = pd.Categorical(pp[project_col], categories=proj_order, ordered=True)
fig1 = px.bar(pp.sort_values([project_col, "Science Area"]),
              x=project_col, y="Pct of Project", color="Science Area",
              text=pp["Pct of Project"].map(lambda v: f"{v:.0f}%" if v >= 10 else ""))
fig1.update_layout(barmode="stack", yaxis_title="% of project labour",
                   xaxis_title="Project", yaxis=dict(ticksuffix="%"), height=520, margin=dict(t=40, r=10, b=0, l=10))
st.plotly_chart(fig1, use_container_width=True)
st.caption("Tip: click legend items to hide/show areas; hover to see exact values.")

st.divider()

# Visual 2: % distribution within chosen science area
st.subheader("% distribution of labour within a selected science area")
areas_sorted = sorted(filtered["Science Area"].unique().tolist())
area_choice = st.selectbox("Choose a science area", options=areas_sorted)
area_df = filtered[filtered["Science Area"] == area_choice].copy()

if area_df.empty:
    st.info("No rows for the selected area in current filter.")
else:
    area_totals_f = filtered.groupby("Science Area", as_index=False)["Hours"].sum().rename(columns={"Hours":"Area Hours"})
    area_df = area_df.merge(area_totals_f, on="Science Area", how="left")
    area_df["Pct of Area"] = np.where(area_df["Area Hours"]>0, area_df["Hours"]/area_df["Area Hours"]*100.0, np.nan)
    area_df = area_df.sort_values("Pct of Area", ascending=False)
    fig2 = px.bar(area_df, x="Pct of Area", y=project_col, orientation="h",
                  text=area_df["Pct of Area"].map(lambda v: f"{v:.1f}%"))
    fig2.update_layout(xaxis_title="% of science area labour", yaxis_title="Project",
                       xaxis=dict(ticksuffix="%"), height=600, margin=dict(t=40, r=10, b=10, l=10))
    st.plotly_chart(fig2, use_container_width=True)

st.divider()

# Detail table + downloads
st.subheader("Detail table (filtered)")
display_cols = [project_col, "Science Area", "Hours", "Project Hours", "Area Hours", "Pct of Project", "Pct of Area"]
tbl = filtered[display_cols].copy()
tbl["Pct of Project"] = tbl["Pct of Project"] * 100.0
tbl["Pct of Area"] = tbl["Pct of Area"] * 100.0
st.dataframe(tbl.sort_values([project_col, "Science Area"]).reset_index(drop=True), use_container_width=True)

st.subheader("Download filtered data")
def to_csv_bytes(df): return df.to_csv(index=False).encode("utf-8")
c1, c2 = st.columns(2)
with c1:
    st.download_button("Download CSV (filtered detail)", data=to_csv_bytes(tbl), file_name="labour_filtered_detail.csv", mime="text/csv")
with c2:
    wide = tbl.pivot_table(index=project_col, columns="Science Area", values="Hours", aggfunc="sum").fillna(0.0).reset_index()
    st.download_button("Download CSV (wide by project x area)", data=to_csv_bytes(wide), file_name="labour_wide_by_area.csv", mime="text/csv")

st.caption("No data is stored by this app. Deploy to Streamlit Cloud or host internally.")
