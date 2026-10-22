import streamlit as st

st.set_page_config(
    page_title="Nexus Retail Intelligence",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Deep Slate Navy Enterprise Design System
st.markdown(
    """
    <style>
        /* Base Canvas Background */
        .stApp {
            background-color: #090D16;
            color: #E2E8F0;
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
        }

        /* Sidebar Styling */
        section[data-testid="stSidebar"] {
            background-color: #0D1322;
            border-right: 1px solid #1E293B;
        }

        /* Metric Cards */
        div[data-testid="stMetric"] {
            background-color: #111827;
            border: 1px solid #1F2937;
            padding: 12px 16px;
            border-radius: 8px;
            box-shadow: 0 1px 3px rgba(0, 0, 0, 0.2);
        }
        div[data-testid="stMetricLabel"] p {
            color: #94A3B8;
            font-size: 12px;
            font-weight: 500;
            letter-spacing: 0.02em;
            text-transform: uppercase;
        }
        div[data-testid="stMetricValue"] div {
            color: #F8FAFC;
            font-size: 20px;
            font-weight: 600;
        }

        /* Streamlit Native Elements Polish */
        .stSelectbox label, .stMultiSelect label, .stTextInput label {
            color: #94A3B8 !important;
            font-size: 12px !important;
            font-weight: 500 !important;
        }
        div[data-baseweb="select"] {
            background-color: #111827;
            border-color: #1F2937;
        }

        /* Tabs Polish */
        button[data-baseweb="tab"] {
            font-size: 13px !important;
            font-weight: 500 !important;
            color: #94A3B8 !important;
        }
        button[aria-selected="true"] {
            color: #38BDF8 !important;
            border-bottom-color: #38BDF8 !important;
        }
    </style>
    """,
    unsafe_allow_html=True
)

# Professional Sidebar Header Branding
with st.sidebar:
    st.markdown(
        """
        <div style="padding: 6px 4px 18px 4px; border-bottom: 1px solid #1E293B; margin-bottom: 14px;">
            <div style="display: flex; align-items: center; gap: 8px;">
                <div style="width: 10px; height: 10px; border-radius: 2px; background: #38BDF8;"></div>
                <span style="color: #F8FAFC; font-weight: 700; font-size: 15px; letter-spacing: 0.05em;">NEXUS RETAIL</span>
            </div>
            <div style="margin-top: 4px; display: flex; align-items: center; gap: 6px;">
                <span style="font-size: 10px; background-color: rgba(16, 185, 129, 0.15); color: #34D399; padding: 2px 6px; border-radius: 4px; font-weight: 600;">PROD v3.3</span>
                <span style="font-size: 11px; color: #64748B;">HDFS Windowing Engine</span>
            </div>
        </div>
        """,
        unsafe_allow_html=True
    )

overview_page = st.Page("pages/1_Executive_Overview.py", title="Executive Overview")
scorecard_page = st.Page("pages/2_SKU_Risk_Scorecard.py", title="SKU Risk Scorecard")
simulator_page = st.Page("pages/3_Prescriptive_Simulator.py", title="Prescriptive Simulator")
archetypes_page = st.Page("pages/4_Shopper_Archetypes.py", title="Assortment Elasticity")

pg = st.navigation([overview_page, scorecard_page, simulator_page, archetypes_page])
pg.run()
