from __future__ import annotations

import logging
from datetime import datetime
from typing import Any

import clickhouse_connect

from etl.config import ROOT, settings
from etl.db import pg_conn

logger = logging.getLogger(__name__)


def _ch_client():
    return clickhouse_connect.get_client(
        host=settings.clickhouse_host,
        port=settings.clickhouse_port,
        username=settings.clickhouse_user,
        password=settings.clickhouse_password or "",
        database=settings.clickhouse_db,
    )


def ensure_clickhouse_schema() -> None:
    client = clickhouse_connect.get_client(
        host=settings.clickhouse_host,
        port=settings.clickhouse_port,
        username=settings.clickhouse_user,
        password=settings.clickhouse_password or "",
    )
    ddl_path = ROOT / "sql" / "clickhouse" / "001_mart.sql"
    sql = ddl_path.read_text(encoding="utf-8")
    for stmt in sql.split(";"):
        stmt = stmt.strip()
        if stmt:
            client.command(stmt)
    logger.info("ClickHouse schema ensured")


def _to_ch_row_route(r: dict[str, Any]) -> list[Any]:
    return [
        r["month"],
        int(r["loading_city_gcid"]),
        int(r["unloading_city_gcid"]),
        r["loading_city"] or "",
        r["unloading_city"] or "",
        r["body_group"],
        r["weight_category"],
        r["p25_trip"],
        r["median_trip"],
        r["p75_trip"],
        r["avg_trip"],
        r["p25_km"],
        r["median_km"],
        r["p75_km"],
        int(r["trips_count"]),
        int(r["carriers_count"]),
        r["cv_rate"],
        r["mom_pct"],
        r["yoy_pct"],
        r["reliability_level"],
        r["as_of"],
        r["built_at"] or datetime.utcnow(),
    ]


def _to_ch_row_pred(r: dict[str, Any]) -> list[Any]:
    return [
        int(r["price_id"]),
        r["loading_date"],
        int(r["loading_city_gcid"]),
        int(r["unloading_city_gcid"]),
        r["body_group"] or "",
        r["actual_price_rub"],
        float(r["predicted_price_rub"]),
        r["abs_error_rub"],
        r["ape_pct"],
        r["model_name"],
        r["scored_at"] or datetime.utcnow(),
    ]


def sync_marts_to_clickhouse() -> dict:
    ensure_clickhouse_schema()
    client = _ch_client()

    with pg_conn() as conn:
        routes = conn.execute("SELECT * FROM mart.mart_route_card").fetchall()
        preds = conn.execute("SELECT * FROM mart.ml_price_predictions").fetchall()

    client.command("TRUNCATE TABLE IF EXISTS deals_mart.mart_route_card")
    client.command("TRUNCATE TABLE IF EXISTS deals_mart.ml_price_predictions")

    if routes:
        client.insert(
            "mart_route_card",
            [_to_ch_row_route(dict(r)) for r in routes],
            column_names=[
                "month",
                "loading_city_gcid",
                "unloading_city_gcid",
                "loading_city",
                "unloading_city",
                "body_group",
                "weight_category",
                "p25_trip",
                "median_trip",
                "p75_trip",
                "avg_trip",
                "p25_km",
                "median_km",
                "p75_km",
                "trips_count",
                "carriers_count",
                "cv_rate",
                "mom_pct",
                "yoy_pct",
                "reliability_level",
                "as_of",
                "built_at",
            ],
        )

    if preds:
        client.insert(
            "ml_price_predictions",
            [_to_ch_row_pred(dict(r)) for r in preds],
            column_names=[
                "price_id",
                "loading_date",
                "loading_city_gcid",
                "unloading_city_gcid",
                "body_group",
                "actual_price_rub",
                "predicted_price_rub",
                "abs_error_rub",
                "ape_pct",
                "model_name",
                "scored_at",
            ],
        )

    stats = {"route_card_rows": len(routes), "prediction_rows": len(preds)}
    logger.info("ClickHouse sync done: %s", stats)
    return stats