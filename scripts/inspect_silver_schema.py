from pyspark.sql import SparkSession

path = (
    "/workspace/data/silver/orr/station_usage/"
    "release=2024_25"
)

spark = (
    SparkSession.builder
    .master("local[*]")
    .appName("RailFlowSilverSchemaProbe")
    .config("spark.ui.enabled", "false")
    .getOrCreate()
)

spark.sparkContext.setLogLevel("ERROR")

df = spark.read.parquet(path)

print("=" * 72)
print("ACTUAL SILVER SCHEMA")
print("=" * 72)

df.printSchema()

print()
print("ROWS:", df.count())
print("COLUMNS:", len(df.columns))

print()
print("COLUMN TYPES")

for name, dtype in df.dtypes:
    print(f"{name:<60} {dtype}")

spark.stop()
