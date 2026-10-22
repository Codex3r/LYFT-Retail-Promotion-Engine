import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go

st.set_page_config(page_title="Assortment Elasticity", layout="wide")

st.title("Assortment Demand & Elasticity Archetypes")
st.caption("Product-level behavioral taxonomy: Mapping 2,500 catalog items across deal dependency, pantry-loading elasticity, and baseline loyalty.")

# 1. LOAD DATA
@st.cache_data
def load_data():
    timeline = pd.read_parquet("sku_timeline_mart.parquet")
    scorecard = pd.read_parquet("sku_prescriptive_scorecard.parquet")
    
    timeline["PRODUCT_ID"] = timeline["PRODUCT_ID"].astype(np.int64)
    scorecard["PRODUCT_ID"] = scorecard["PRODUCT_ID"].astype(np.int64)
    
    if "DATE" not in timeline.columns:
        base_date = pd.Timestamp("2024-01-01")
        timeline["DATE"] = base_date + pd.to_timedelta(timeline["DAY"] - 1, unit="D")
    else:
        timeline["DATE"] = pd.to_datetime(timeline["DATE"])
        
    return timeline, scorecard

try:
    timeline_df, scorecard_df = load_data()
except Exception as e:
    st.error(f"Error loading analytical data: {e}")
    st.stop()

# 2. TEMPORAL SEGREGATION CONTROLS
col_time_left, col_time_right = st.columns([2.5, 5.5])

with col_time_left:
    time_window = st.segmented_control(
        "Analysis Period",
        options=["All Time", "Past 1 Year", "Past 1 Month", "Past 1 Week"],
        default="All Time",
        help="Filter observation window to evaluate elasticity and deal dependency drift over time."
    )

# 3. DYNAMIC METRIC RECALCULATION
max_date = timeline_df["DATE"].max()

if time_window == "Past 1 Week":
    start_date = max_date - pd.Timedelta(days=7)
    window_timeline = timeline_df[timeline_df["DATE"] >= start_date]
elif time_window == "Past 1 Month":
    start_date = max_date - pd.Timedelta(days=30)
    window_timeline = timeline_df[timeline_df["DATE"] >= start_date]
elif time_window == "Past 1 Year":
    start_date = max_date - pd.Timedelta(days=365)
    window_timeline = timeline_df[timeline_df["DATE"] >= start_date]
else:
    window_timeline = timeline_df

if time_window == "All Time":
    # Use full precomputed scorecard
    active_df = scorecard_df.copy()
else:
    # Recalculate SKU-level metrics for the active window
    agg = window_timeline.groupby("PRODUCT_ID").agg(
        window_units=("daily_units", "sum"),
        window_revenue=("daily_revenue", "sum"),
        window_promo_units=("daily_units", lambda u: u[window_timeline.loc[u.index, "is_promo"] == 1].sum())
    ).reset_index()

    active_df = scorecard_df.drop(columns=["total_units", "total_revenue", "promo_share"]).merge(agg, on="PRODUCT_ID", how="inner")
    active_df.rename(columns={"window_units": "total_units", "window_revenue": "total_revenue"}, inplace=True)
    active_df["promo_share"] = np.where(
        active_df["total_units"] > 0,
        (active_df["window_promo_units"] / active_df["total_units"]) * 100.0,
        0.0
    )

with col_time_right:
    st.markdown(
        f"""
        <div style="text-align: right; margin-top: 24px; color: #64748B; font-size: 12px;">
            Active Window: <span style="color: #94A3B8; font-weight: 600;">{window_timeline['DATE'].min().strftime('%b %d, %Y')}</span> to <span style="color: #94A3B8; font-weight: 600;">{max_date.strftime('%b %d, %Y')}</span> • <b>{len(active_df):,}</b> Active SKUs
        </div>
        """,
        unsafe_allow_html=True
    )

# 4. PORTFOLIO SEGMENT KPI CARDS
pantry_loaders = active_df[active_df["PCI"] >= 0.45]
elastic_expanders = active_df[(active_df["PCI"] < 0.45) & (active_df["promo_share"] >= 30.0)]
baseline_regulars = active_df[(active_df["PCI"] < 0.45) & (active_df["promo_share"] < 30.0)]

col1, col2, col3 = st.columns(3)
with col1:
    st.metric(
        "Pantry-Loading SKUs (Storable)",
        f"{len(pantry_loaders):,} SKUs ({(len(pantry_loaders)/max(1, len(active_df)))*100:.1f}%)",
        delta="Severe Deficit Drag",
        delta_color="inverse"
    )
with col2:
    st.metric(
        "Elastic Volume Expanders",
        f"{len(elastic_expanders):,} SKUs ({(len(elastic_expanders)/max(1, len(active_df)))*100:.1f}%)",
        delta="Incremental Basket Lift",
        delta_color="normal"
    )
with col3:
    st.metric(
        "Inelastic Core Staples",
        f"{len(baseline_regulars):,} SKUs ({(len(baseline_regulars)/max(1, len(active_df)))*100:.1f}%)",
        delta="Full-Price Regulars",
        delta_color="off"
    )

