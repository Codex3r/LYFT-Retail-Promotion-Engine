import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go

st.title("Executive Retail Performance Overview")
st.caption("Distributed Hadoop HDFS & PySpark Windowing Mart • Trade Promotion P&L & Category Capital Exposure")

# 1. DATA INGESTION
@st.cache_data
def load_data():
    scorecard = pd.read_parquet("sku_prescriptive_scorecard.parquet")
    timeline = pd.read_parquet("sku_timeline_mart.parquet")
    scorecard["PRODUCT_ID"] = scorecard["PRODUCT_ID"].astype(np.int64)
    timeline["PRODUCT_ID"] = timeline["PRODUCT_ID"].astype(np.int64)
    return scorecard, timeline

try:
    scorecard_df, timeline_df = load_data()
except Exception as e:
    st.error(f"Error loading analytical data: {e}")
    st.stop()

# 2. FINANCIAL CALCULATIONS
audited_skus = len(scorecard_df)
tot_revenue = scorecard_df["total_revenue"].sum()
tot_volume = scorecard_df["total_units"].sum()
tot_promo_vol = scorecard_df["promo_volume"].sum()
promo_vol_share = (tot_promo_vol / tot_volume * 100) if tot_volume > 0 else 0.0

promo_revenue = tot_revenue * (promo_vol_share / 100.0)
avg_discount_rate = (scorecard_df["avg_discount"].mean() / 100.0) if "avg_discount" in scorecard_df.columns else 0.20
markdown_dollars = promo_revenue * avg_discount_rate

mean_pci = scorecard_df["PCI"].mean()
trough_bleed_dollars = (promo_revenue * mean_pci) * 0.28
net_trade_margin = promo_revenue - markdown_dollars - trough_bleed_dollars

red_skus = (scorecard_df["risk_tier"] == "RED").sum()
red_pct = (red_skus / audited_skus * 100) if audited_skus > 0 else 0.0
red_revenue = scorecard_df[scorecard_df["risk_tier"] == "RED"]["total_revenue"].sum()

# 3. EXECUTIVE KPI COMMAND STRIP
col1, col2, col3, col4, col5 = st.columns(5)
col1.metric("Audited Products", f"{audited_skus:,} SKUs")
col2.metric("Portfolio Revenue", f"${tot_revenue:,.0f}")
col3.metric("Promo Dependency", f"{promo_vol_share:.1f}%")
col4.metric("Net Trade Contribution", f"${net_trade_margin:,.0f}", delta=f"-${(markdown_dollars+trough_bleed_dollars)/1e3:.1f}k Leak", delta_color="inverse")
col5.metric("High-Risk (RED) Exposure", f"{red_pct:.1f}% SKUs", delta=f"${red_revenue/1e3:.1f}k at Risk", delta_color="inverse")

st.write("")

# Common Plotly config for hover-only toolbar without camera button
clean_config = {
    'displayModeBar': 'hover',
    'displaylogo': False,
    'modeBarButtonsToRemove': ['toImage', 'sendDataToCloud']
}

col_chart_left, col_chart_right = st.columns([1, 1])

# --- CHART 1: WATERFALL BRIDGE ---
with col_chart_left:
    st.markdown("<p style='font-size: 13px; font-weight: 600; color: #94A3B8; margin-bottom: 6px;'>PROMOTIONAL MARGIN REALIZATION BRIDGE (P&L)</p>", unsafe_allow_html=True)
    
    fig_waterfall = go.Figure(go.Waterfall(
        name="Trade P&L",
        orientation="v",
        measure=["relative", "relative", "relative", "total"],
        x=["Promo Gross", "Markdowns", "Stockpiling Bleed", "Net Margin"],
        textposition="outside",
        text=[f"+${promo_revenue/1e3:.1f}k", f"-${markdown_dollars/1e3:.1f}k", f"-${trough_bleed_dollars/1e3:.1f}k", f"${net_trade_margin/1e3:.1f}k"],
        y=[promo_revenue, -markdown_dollars, -trough_bleed_dollars, net_trade_margin],
        connector={"line": {"color": "#334155", "width": 1.5}},
        decreasing={"marker": {"color": "#F87171"}},
        increasing={"marker": {"color": "#34D399"}},
        totals={"marker": {"color": "#38BDF8"}}
    ))
    
    fig_waterfall.update_layout(
        template="plotly_dark",
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="#111827",
        margin=dict(l=20, r=20, t=25, b=25),
        height=340,
        showlegend=False,
        font=dict(family="sans-serif", size=11, color="#94A3B8"),
        xaxis=dict(showgrid=False, linecolor="#1F2937"),
        yaxis=dict(showgrid=True, gridcolor="#1E293B", linecolor="#1F2937")
    )
    st.plotly_chart(fig_waterfall, use_container_width=True, config=clean_config)

