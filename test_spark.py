import os

# Force Python/PySpark to use Java 17 directly
os.environ["JAVA_HOME"] = "/usr/lib/jvm/java-17-openjdk-amd64"

from pyspark.sql import SparkSession

print("Current JAVA_HOME forced in Python:", os.environ.get("JAVA_HOME"))

spark = (
    SparkSession.builder.appName("PySpark_Sanity_Check")
    .master("local[*]")
    .getOrCreate()
)

print("Spark Session initialized successfully!")
print(f"Spark Version: {spark.version}")
spark.stop()
