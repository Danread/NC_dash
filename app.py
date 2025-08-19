import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px
import plotly.graph_objects as go
from pptx import Presentation
from pptx.util import Inches, Pt
import io

st.set_page_config(page_title="UKCEH NC labour explorer", layout="wide")

# --- Load data ---
@st.cache_data
def load_data(uploaded_file=None):
    if uploaded_file is not None:
        if uploaded_file.name.endswith(".xlsx"):
            df = pd.read_excel(uploaded_file)
        else:
            df = pd.read_csv(uploaded_file)
    else:
        df = pd.read_excel("NC_analysis_dash.xlsx")  # default file bundled
    return df

uploaded = st.file_uploader("Upload updated NC_analysis_dash.xlsx (optional)", type=["xlsx","csv"])
df = load_data(uploaded)

# --- Sidebar filters ---
st.sidebar.header("Filters")
hide_prof = st.sidebar.checkbox("Hide Professional Services by default", value=True)
nc_types = st.sidebar.multiselect("NC_type filter", sorted(df["NC_type"].dropna().unique()), default=None)
view_mode = st.sidebar.radio("View mode", ["Hours","Percent"], index=0)

# filter
filtered = df.copy()
if hide_prof and "Professional Services" in filtered["Science Area"].unique():
    filtered = filtered[filtered["Science Area"] != "Professional Services"]
if nc_types:
    filtered = filtered[filtered["NC_type"].isin(nc_types)]

# --- Shared colour map for Science Areas ---
areas_in_view = sorted(filtered["Science Area"].dropna().unique().tolist())
palette = px.colors.qualitative.Plotly
area_color_map = {area: palette[i % len(palette)] for i, area in enumerate(areas_in_view)}

# --- Tabs ---
tab1, tab2, tab3, tab4, tab5 = st.tabs([
    "Project split by science area",
    "Distribution within a science area",
    "Staff workload (by project)",
    "Project → staff distribution (single project)",
    "Export"
])

# --- Tab 1 ---
with tab1:
    st.subheader("Project split by science area")
    proj_totals = filtered.groupby(["Project","Science Area"], as_index=False)["Hours"].sum()
    proj_totals["Total"] = proj_totals.groupby("Project")["Hours"].transform("sum")

    if view_mode=="Percent":
        proj_totals["Value"] = proj_totals["Hours"]/proj_totals["Total"]*100
        xaxis_title = "% of labour"
        xaxis = dict(ticksuffix="%")
    else:
        proj_totals["Value"] = proj_totals["Hours"]
        xaxis_title = "Hours"
        xaxis = dict()

    fig1 = px.bar(proj_totals, x="Project", y="Value", color="Science Area",
                  color_discrete_map=area_color_map,
                  barmode="stack")
    fig1.update_layout(xaxis_title="Project", yaxis_title=xaxis_title, xaxis=xaxis)
    st.plotly_chart(fig1, use_container_width=True)

    # Toggle for stacked by Science Area
    mode = st.radio("Plot mode", ["Projects stacked by Area","Areas stacked by Project"], horizontal=True)
    if mode=="Projects stacked by Area":
        st.plotly_chart(fig1, use_container_width=True)
    else:
        area_totals = proj_totals.groupby(["Science Area","Project"], as_index=False)["Value"].sum()
        fig_alt = px.bar(area_totals, x="Science Area", y="Value", color="Project",
                         barmode="stack")
        fig_alt.update_layout(yaxis_title=xaxis_title)
        st.plotly_chart(fig_alt, use_container_width=True)

# --- Tab 2 ---
with tab2:
    st.subheader("Distribution within a science area")
    areas = sorted(filtered["Science Area"].dropna().unique())
    chosen_area = st.selectbox("Choose science area", areas)
    area_df = filtered[filtered["Science Area"]==chosen_area].groupby("Project", as_index=False)["Hours"].sum()
    total = area_df["Hours"].sum()
    if view_mode=="Percent":
        area_df["Value"] = area_df["Hours"]/total*100
        xlabel = "% of labour"; xaxis = dict(ticksuffix="%")
    else:
        area_df["Value"] = area_df["Hours"]; xlabel = "Hours"; xaxis = dict()
    fig2 = px.bar(area_df, x="Value", y="Project", orientation="h")
    fig2.update_layout(xaxis_title=xlabel, yaxis_title="Project", xaxis=xaxis)
    st.plotly_chart(fig2, use_container_width=True)

# --- Tab 3 ---
with tab3:
    st.subheader("Staff workload (by project)")
    staff_df = filtered.groupby(["Person","Project"], as_index=False)["Hours"].sum()
    totals = staff_df.groupby("Person")["Hours"].transform("sum")
    if view_mode=="Percent":
        staff_df["Value"] = staff_df["Hours"]/totals*100
        xlab = "% of person's hours"; xaxis=dict(ticksuffix="%")
    else:
        staff_df["Value"] = staff_df["Hours"]; xlab="Hours"; xaxis=dict()
    fig3 = px.bar(staff_df, x="Value", y="Person", color="Project", orientation="h")
    fig3.update_layout(xaxis_title=xlab, yaxis_title="Staff", xaxis=xaxis, height=600)
    st.plotly_chart(fig3, use_container_width=True)

# --- Tab 4 ---
with tab4:
    st.subheader("Project → staff distribution (single project)")
    projects = sorted(filtered["Project"].unique())
    proj_choice = st.selectbox("Choose a project", projects)
    proj_df = filtered[filtered["Project"]==proj_choice]
    by_psa = proj_df.groupby(["Person","Science Area"], as_index=False)["Hours"].sum()
    proj_total = by_psa["Hours"].sum()
    if view_mode=="Percent":
        by_psa["Value"] = by_psa["Hours"]/proj_total*100
        xlab="% of project hours"; xaxis=dict(ticksuffix="%"); fmt=lambda v:f"{v:.1f}%"
    else:
        by_psa["Value"] = by_psa["Hours"]; xlab="Hours"; xaxis=dict(); fmt=lambda v:f"{v:,.0f}"
    totals_per_person = by_psa.groupby("Person", as_index=False)["Hours"].sum().sort_values("Hours", ascending=False)
    people_order = totals_per_person["Person"].tolist()
    by_psa["Person"] = pd.Categorical(by_psa["Person"], categories=people_order, ordered=True)
    height = max(400, min(1200, 28*len(people_order)))
    fig4 = px.bar(by_psa, x="Value", y="Person", color="Science Area",
                  color_discrete_map=area_color_map, orientation="h",
                  text=by_psa["Value"].map(fmt))
    fig4.update_layout(barmode="stack", xaxis_title=xlab, yaxis_title="Staff", xaxis=xaxis, height=height)
    st.plotly_chart(fig4, use_container_width=True)

# --- Tab 5: Export ---
with tab5:
    st.subheader("Export")
    st.info("Use the buttons below to export plots as PNG or PowerPoint.")
    # Example: Export first chart
    buf = io.BytesIO()
    fig1.write_image(buf, format="png")
    st.download_button("Download Project split (PNG)", data=buf.getvalue(), file_name="split.png")
