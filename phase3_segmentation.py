import os
import joblib
import numpy as np
import pandas as pd
from sklearn.cluster import KMeans
from sklearn.preprocessing import StandardScaler

print("--> Phase 3: Behavioral Feature Engineering & Segmentation Started...")

# -------------------------------------------------------------
# 1. Load Curated Dataset & Ensure Derived Features
# -------------------------------------------------------------
input_file = "curated_dunnhumby_transactions.parquet"
if not os.path.exists(input_file):
    print(
        f"ERROR: '{input_file}' not found! Run Phase 2 preprocessing script"
        " first."
    )
    exit(1)

print(f"Loading curated dataset from {input_file}...")
df = pd.read_parquet(input_file)
print(f"Loaded rows: {len(df):,}")

# Re-derive discount percentage and promotional flag for analytics
df["discount_pct"] = np.where(
    df["base_revenue"] > 0, df["total_discount"] / df["base_revenue"], 0.0
)
df["is_promo"] = (df["discount_pct"] >= 0.20).astype(int)

# -------------------------------------------------------------
# 2. Step 1: Inter-Purchase Time (IPT) & Stockpiling Index ($PSI$)
# -------------------------------------------------------------
print(
    "Executing Step 1: Calculating Inter-Purchase Time (IPT) & Stockpiling"
    " Index..."
)

# Sort chronologically to compute time gaps
df = df.sort_values(by=["household_key", "PRODUCT_ID", "DAY"])

# Calculate delta time (IPT) between consecutive trips for the same household-product pair
df["prev_day"] = df.groupby(["household_key", "PRODUCT_ID"])["DAY"].shift(1)
df["ipt"] = df["DAY"] - df["prev_day"]

# Filter out initial purchase records (where ipt is NaN) for interval calculations
df_intervals = df[df["ipt"].notna() & (df["ipt"] > 0)].copy()

# Compute median baseline IPT and promotional IPT per household/product
promo_ipt = (
    df_intervals[df_intervals["is_promo"] == 1]
    .groupby("household_key")["ipt"]
    .median()
    .rename("ipt_promo")
)
base_ipt = (
    df_intervals[df_intervals["is_promo"] == 0]
    .groupby("household_key")["ipt"]
    .median()
    .rename("ipt_base")
)

# Merge back into a household summary table
df_hh_ipt = pd.concat([base_ipt, promo_ipt], axis=1).fillna(0)

# Calculate Stockpiling Index (PSI): Ratio of promotional interval expansion relative to baseline
df_hh_ipt["stockpiling_index"] = np.where(
    df_hh_ipt["ipt_base"] > 0,
    df_hh_ipt["ipt_promo"] / df_hh_ipt["ipt_base"],
    1.0,
)

# -------------------------------------------------------------
# 3. Step 2: Promotional Elasticity & Cohort Volume Ratios
# -------------------------------------------------------------
print(
    "Executing Step 2: Deriving Cohort Ratios & Promotional Sensitivity..."
)

hh_spend = df.groupby("household_key").agg(
    total_spend=("SALES_VALUE", "sum"),
    avg_discount_pct=("discount_pct", "mean"),
    shopping_trips=("BASKET_ID", "nunique"),
)

# Calculate storable-to-perishable volume ratio per household
cohort_pivot = (
    df.pivot_table(
        index="household_key",
        columns="commodity_cohort",
        values="QUANTITY",
        aggfunc="sum",
        fill_value=0,
    )
    .reset_index()
)

for col in ["STORABLE", "PERISHABLE", "EXPANDABLE"]:
  if col not in cohort_pivot.columns:
    cohort_pivot[col] = 0.0

cohort_pivot["storable_perishable_ratio"] = np.where(
    cohort_pivot["PERISHABLE"] > 0,
    cohort_pivot["STORABLE"] / cohort_pivot["PERISHABLE"],
    cohort_pivot["STORABLE"],
)

df_features = hh_spend.join(df_hh_ipt[["stockpiling_index"]], how="left").join(
    cohort_pivot[
        ["household_key", "storable_perishable_ratio", "STORABLE", "PERISHABLE"]
    ].set_index("household_key"),
    how="left",
)
df_features = df_features.fillna(0)

# Save intermediate feature matrix
features_filename = "household_behavior_features.parquet"
df_features.reset_index().to_parquet(
    features_filename, engine="pyarrow", compression="snappy", index=False
)
print(f"Saved household features to: {features_filename}")

# -------------------------------------------------------------
# 4. Step 3: Unsupervised K-Means Customer Segmentation
# -------------------------------------------------------------
print("Executing Step 3: Unsupervised K-Means Clustering...")

feature_cols = [
    "avg_discount_pct",
    "stockpiling_index",
    "storable_perishable_ratio",
    "shopping_trips",
]
X = df_features[feature_cols].values

scaler = StandardScaler()
X_scaled = scaler.fit_transform(X)

kmeans = KMeans(n_clusters=4, random_state=42, n_init=10)
df_features["cluster_id"] = kmeans.fit_predict(X_scaled)


def assign_archetype(cluster_id):
  mapping = {
      0: "Convenience Shoppers",
      1: "Deep-Discount Stockpilers",
      2: "Brand-Loyal Perishable Buyers",
      3: "Moderate Promotional Seekers",
  }
  return mapping.get(cluster_id, "General Shopper")


df_features["customer_archetype"] = df_features["cluster_id"].apply(
    assign_archetype
)

clusters_filename = "household_clusters.parquet"
df_clusters = df_features[
    ["cluster_id", "customer_archetype"]
].reset_index()
df_clusters.to_parquet(
    clusters_filename, engine="pyarrow", compression="snappy", index=False
)
print(f"Saved cluster mappings to: {clusters_filename}")

model_filename = "kmeans_model.pkl"
scaler_filename = "scaler_model.pkl"
joblib.dump(kmeans, model_filename)
joblib.dump(scaler, scaler_filename)
print(f"Serialized model artifacts to: {model_filename} & {scaler_filename}")

# -------------------------------------------------------------
# SUCCESSFUL COMPLETION MESSAGE
# -------------------------------------------------------------
print("\n" + "=" * 60)
print("SUCCESS: Phase 3 Behavioral Pipeline Executed Flawlessly! 🎉")
print("=" * 60)
print(f"📊 Total Households Segmented   : {len(df_features):,}")
print(f"💾 Feature Matrix Saved         : {features_filename}")
print(f"💾 Cluster Assignments Saved    : {clusters_filename}")
print(f"🤖 ML Model Artifacts Serialized: {model_filename}")
print("🚀 Your household behavioral analytics engine is fully active!")
print("=" * 60)
