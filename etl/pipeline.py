from __future__ import annotations

import logging
from datetime import date, datetime
from etl.config import settings
from etl.db import pg_conn
from etl.dq import classify_reason
from etl.transforms import map_body_group, volume_category, weight_category

logger = logging.getLogger(__name__)


REF_SQL = """
TRUNCATE core.cities_dedup;
INSERT INTO core.cities_dedup (gc_id, city_id, name, full_name_local, region, latitude, longitude)
SELECT DISTINCT ON (c.gc_id)
       c.gc_id,
       c.id,
       c.name,
       c.full_name_local,
       NULLIF(trim(split_part(c.full_name_local, ',', 2)), ''),
       c.latitude,
       c.longitude
FROM cities c
ORDER BY c.gc_id, c.id;

TRUNCATE core.body_type_map;
INSERT INTO core.body_type_map (body_type_id, std_id, body_group)
SELECT bt.id,
       COALESCE(bt.std_id, bt.id),
       CASE
         WHEN bt.id IN (56, 57, 58, 59, 60, 61) OR bt.std_id = 56 THEN 'Тент'
         WHEN bt.id IN (4, 46, 47, 48) OR bt.std_id = 4 THEN 'Рефрижератор'
         WHEN bt.id = 2 OR bt.std_id = 2 THEN 'Изотерм'
         WHEN bt.id IN (1, 15) OR bt.std_id = 15 THEN 'Борт'
         ELSE 'Прочие'
       END
FROM body_types bt;
"""


EXTRACT_SQL = """
WITH city_ids AS (
    SELECT gc_id FROM core.cities_dedup
),
primary_body AS (
    SELECT DISTINCT ON (pbt.price_id)
           pbt.price_id,
           pbt.body_type_id
    FROM price_body_types pbt
    ORDER BY pbt.price_id, pbt.body_type_id
)
SELECT p.id AS price_id,
       p.created_at,
       p.loading_date,
       p.end_loading_date,
       p.loading_city_gcid,
       p.unloading_city_gcid,
       p.distance,
       p.total_weight,
       p.total_volume,
       p.body_type,
       pb.body_type_id AS pbt_body_type_id,
       p.price,
       p.currency_code,
       p.complex,
       p.price_type,
       p.is_fact,
       p.organization_id,
       p.nearest_rate_date,
       p.outlier_mark,
       p.weight_category,
       p.volume_category,
       er.value AS fx_rate,
       (lc.gc_id IS NOT NULL) AS loading_city_ok,
       (uc.gc_id IS NOT NULL) AS unloading_city_ok
FROM prices p
LEFT JOIN primary_body pb ON pb.price_id = p.id
LEFT JOIN exchange_rates er
       ON er.num_code = p.currency_code
      AND er.setting_date = p.nearest_rate_date
LEFT JOIN city_ids lc ON lc.gc_id = p.loading_city_gcid
LEFT JOIN city_ids uc ON uc.gc_id = p.unloading_city_gcid
WHERE p.loading_date >= %(start_date)s
  AND p.loading_date <= %(end_date)s
"""


def refresh_reference_data() -> None:
    with pg_conn() as conn:
        conn.execute(REF_SQL)
    logger.info("Reference tables core.cities_dedup / core.body_type_map refreshed")


def run_etl(
    start_date: Optional[date] = None,
    end_date: Optional[date] = None,
) -> dict:
    start = start_date or settings.etl_start_date
    end = end_date or settings.etl_end_date
    started_at = datetime.utcnow()

    refresh_reference_data()

    with pg_conn() as conn:
        rows = conn.execute(
            EXTRACT_SQL,
            {"start_date": start, "end_date": end},
        ).fetchall()

    rows_read = len(rows)
    quarantine: list[tuple] = []
    clean: list[tuple] = []

    for row in rows:
        reason = classify_reason(row)
        if reason:
            quarantine.append(
                (
                    row["price_id"],
                    reason,
                    row["loading_date"],
                    row["currency_code"],
                    row["price"],
                    row["distance"],
                    None,
                )
            )
            continue

        body_raw = row["pbt_body_type_id"] if row["pbt_body_type_id"] is not None else row["body_type"]
        body_group, body_std = map_body_group(body_raw)
        fx = 1.0 if str(row["currency_code"]) == "643" else float(row["fx_rate"])
        price_rub = float(row["price"]) * fx
        w_cat = row["weight_category"] or weight_category(row["total_weight"])
        v_cat = row["volume_category"] or volume_category(row["total_volume"])

        clean.append(
            (
                row["price_id"],
                row["created_at"],
                row["loading_date"],
                row["end_loading_date"],
                row["loading_city_gcid"],
                row["unloading_city_gcid"],
                row["distance"],
                row["total_weight"],
                row["total_volume"],
                row["body_type"],
                body_group,
                body_std,
                row["price"],
                row["currency_code"],
                price_rub,
                fx,
                row["nearest_rate_date"],
                row["complex"],
                row["price_type"],
                row["is_fact"],
                row["organization_id"],
                row["outlier_mark"],
                w_cat,
                v_cat,
            )
        )

    with pg_conn() as conn:
        # Idempotent window rewrite: DELETE + COPY into staging + INSERT
        conn.execute(
            "DELETE FROM core.dq_quarantine_prices q "
            "USING prices p "
            "WHERE q.price_id = p.id "
            "  AND p.loading_date >= %s AND p.loading_date <= %s",
            (start, end),
        )
        conn.execute(
            "DELETE FROM core.prices_clean "
            "WHERE loading_date >= %s AND loading_date <= %s",
            (start, end),
        )

        if quarantine:
            with conn.cursor() as cur:
                with cur.copy(
                    """
                    COPY core.dq_quarantine_prices
                        (price_id, reason_code, loading_date, currency_code, price, distance, details)
                    FROM STDIN
                    """
                ) as copy:
                    for q in quarantine:
                        copy.write_row(q)

        if clean:
            with conn.cursor() as cur:
                with cur.copy(
                    """
                    COPY core.prices_clean (
                        price_id, created_at, loading_date, end_loading_date,
                        loading_city_gcid, unloading_city_gcid, distance,
                        total_weight, total_volume, body_type, body_group, body_group_std_id,
                        price, currency_code, price_rub, fx_rate, nearest_rate_date,
                        complex, price_type, is_fact, organization_id, outlier_mark,
                        weight_category, volume_category
                    ) FROM STDIN
                    """
                ) as copy:
                    for row in clean:
                        copy.write_row(row)

        finished_at = datetime.utcnow()
        conn.execute(
            """
            INSERT INTO core.etl_runs
                (start_date, end_date, rows_read, rows_quarantine, rows_loaded, started_at, finished_at)
            VALUES (%s, %s, %s, %s, %s, %s, %s)
            """,
            (start, end, rows_read, len(quarantine), len(clean), started_at, finished_at),
        )

    stats = {
        "start_date": start.isoformat(),
        "end_date": end.isoformat(),
        "rows_read": rows_read,
        "rows_quarantine": len(quarantine),
        "rows_loaded": len(clean),
    }
    logger.info(
        "ETL done: read=%s quarantine=%s loaded=%s window=%s..%s",
        stats["rows_read"],
        stats["rows_quarantine"],
        stats["rows_loaded"],
        stats["start_date"],
        stats["end_date"],
    )
    return stats