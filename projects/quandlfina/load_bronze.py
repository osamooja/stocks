# Databricks notebook source
import quandl as qu
import pandas as pd
import time
from pyspark.sql.functions import col
import common.etl as etl
from datetime import datetime, timedelta
from pyspark.sql import SparkSession

# Function to fetch data from Quandl
def fetch_quandl_data(database_code, dataset_code):
    try:
        data = qu.get(f"{database_code}/{dataset_code}", paginate = True)
        return data
    except qu.errors.quandl_error.LimitExceededError:
        print(f"Loading {dataset_code} to {database_code} failed with error: API speed limit exceeded. Waiting 10mins")
        time.sleep(600)
    return fetch_quandl_data(database_code, dataset_code)

# COMMAND ----------

# Load integration configurations
configs = etl.get_integration_configs(spark, "quandlfina")
api_key = configs.select("api_key").first().api_key
source_database = configs.select("source_database").first().source_database
target_schema = configs.select("target_schema").first().target_schema

# Create schema if it does not exist
etl.create_schema_if_not_exists(spark, target_schema)

exceptions = []
for row in configs.collect():
    source_table = row["source_table"]
    target_table = row["target_table"]
    pk_list = row["pk_list"]

    try:
        # Fetch data
        quandl_data = fetch_quandl_data(source_database, source_table)

        if quandl_data.empty:
            print(f"No data found for: {source_table}. Skipping.")
            continue

        # Convert Yahoo Finance data to Spark DataFrame
        df = spark.createDataFrame(quandl_data.reset_index())
        df = etl.clean_column_names(df)
        df = etl.add_necessary_fields(df, pk_list, source_table)

        # Write DataFrame to Delta table
        etl.write_to_table(df, f"{target_schema}.{target_table}")
        print(f"Load complete on: {target_table}")
    except Exception as e:
        error_message = str(e)
        print(f"Loading {source_table} to {target_table} failed with error: {error_message}")
        print("Continuing loading remaining tables.")
        exceptions.append(e)

# if exceptions:
#     raise Exception(f"One or more loads failed: {exceptions}")
