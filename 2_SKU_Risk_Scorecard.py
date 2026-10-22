import streamlit as st
import pandas as pd
import numpy as np

st.set_page_config(page_title="SKU Risk Scorecard", layout="wide")

st.title("SKU Risk Scorecard & Prescriptive Policy")
st.caption("Actionable merchandising directives: Dynamic discount ceilings (d*), inter-purchase rest cooldowns, and forward-buy risk mitigation.")

# 1. LOAD DATA
@st.cache_data
def load_scorecard():
    df = pd.read_parquet("sku_prescriptive_scorecard.parquet")
    df["PRODUCT_ID"] = df["PRODUCT_ID"].astype(np.int64)
    return df

try:
    scorecard = load_scorecard()
except Exception as e:
    st.error(f"Error loading scorecard artifact: {e}")
    st.stop()

# Dollar leak per SKU
scorecard["estimated_dollar_leak"] = scorecard["promo_volume"] * scorecard["PCI"] * 1.20

# 2. TOP 5 VALUE DESTRUCTION TRIAGE
st.markdown("<p style='font-size: 12px; font-weight: 600; color: #94A3B8; letter-spacing: 0.05em; text-transform: uppercase;'>Immediate Triage • Top 5 Value-Destroying Items</p>", unsafe_allow_html=True)
top_bleeders = scorecard.sort_values(by="estimated_dollar_leak", ascending=False).head(5)

t_cols = st.columns(5)
for idx, (_, row) in enumerate(top_bleeders.iterrows()):
    with t_cols[idx]:
        st.markdown(
            f"""
            <div style="background-color: #111827; border: 1px solid rgba(239, 68, 68, 0.3); border-radius: 8px; padding: 12px 14px; min-height: 120px;">
                <div style="display: flex; justify-content: space-between; align-items: center;">
                    <span style="background-color: rgba(239, 68, 68, 0.2); color: #F87171; font-size: 10px; font-weight: 700; padding: 2px 6px; border-radius: 4px;">#{idx+1} BLEED</span>
                    <span style="color: #64748B; font-size: 11px;">SKU #{row['PRODUCT_ID']}</span>
                </div>
                <div style="color: #F8FAFC; font-weight: 600; font-size: 13px; margin: 8px 0 2px 0; white-space: nowrap; overflow: hidden; text-overflow: ellipsis;" title="{row['COMMODITY_DESC']}">
                    {row['COMMODITY_DESC']}
                </div>
                <div style="color: #F87171; font-weight: 700; font-size: 17px; margin-top: 2px;">
                    -${row['estimated_dollar_leak']:,.0f}
                </div>
                <div style="color: #FBBF24; font-size: 11px; margin-top: 4px;">Cap: ≤{int(row['d_star_ceiling']*100)}% • {row['cooldown_rest_days']}d cooldown</div>
            </div>
            """,
            unsafe_allow_html=True
        )

st.write("")

# 3. INTERACTIVE CONTROL SHELF (Balanced widths)
filt_col1, filt_col2, filt_col3, filt_col4 = st.columns([1.2, 1.3, 2.5, 2.0])

with filt_col1:
    tier_filter = st.multiselect(
        "Risk Tier",
        options=["RED", "YELLOW", "GREEN"],
        default=["RED", "YELLOW", "GREEN"]
    )

with filt_col2:
    cohort_filter = st.multiselect(
        "Product Cohort",
        options=list(scorecard["commodity_cohort"].unique()),
        default=list(scorecard["commodity_cohort"].unique())
    )

with filt_col3:
    def categorize_action(act):
        if "Pantry Exhaustion" in act or "Basket Value Defense" in act:
            return "Margin Defense (High Risk)"
        elif "Subsidized Demand Taper" in act:
            return "Demand Correction (Deal Dependent)"
        elif "Controlled Profit Pulse" in act:
            return "Controlled Profit Pulse"
        else:
            return "Volume Growth"

    scorecard["strategy_group"] = scorecard["prescriptive_action"].apply(categorize_action)
    group_options = list(scorecard["strategy_group"].unique())
    group_filter = st.multiselect(
        "Operational Strategy",
        options=group_options,
        default=group_options
    )

with filt_col4:
    search_query = st.text_input("Quick Lookup", value="", placeholder="Search by SKU ID or Commodity...")

# Filter Application
filtered = scorecard[
    (scorecard["risk_tier"].isin(tier_filter)) &
    (scorecard["commodity_cohort"].isin(cohort_filter)) &
    (scorecard["strategy_group"].isin(group_filter))
].copy()

if search_query:
    q = search_query.strip()
    if q.isdigit():
        filtered = filtered[filtered["PRODUCT_ID"] == int(q)]
    else:
        filtered = filtered[filtered["COMMODITY_DESC"].str.contains(q, case=False)]

# Formatted DataFrame with clean column config
filtered["Cap_Display"] = (filtered["d_star_ceiling"] * 100).round(1).astype(str) + "%"
filtered["Cooldown_Display"] = filtered["cooldown_rest_days"].astype(str) + " Days"
filtered["Promo_Share_Display"] = filtered["promo_share"].round(1).astype(str) + "%"
filtered["PCI_Display"] = filtered["PCI"].apply(lambda x: f"{x:.2f}")

display_df = filtered[[
    "PRODUCT_ID",
    "COMMODITY_DESC",
    "commodity_cohort",
    "risk_tier",
    "PCI_Display",
    "Promo_Share_Display",
    "Cap_Display",
    "Cooldown_Display",
    "prescriptive_action"
]].rename(columns={
    "PRODUCT_ID": "SKU #",
    "COMMODITY_DESC": "Commodity",
    "commodity_cohort": "Cohort",
    "risk_tier": "Risk Tier",
    "PCI_Display": "PCI",
    "Promo_Share_Display": "Promo Share",
    "Cap_Display": "Cap (d*)",
    "Cooldown_Display": "Rest Cooldown",
    "prescriptive_action": "Prescribed Operational Strategy"
})

def highlight_tier(val):
    if val == "RED":
        return "background-color: rgba(239, 68, 68, 0.2); color: #F87171; font-weight: 600; text-align: center;"
    elif val == "YELLOW":
        return "background-color: rgba(245, 158, 11, 0.2); color: #FBBF24; font-weight: 600; text-align: center;"
    elif val == "GREEN":
        return "background-color: rgba(16, 185, 129, 0.2); color: #34D399; font-weight: 600; text-align: center;"
    return ""

styled_table = (
    display_df.style
    .map(highlight_tier, subset=["Risk Tier"])
    .set_properties(subset=["SKU #", "Cohort", "PCI", "Promo Share", "Cap (d*)", "Rest Cooldown"], **{"text-align": "center"})
    .set_properties(subset=["Commodity", "Prescribed Operational Strategy"], **{"text-align": "left"})
)

st.dataframe(
    styled_table,
    use_container_width=True,
    height=450,
    hide_index=True,
    column_config={
        "Prescribed Operational Strategy": st.column_config.TextColumn(width="large"),
        "Commodity": st.column_config.TextColumn(width="medium")
    }
)
st.caption(f"Showing {len(display_df):,} matching SKUs from the 2,500 catalog. Triage priorities require manual override before the next promo run.")
