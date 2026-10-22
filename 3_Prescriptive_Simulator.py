import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
import pyarrow.dataset as ds

st.set_page_config(page_title="Prescriptive Simulator", layout="wide")

st.title("Dynamic SKU Simulator & Promotion Timeline")
st.caption("Longitudinal SKU telemetry: Baseline stability, promotional lift spikes, and post-promotional trough deficits.")

# 1. LOAD DATA
@st.cache_data
def load_scorecard():
    sc = pd.read_parquet("sku_prescriptive_scorecard.parquet")
    sc["PRODUCT_ID"] = sc["PRODUCT_ID"].astype(np.int64)
    return sc

try:
    scorecard_df = load_scorecard()
except Exception as e:
    st.error(f"Error loading scorecard: {e}")
    st.stop()

scorecard_df["sku_display"] = (
    scorecard_df["COMMODITY_DESC"].astype(str) + " • SKU #" + scorecard_df["PRODUCT_ID"].astype(str)
)

# 2. SELECTOR SETUP
selected_display = st.selectbox(
    "Select Target SKU (2,500 Active Catalog):",
    options=scorecard_df["sku_display"].values,
    index=0
)

sku_meta = scorecard_df[scorecard_df["sku_display"] == selected_display].iloc[0]
selected_sku = int(sku_meta["PRODUCT_ID"])

@st.cache_data
def get_sku_timeline(product_id: int):
    dataset = ds.dataset("sku_timeline_mart.parquet", format="parquet")
    table = dataset.to_table(filter=ds.field("PRODUCT_ID") == product_id)
    df = table.to_pandas()
    
    if "DATE" not in df.columns:
        base_date = pd.Timestamp("2024-01-01")
        df["DATE"] = base_date + pd.to_timedelta(df["DAY"] - 1, unit="D")
    else:
        df["DATE"] = pd.to_datetime(df["DATE"])
        
    return df.sort_values("DATE")

sku_timeline = get_sku_timeline(selected_sku)

# Metrics
pci = float(sku_meta.get("PCI", 0.45))
cooldown = int(sku_meta.get("cooldown_rest_days", 21))
raw_ceiling = sku_meta.get("d_star_ceiling", 0.20)
ceiling = int(raw_ceiling * 100) if raw_ceiling <= 1.0 else int(raw_ceiling)
tier = str(sku_meta.get("risk_tier", "YELLOW")).upper()
action_text = sku_meta.get("prescriptive_action", "Standard Review")

# 3. INTEGRATED METRIC STRIP (No detached strings)
col1, col2, col3, col4 = st.columns(4)
col1.metric("Selected SKU", f"#{selected_sku}", help=f"{sku_meta['COMMODITY_DESC']} ({sku_meta['commodity_cohort']})")
col2.metric("Stockpiling Propensity (PCI)", f"{pci:.2f}")
col3.metric("Optimal Ceiling (d*)", f"{ceiling}%")
col4.metric("Mandatory Cooldown", f"{cooldown} Days")

badge_border = "#F87171" if tier == "RED" else "#FBBF24" if tier == "YELLOW" else "#34D399"
st.markdown(
    f"""
    <div style="background-color: #111827; border: 1px solid #1F2937; padding: 12px 18px; border-radius: 8px; border-left: 4px solid {badge_border}; margin: 10px 0 16px 0;">
        <span style="color: #94A3B8; font-size: 11px; font-weight: 600; text-transform: uppercase; letter-spacing: 0.05em;">Prescribed Policy ({tier} Risk Tier)</span><br>
        <span style="color: #F8FAFC; font-weight: 500; font-size: 13px; line-height: 1.5;">{action_text}</span>
    </div>
    """,
    unsafe_allow_html=True
)

