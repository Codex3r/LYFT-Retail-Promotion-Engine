import pandas as pd

# Load the parquet file
df = pd.read_parquet("curated_dunnhumby_transactions.parquet")

print("========================================")
print("     CURATED DATASET INSPECTION         ")
print("========================================")
print(f"Total Rows & Columns : {df.shape}")
print("\nColumn Names & Data Types:")
print(df.dtypes)
print("\nFirst 3 Rows Preview:")
print(df.head(3))
print("========================================")
