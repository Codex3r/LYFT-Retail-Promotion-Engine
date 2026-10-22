import os
import pandas as pd

print("--> Phase 2 Preprocessing Pipeline Started...")

# -------------------------------------------------------------
# 1. Load Raw CSV Data
# -------------------------------------------------------------
print("Loading raw Dunnhumby CSV files...")
if not os.path.exists("transaction_data.csv") or not os.path.exists(
    "product.csv"
):
    print(
        "ERROR: 'transaction_data.csv' or 'product.csv' not found in the"
        " directory!"
    )
    exit(1)

df_trans = pd.read_csv("transaction_data.csv")
df_prod = pd.read_csv("product.csv")

initial_rows = len(df_trans)
print(f"Initial transaction rows loaded: {initial_rows:,}")

# -------------------------------------------------------------
# 2. Step 1: Transaction Integrity Guard
# -------------------------------------------------------------
print("Executing Step 1: Transaction Integrity Guard...")
df_trans = df_trans[(df_trans["QUANTITY"] > 0) & (df_trans["SALES_VALUE"] > 0)]

unit_price = df_trans["SALES_VALUE"] / df_trans["QUANTITY"]
wholesale_mask = ((df_trans["QUANTITY"] > 15) & (unit_price >= 2.0)) | (
    df_trans["QUANTITY"] > 30
)
df_trans = df_trans[~wholesale_mask]
print(f"Rows after Integrity Guard: {len(df_trans):,}")

# -------------------------------------------------------------
# 3. Step 2: Feature & Price Reconstruction Engine
# -------------------------------------------------------------
print("Executing Step 2: Feature & Price Reconstruction...")
retail_disc = df_trans["RETAIL_DISC"].abs().fillna(0)
coupon_disc = df_trans["COUPON_DISC"].abs().fillna(0)
coupon_match = df_trans["COUPON_MATCH_DISC"].abs().fillna(0)

df_trans["total_discount"] = retail_disc + coupon_disc + coupon_match
df_trans["base_revenue"] = df_trans["SALES_VALUE"] + df_trans["total_discount"]
df_trans["base_unit_price"] = (
    df_trans["base_revenue"] / df_trans["QUANTITY"]
).round(2)
df_trans["discount_pct"] = (
    df_trans["total_discount"] / df_trans["base_revenue"]
).round(4)
df_trans["is_promo"] = (df_trans["discount_pct"] >= 0.20).astype(int)

# -------------------------------------------------------------
# 4. Step 3: Tri-Cohort Catalog Taxonomy Mapping
# -------------------------------------------------------------
print("Executing Step 3: Catalog Taxonomy & Cohort Mapping...")
df_merged = df_trans.merge(
    df_prod[["PRODUCT_ID", "COMMODITY_DESC", "DEPARTMENT"]],
    on="PRODUCT_ID",
    how="inner",
)

storable_commodities = [
    "LAUNDRY DETERGENT",
    "PAPER TOWELS",
    "CANNED VEGETABLES",
    "PASTA",
]
perishable_commodities = ["MILK", "EGGS", "FRESH BREAD", "YOGURT"]
expandable_commodities = ["SOFT DRINKS", "SNACKS", "ICE CREAM", "CHIPS"]


def assign_cohort(comm):
  if comm in storable_commodities:
    return "STORABLE"
  elif comm in perishable_commodities:
    return "PERISHABLE"
  elif comm in expandable_commodities:
    return "EXPANDABLE"
  else:
    return "OTHER_GROCERY"


df_merged["commodity_cohort"] = df_merged["COMMODITY_DESC"].apply(
    assign_cohort
)
valid_departments = ["GROCERY", "DRUG GM", "PASTRY", "PRODUCE"]
df_filtered = df_merged[df_merged["DEPARTMENT"].isin(valid_departments)].copy()

# -------------------------------------------------------------
# 5. Step 4: Same-Basket Consolidation (Fixing zero-day glitches)
# -------------------------------------------------------------
print("Executing Step 4: Same-Basket Consolidation...")
df_consolidated = (
    df_filtered.groupby(
        [
            "household_key",
            "BASKET_ID",
            "PRODUCT_ID",
            "DAY",
            "commodity_cohort",
            "COMMODITY_DESC",
        ],
        as_index=False,
    )
    .agg({
        "QUANTITY": "sum",
        "SALES_VALUE": "sum",
        "total_discount": "sum",
        "base_revenue": "sum",
    })
)

# -------------------------------------------------------------
# 6. Step 5: Chronological Ordering & Left-Censoring Anchors
# -------------------------------------------------------------
print("Executing Step 5: Chronological Sorting & Anchoring...")
df_consolidated.sort_values(
    by=["household_key", "PRODUCT_ID", "DAY"], ascending=True, inplace=True
)
df_consolidated["is_first_purchase"] = (
    df_consolidated.groupby(["household_key", "PRODUCT_ID"]).cumcount() == 0
).astype(int)

# -------------------------------------------------------------
# 7. Step 6: Schema Optimization & Snappy-Compressed Export
# -------------------------------------------------------------
print("Executing Step 6: Serialization to Snappy Parquet...")
output_filename = "curated_dunnhumby_transactions.parquet"
df_consolidated.to_parquet(
    output_filename, engine="pyarrow", compression="snappy", index=False
)

# -------------------------------------------------------------
# SUCCESSFUL COMPLETION MESSAGE
# -------------------------------------------------------------
print("\n" + "=" * 60)
print("SUCCESS: Phase 2 Preprocessing Pipeline Executed Flawlessly! 🎉")
print("=" * 60)
print(f"📊 Original Raw Rows Processed : {initial_rows:,}")
print(f"✨ Final Clean Curated Rows  : {len(df_consolidated):,}")
print(f"💾 Output File Serialized    : {output_filename}")
print("🚀 Your dataset is locked in, compressed, and ready for modeling!")
print("=" * 60)
