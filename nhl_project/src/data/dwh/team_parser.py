import pandas as pd
import requests
from datetime import timedelta, datetime

import logging

from airflow.models import DAG
from airflow.models import Variable
from airflow.providers.postgres.hooks.postgres import PostgresHook
from airflow.operators.python import PythonOperator
from airflow.utils.dates import days_ago

from pyspark.sql import SparkSession
from pyspark.sql.window import Window
import pyspark.sql.functions as F


DEFAULT_ARGS = {
    "owner": "Galanov, Shiryeava",
    "email": "maxglnv@gmail.com",
    "email_on_failure": True,
    "email_on_retry": False,
    "retries": 3,
    "retry_delay": timedelta(seconds=15),
}

dag = DAG(
    dag_id="nhl_teams",
    schedule_interval="45 5 1 10 *",
    start_date=days_ago(2),
    catchup=False,
    tags=["hse_nhl_ml_project"],
    default_args=DEFAULT_ARGS,
    description="ETL process for getting list of NHL teams",
)


def get_information(endpoint, base_url="https://api-web.nhle.com"):
    base_url = f"{base_url}"
    endpoint = f"{endpoint}"
    full_url = f"{base_url}{endpoint}"

    response = requests.get(full_url)

    if response.status_code == 200:
        player_data = response.json()
        return player_data
    else:
        print(f"Error: Unable to fetch data. Status code: {response.status_code}")


def read_table_from_pg(spark, table_name):
    password = Variable.get("HSE_DB_PASSWORD")

    df_table = spark.read \
        .format("jdbc") \
        .option("url", "jdbc:postgresql://rc1b-diwt576i60sxiqt8.mdb.yandexcloud.net:6432/hse_db") \
        .option("driver", "org.postgresql.Driver") \
        .option("dbtable", table_name) \
        .option("user", "maxglnv") \
        .option("password", password) \
        .load()

    return df_table


def write_table_to_pg(df, spark, write_mode, table_name):
    password = Variable.get("HSE_DB_PASSWORD")
    df.cache() 
    print("Initial count:", df.count())
    print("SparkContext active:", spark.sparkContext._jsc.sc().isStopped())

    try:
        df.write \
            .mode(write_mode) \
            .format("jdbc") \
            .option("url", "jdbc:postgresql://rc1b-diwt576i60sxiqt8.mdb.yandexcloud.net:6432/hse_db") \
            .option("driver", "org.postgresql.Driver") \
            .option("dbtable", table_name) \
            .option("user", "maxglnv") \
            .option("password", password) \
            .save()
        print("Data written to PostgreSQL successfully")
    except Exception as e:
        print("Error during saving data to PostgreSQL:", e)

    print("Count after write:", df.count())
    df.unpersist()


def get_teams_to_source(**kwargs):

    logger = logging.getLogger("airflow.task")
    logger.info("Запуск задачи получения данных о командах")

    current_date = kwargs["ds"]

    spark = (
        SparkSession.builder.config(
            "spark.jars",
            "~/airflow_venv/lib/python3.10/site-packages/pyspark/jars/postgresql-42.3.1.jar",
        )
        .master("local[*]")
        .appName("parse_teams")
        .getOrCreate()
    )

    dt = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    data_teams = get_information("en/team", "https://api.nhle.com/stats/rest/")
    df_teams_pd = pd.DataFrame(data_teams["data"])

    df_teams = (
        spark.createDataFrame(df_teams_pd)
        .withColumn("_source_load_datetime", F.lit(dt))
        .withColumn("_source", F.lit("API_NHL"))
    )

    logger.info("Начинаю запись данных")


    table_name = f"dwh_source.teams_{current_date.replace('-', '_')}"
    logger.info(table_name)

    write_table_to_pg(df_teams, spark, "overwrite", table_name)
    logger.info("Запись данных в базу данных успешно завершена")

    logger.info("Начинаю запись метаданных")

    data = [("dwh_source.teams", dt)]
    df_meta = spark.createDataFrame(data, schema=["table_name", "updated_at"])

    write_table_to_pg(df_meta, spark, "append", "dwh_source.metadata_table")
    logger.info("Запись метаданных успешно завершена")


def get_penultimate_table_name(spark, table_name):

    df_meta = read_table_from_pg(spark, "dwh_source.metadata_table")
    
    sorted_df_meta = df_meta.filter(F.col("table_name") == table_name).orderBy(F.col("updated_at").desc())
    if sorted_df_meta.count() < 2:
        return None
    else:
        second_to_last_date = sorted_df_meta.select("updated_at").limit(2).orderBy(F.col("updated_at").asc()).collect()[0][0]
        return second_to_last_date


