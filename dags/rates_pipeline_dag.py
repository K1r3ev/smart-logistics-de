from __future__ import annotations

import sys
from datetime import datetime, timedelta
from pathlib import Path

from airflow import DAG
from airflow.operators.python import PythonOperator

PROJECT = Path("/opt/airflow/project")
if PROJECT.exists() and str(PROJECT) not in sys.path:
    sys.path.insert(0, str(PROJECT))


def _task_etl(**_context):
    from etl.config import settings
    from etl.pipeline import run_etl

    # Full historical backfill for demo; window params still honored by ETL
    return run_etl(settings.etl_start_date, settings.etl_end_date)


def _task_marts(**_context):
    from etl.marts import build_route_card

    return build_route_card()


def _task_clickhouse(**_context):
    from etl.clickhouse_sync import sync_marts_to_clickhouse

    return sync_marts_to_clickhouse()


def _task_ml(**_context):
    from ml.score import train_and_score

    return train_and_score()


default_args = {
    "owner": "data-engineering",
    "depends_on_past": False,
    "email_on_failure": False,
    "email_on_retry": False,
    "retries": 1,
    "retry_delay": timedelta(minutes=5),
}

with DAG(
    dag_id="smart_logistics_rates_pipeline",
    description="ETL → Mart PG → ClickHouse sync → ML batch scoring",
    default_args=default_args,
    start_date=datetime(2026, 10, 1),
    schedule="@daily",
    catchup=False,
    tags=["de-interview", "rates", "ul"],
) as dag:
    etl = PythonOperator(task_id="extract_clean_load", python_callable=_task_etl)
    marts = PythonOperator(task_id="build_marts_pg", python_callable=_task_marts)
    ch = PythonOperator(task_id="sync_marts_clickhouse", python_callable=_task_clickhouse)
    ml = PythonOperator(task_id="ml_train_score", python_callable=_task_ml)

    etl >> marts >> ch >> ml