# 4. CAVITY IDENTIFICATION
sku_timeline["prev_promo"] = sku_timeline["is_promo"].rolling(7, min_periods=1).max().shift(1).fillna(0)
sku_timeline["is_trough"] = (
    (sku_timeline["is_promo"] == 0) & 
    (sku_timeline["prev_promo"] > 0) & 
    (sku_timeline["daily_units"] < sku_timeline["baseline_28d"])
)

def assign_volume_color(row):
    if row["is_promo"] > 0:
        return "#F59E0B"
    elif row["is_trough"]:
        return "#EF4444"
    else:
        return "#0284C7"

bar_colors = sku_timeline.apply(assign_volume_color, axis=1).tolist()
state_labels = [
    "Promotional Lift Spike" if p > 0 
    else "Post-Promo Trough Deficit" if t 
    else "Baseline Flow" 
    for p, t in zip(sku_timeline["is_promo"], sku_timeline["is_trough"])
]

sku_timeline["trough_floor"] = np.where(sku_timeline["is_trough"], sku_timeline["daily_units"], np.nan)
sku_timeline["trough_ceiling"] = np.where(sku_timeline["is_trough"], sku_timeline["baseline_28d"], np.nan)

# 5. STREAMLINED TIMELINE GRAPH
fig = go.Figure()

fig.add_trace(go.Bar(
    x=sku_timeline["DATE"],
    y=sku_timeline["daily_units"],
    name="Daily Units",
    marker=dict(color=bar_colors, opacity=0.9),
    customdata=state_labels,
    hovertemplate="<b>%{x|%b %d, %Y}</b><br>Volume: <b>%{y:,.0f} units</b><br>State: %{customdata}<extra></extra>"
))

fig.add_trace(go.Scatter(
    x=sku_timeline["DATE"],
    y=sku_timeline["baseline_28d"],
    name="28d Baseline",
    line=dict(color="#CBD5E1", width=1.5, dash="dash"),
    mode="lines",
    hovertemplate="Baseline: <b>%{y:.1f}</b><extra></extra>"
))

# Shaded Deficit Cavity
fig.add_trace(go.Scatter(
    x=sku_timeline["DATE"],
    y=sku_timeline["trough_floor"],
    mode="lines",
    line=dict(width=0),
    showlegend=False,
    hoverinfo="skip"
))
fig.add_trace(go.Scatter(
    x=sku_timeline["DATE"],
    y=sku_timeline["trough_ceiling"],
    mode="lines",
    line=dict(width=0),
    fill="tonexty",
    fillcolor="rgba(239, 68, 68, 0.22)",
    name="Trough Deficit",
    hoverinfo="skip"
))

clean_config = {
    'displayModeBar': 'hover',
    'displaylogo': False,
    'modeBarButtonsToRemove': ['toImage', 'sendDataToCloud']
}

fig.update_layout(
    template="plotly_dark",
    paper_bgcolor="rgba(0,0,0,0)",
    plot_bgcolor="#111827",
    height=460,
    margin=dict(l=15, r=15, t=30, b=15),
    legend=dict(
        orientation="h",
        yanchor="bottom",
        y=1.02,
        xanchor="right",
        x=1,
        font=dict(size=11, color="#94A3B8")
    ),
    hovermode="x unified",
    xaxis=dict(
        showgrid=True,
        gridcolor="#1E293B",
        linecolor="#1F2937",
        rangeselector=dict(
            buttons=list([
                dict(count=1, label="1M", step="month", stepmode="backward"),
                dict(count=3, label="3M", step="month", stepmode="backward"),
                dict(count=6, label="6M", step="month", stepmode="backward"),
                dict(count=1, label="1Y", step="year", stepmode="backward"),
                dict(step="all", label="All")
            ]),
            bgcolor="#1E293B",
            activecolor="#0284C7",
            font=dict(color="#F8FAFC", size=10)
        ),
        type="date"
    ),
    yaxis=dict(title="Units Sold", showgrid=True, gridcolor="#1E293B", linecolor="#1F2937", zeroline=False)
)

st.plotly_chart(fig, use_container_width=True, config=clean_config)
