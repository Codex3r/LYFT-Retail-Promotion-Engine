import os
import sys
import gc
from pyspark.sql import SparkSession
from pyspark.sql import functions as F
from pyspark.sql.window import Window

LOCAL_MART_PATH = "sku_timeline_mart.parquet"
LOCAL_SOURCE = os.path.abspath("curated_dunnhumby_transactions.parquet")

def run_pipeline():
    print("==================================================")
    print("--> RUNNING SPARK WINDOWING ENGINE FOR 2,500 SKUS")
    print("==================================================")

    spark = SparkSession.builder \
        .appName("Retail_Analytics_2500_Engine") \
        .master("local[*]") \
        .config("spark.driver.memory", "6g") \
        .config("spark.executor.memory", "4g") \
        .config("spark.sql.shuffle.partitions", "16") \
        .config("spark.hadoop.fs.defaultFS", "file:///") \
        .getOrCreate()
        
    spark.sparkContext.setLogLevel("ERROR")

    source_uri = f"file://{LOCAL_SOURCE}"
    print(f"--> Reading source transactions: {source_uri}")

    if not os.path.exists(LOCAL_SOURCE):
        print(f"ERROR: Local source file not found at {LOCAL_SOURCE}")
        spark.stop()
        sys.exit(1)

    df_raw = spark.read.parquet(source_uri)

    # Cast existing columns cleanly
    df_clean = df_raw.withColumn("PRODUCT_ID", F.col("PRODUCT_ID").cast("long")) \
                     .withColumn("DAY", F.col("DAY").cast("int")) \
                     .withColumn("QUANTITY", F.col("QUANTITY").cast("double")) \
                     .withColumn("SALES_VALUE", F.col("SALES_VALUE").cast("double")) \
                     .withColumn("total_discount", F.abs(F.col("total_discount")).cast("double"))

    # Ensure commodity_cohort exists
    if "commodity_cohort" not in df_clean.columns:
        df_clean = df_clean.withColumn(
            "commodity_cohort",
            F.when(F.col("COMMODITY_DESC").isin("PAPER TOWELS", "FACIAL TISSUE", "LAUNDRY DETERGENTS", "DIAPERS"), "STORABLE")
             .when(F.col("COMMODITY_DESC").isin("SOFT DRINKS", "SNACKS/CANDY", "COOKIES", "BAG SNACKS"), "EXPANDABLE")
             .otherwise("PERISHABLE")
        )

    print("--> Aggregating daily SKU volumes...")
    daily_sku = df_clean.groupBy("PRODUCT_ID", "DAY", "COMMODITY_DESC", "commodity_cohort") \
        .agg(
            F.sum("QUANTITY").alias("daily_units"),
            F.sum("SALES_VALUE").alias("daily_revenue"),
            F.sum("total_discount").alias("daily_discount_val")
        ) \
        .withColumn("shelf_price", (F.col("daily_revenue") + F.col("daily_discount_val")) / F.col("daily_units")) \
        .withColumn("discount_depth", F.when(F.col("shelf_price") > 0, F.col("daily_discount_val") / (F.col("daily_revenue") + F.col("daily_discount_val"))).otherwise(0.0)) \
        .withColumn("is_promo", F.when(F.col("discount_depth") >= 0.20, 1).otherwise(0))

    # Identify and select top 2,500 active SKUs
    print("--> Selecting top 2,500 active SKUs by volume...")
    top_2500_skus = [
        row.PRODUCT_ID for row in daily_sku.groupBy("PRODUCT_ID")
        .agg(F.sum("daily_units").alias("tot_u"))
        .filter(F.col("tot_u") >= 30)
        .orderBy(F.desc("tot_u"))
        .limit(2500)
        .collect()
    ]
    print(f"--> Extracted target catalog: {len(top_2500_skus)} active SKUs.")

    # 28-day baseline and 21-day forward-looking windowing
    print("--> Computing distributed 28d baseline and 21d forward troughs...")
    window_baseline_28 = Window.partitionBy("PRODUCT_ID").orderBy("DAY").rowsBetween(-28, -1)
    window_trough_21 = Window.partitionBy("PRODUCT_ID").orderBy("DAY").rowsBetween(1, 21)

    timeline_df = daily_sku.filter(F.col("PRODUCT_ID").isin(top_2500_skus)) \
        .withColumn("baseline_28d", F.avg("daily_units").over(window_baseline_28)) \
        .withColumn("trough_21d", F.avg(
            F.when(F.col("is_promo") == 0, F.col("daily_units")).otherwise(None)
        ).over(window_trough_21)) \
        .fillna({"baseline_28d": 0.0, "trough_21d": 0.0})

    # Memory-safe local export
    print(f"--> Writing to {LOCAL_MART_PATH}...")
    temp_dir = os.path.abspath("temp_spark_export_dir")
    timeline_df.repartition(4).write.mode("overwrite").parquet(f"file://{temp_dir}")

    import pyarrow.dataset as ds
    import pyarrow.parquet as pq
    import shutil

    dataset = ds.dataset(temp_dir, format="parquet")
    table = dataset.to_table()
    pq.write_table(table, LOCAL_MART_PATH, compression="snappy")
    shutil.rmtree(temp_dir, ignore_errors=True)

    spark.stop()
    gc.collect()
    print(f"SUCCESS: Materialized {LOCAL_MART_PATH} with exactly {len(top_2500_skus)} SKUs.")

if __name__ == "__main__":
    run_pipeline()