# --- CHART 2: COHORT STACKED REVENUE ---
with col_chart_right:
    st.markdown("<p style='font-size: 13px; font-weight: 600; color: #94A3B8; margin-bottom: 6px;'>REVENUE AT RISK BY PRODUCT COHORT</p>", unsafe_allow_html=True)
    
    cohort_revenue = scorecard_df.groupby(["commodity_cohort", "risk_tier"])["total_revenue"].sum().unstack(fill_value=0)
    for t in ["GREEN", "YELLOW", "RED"]:
        if t not in cohort_revenue.columns:
            cohort_revenue[t] = 0.0

    cohorts = cohort_revenue.index.tolist()
    fig_cohort = go.Figure()
    fig_cohort.add_trace(go.Bar(
        y=cohorts, x=cohort_revenue["GREEN"], name="Green (Incremental)",
        orientation="h", marker=dict(color="#34D399"),
        hovertemplate="<b>%{y}</b> • Green: $%{x:,.0f}<extra></extra>"
    ))
    fig_cohort.add_trace(go.Bar(
        y=cohorts, x=cohort_revenue["YELLOW"], name="Yellow (Controlled)",
        orientation="h", marker=dict(color="#FBBF24"),
        hovertemplate="<b>%{y}</b> • Yellow: $%{x:,.0f}<extra></extra>"
    ))
    fig_cohort.add_trace(go.Bar(
        y=cohorts, x=cohort_revenue["RED"], name="Red (At Risk)",
        orientation="h", marker=dict(color="#F87171"),
        hovertemplate="<b>%{y}</b> • Red: $%{x:,.0f}<extra></extra>"
    ))

    fig_cohort.update_layout(
        barmode="stack",
        template="plotly_dark",
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="#111827",
        margin=dict(l=20, r=20, t=25, b=25),
        height=340,
        font=dict(family="sans-serif", size=11, color="#94A3B8"),
        legend=dict(
            orientation="h",
            yanchor="bottom",
            y=1.02,
            xanchor="left",
            x=0,
            font=dict(size=11, color="#94A3B8")
        ),
        xaxis=dict(title=None, showgrid=True, gridcolor="#1E293B", linecolor="#1F2937"),
        yaxis=dict(title=None, showgrid=False, linecolor="#1F2937")
    )
    st.plotly_chart(fig_cohort, use_container_width=True, config=clean_config)

# 4. STRATEGIC EXECUTIVE BRIEFING
st.markdown(
    f"""
    <div style="background-color: #111827; border: 1px solid #1F2937; padding: 14px 18px; border-radius: 8px; border-left: 4px solid #38BDF8; margin-top: 10px;">
        <span style="color: #94A3B8; font-size: 11px; font-weight: 600; text-transform: uppercase; letter-spacing: 0.05em;">Portfolio Directive</span><br>
        <span style="color: #F8FAFC; font-size: 13px; line-height: 1.5;">
            Gross promotion sales generated <b>${promo_revenue:,.0f}</b>. Trade discounts absorbed <b>${markdown_dollars:,.0f}</b> and post-promotional stockpiling troughs destroyed an estimated <b>${trough_bleed_dollars:,.0f}</b> in baseline margin, leaving <b>${net_trade_margin:,.0f}</b> in net trade contribution. High forward-buying exposure is concentrated in <b>{red_skus} STORABLE catalog items</b>.
        </span>
    </div>
    """,
    unsafe_allow_html=True
)