st.write("")

# 5. 4-QUADRANT BEHAVIOR MATRIX (WebGL ScatterGL)
tier_colors = {
    "RED": "#F87171",
    "YELLOW": "#FBBF24",
    "GREEN": "#34D399"
}

fig = go.Figure()

for tier in ["GREEN", "YELLOW", "RED"]:
    sub = active_df[active_df["risk_tier"] == tier]
    sizes = np.clip(np.sqrt(sub["total_units"]) * 0.7, 4, 20)
    
    fig.add_trace(go.Scattergl(
        x=sub["promo_share"],
        y=sub["PCI"],
        mode="markers",
        name=f"{tier} ({len(sub):,} SKUs)",
        marker=dict(
            size=sizes,
            color=tier_colors[tier],
            opacity=0.42,
            line=dict(width=0.4, color="rgba(255,255,255,0.3)")
        ),
        text=sub["COMMODITY_DESC"],
        customdata=np.stack((sub["PRODUCT_ID"], sub["commodity_cohort"], sub["total_revenue"]), axis=-1),
        hovertemplate="<b>%{text}</b> (SKU #%{customdata[0]})<br>Cohort: %{customdata[1]}<br>Promo Share: <b>%{x:.1f}%</b><br>PCI: <b>%{y:.2f}</b><br>Revenue: <b>$%{customdata[2]:,.0f}</b><extra></extra>"
    ))

# Reference Threshold Lines
fig.add_hline(
    y=0.45, line_width=1.5, line_dash="dash", line_color="#F87171",
    annotation_text="Pantry Stockpiling Threshold (0.45)", annotation_position="top left",
    annotation_font=dict(color="#F87171", size=10)
)
fig.add_vline(
    x=35.0, line_width=1.5, line_dash="dot", line_color="#64748B",
    annotation_text="High Deal Reliance (35%)", annotation_position="top right",
    annotation_font=dict(color="#94A3B8", size=10)
)

fig.update_layout(
    template="plotly_dark",
    paper_bgcolor="rgba(0,0,0,0)",
    plot_bgcolor="#111827",
    height=480,
    margin=dict(l=15, r=15, t=30, b=15),
    legend=dict(
        orientation="h",
        yanchor="bottom",
        y=1.02,
        xanchor="right",
        x=1,
        font=dict(size=11, color="#94A3B8")
    ),
    hovermode="closest",
    xaxis=dict(showgrid=True, gridcolor="#1E293B", linecolor="#1F2937", title="Promotional Volume Dependency (% Sold on Deal)", range=[0, 100 if time_window in ["Past 1 Week", "Past 1 Month"] else 75]),
    yaxis=dict(showgrid=True, gridcolor="#1E293B", linecolor="#1F2937", title="Cannibalization Index (PCI)", range=[0, 0.95])
)

# Explicitly disable modebar to eliminate overlapping camera/zoom icons
st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False})

# 6. DIRECTIVE TABS
st.markdown("<p style='font-size: 13px; font-weight: 600; color: #94A3B8; margin-top: 10px; margin-bottom: 4px;'>CATEGORY OPERATIONAL DIRECTIVES</p>", unsafe_allow_html=True)

tab_a, tab_b, tab_c = st.tabs([
    "Pantry-Loading Essentials (Top-Right)",
    "Elastic Basket Expanders (Bottom-Right)",
    "Inelastic Staples (Left-Half)"
])

with tab_a:
    st.markdown("""
    * **Demand Dynamics**: Consumers forward-buy multiple weeks of supply when discounted, causing severe post-promotional volume troughs.
    * **Core Categories**: Paper Towels, Liquid Detergents, Bulk Facial Tissue, Canned Soup.
    * **Prescriptive Action**: **Cap promotional depth at ≤15%**, enforce **mandatory 35–42 day rest cooldowns**, and transition single-item cuts into *Multi-Buys (e.g., Buy 3 for $X)* to force higher basket thresholds.
    """)

with tab_b:
    st.markdown("""
    * **Demand Dynamics**: Demand is price-elastic; consumption expands directly on deal (entertaining, snacking) without dragging down subsequent baseline volume.
    * **Core Categories**: Carbonated Soft Drinks, Pre-Packaged Cookies, Salty Snacks.
    * **Prescriptive Action**: **Promote actively at 20%–25% discounts**. Secure vendor co-op trade allowances and feature endcap placement to maximize basket velocity.
    """)

with tab_c:
    st.markdown("""
    * **Demand Dynamics**: Everyday essentials bought on strict schedule; consumers purchase regardless of whether the product is promoted.
    * **Core Categories**: Fluid Milk, Fresh Eggs, Breakfast Bread, Specialty Baby Food.
    * **Prescriptive Action**: **Cease circular price discounts**. Promotional spend on these items is pure deadweight markdown cost, as regular shoppers will purchase them at full retail price.
    """)