def get_teams_to_staging(**kwargs):
    current_date = kwargs["ds"]

    spark = (
        SparkSession.builder
        .config("spark.jars", "~/airflow_venv/lib/python3.10/site-packages/pyspark/jars/postgresql-42.3.1.jar")
        .master("local[*]")
        .appName("parse_teams")
        .getOrCreate()
    )

    df_new = read_table_from_pg(spark, f"dwh_source.teams_{current_date.replace('-', '_')}")
    df_new = df_new.withColumn("_source_is_deleted", F.lit("False"))

    prev_table_name = get_penultimate_table_name(spark, "dwh_source.teams")

    if prev_table_name:
        df_prev = read_table_from_pg(spark, f"dwh_source.teams_{prev_table_name[:10].replace('-', '_')}")
        df_prev = df_prev.withColumn("_source_is_deleted", F.lit("True"))

        df_deleted = df_prev.join(df_new, "id", "leftanti").withColumn(
            "_source_load_datetime", F.lit(df_new.select("_source_load_datetime").first()[0])
        )

        df_changed = df_new.select(F.col("id"), F.col("fullName"), F.col("triCode")).subtract(
            df_prev.select(F.col("id"), F.col("fullName"), F.col("triCode"))
        )
        df_changed = df_new.join(df_changed, "id", "inner").select(df_new["*"])

        df_final = df_changed.union(df_deleted).withColumn("_batch_id", F.lit(current_date))
    else:
        df_final = df_new.withColumn("_batch_id", F.lit(current_date))

    write_table_to_pg(df_final, spark, "overwrite", "dwh_staging.teams")


def get_teams_to_operational(**kwargs):
    spark = (
        SparkSession.builder
        .config("spark.jars", "~/airflow_venv/lib/python3.10/site-packages/pyspark/jars/postgresql-42.3.1.jar")
        .master("local[*]")
        .appName("parse_teams")
        .getOrCreate()
    )

    df = read_table_from_pg(spark, "dwh_staging.teams")
    df = df.select(
        F.col("id").alias("team_source_id"),
        F.col("fullName").alias("team_full_name"),
        F.col("triCode").alias("team_business_id"),
        F.col("_source_load_datetime"),
        F.col("_source_is_deleted"),
        F.col("_source"),
        F.col("_batch_id"),
    ).withColumn(
        "team_id", F.sha1(F.concat_ws("_", F.col("team_source_id"), F.col("_source")))
    )

    write_table_to_pg(df, spark, "append", "dwh_operational.teams")


def hub_teams(**kwargs):
    current_date = kwargs["ds"]

    spark = (
        SparkSession.builder
        .config("spark.jars", "~/airflow_venv/lib/python3.10/site-packages/pyspark/jars/postgresql-42.3.1.jar")
        .master("local[*]")
        .appName("parse_teams")
        .getOrCreate()
    )

    df_new = read_table_from_pg(spark, "dwh_operational.teams")
    df_new = df_new.filter(
        F.col("_batch_id") == F.lit(current_date)
    )

    windowSpec = (
        Window.partitionBy("team_id")
        .orderBy(F.col("_source_load_datetime").desc())
        .rowsBetween(Window.unboundedPreceding, Window.unboundedFollowing)
    )

    df_new = (
        df_new.withColumn(
            "_source_load_datetime", F.last("_source_load_datetime").over(windowSpec)
        )
        .withColumn("_source", F.last("_source").over(windowSpec))
        .select(
            F.col("team_id"),
            F.col("team_business_id"),
            F.col("team_source_id"),
            F.col("_source_load_datetime"),
            F.col("_source"),
        )
    )

    try:
        df_old = read_table_from_pg(spark, "dwh_detailed.hub_teams")

        df_new = df_new.join(df_old, "team_id", "leftanti")
        df_final = df_new.union(df_old).orderBy("_source_load_datetime", "team_id")
    except:
        df_final = df_new.orderBy("_source_load_datetime", "team_id")

    write_table_to_pg(df_final, spark, "overwrite", "dwh_detailed.hub_teams")


task_get_teams_to_source = PythonOperator(
    task_id="get_teams_to_source",
    python_callable=get_teams_to_source,
    dag=dag,
)

task_get_teams_to_staging = PythonOperator(
    task_id="get_teams_to_staging",
    python_callable=get_teams_to_staging,
    dag=dag,
)

task_get_teams_to_operational = PythonOperator(
    task_id="get_teams_to_operational",
    python_callable=get_teams_to_operational,
    dag=dag,
)

task_hub_teams = PythonOperator(
    task_id="hub_teams",
    python_callable=hub_teams,
    dag=dag,
)

task_get_teams_to_source >> task_get_teams_to_staging >> task_get_teams_to_operational
task_get_teams_to_operational >> task_hub_teams
