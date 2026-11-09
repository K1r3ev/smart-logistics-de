from __future__ import annotations

import logging
from datetime import date
from typing import Optional

from etl.config import settings
from etl.db import pg_conn

logger = logging.getLogger(__name__)

BUILD_ROUTE_CARD_SQL = """
WITH body_expanded AS (
    SELECT p.price_id,
           p.loading_date,
           p.loading_city_gcid,
           p.unloading_city_gcid,
           p.distance,
           p.price_rub,
           p.price_type,
           p.organization_id,
           p.weight_category,
           p.outlier_mark,
           p.is_fact,
           p.complex,
           COALESCE(bg.body_group, p.body_group) AS body_group
    FROM core.prices_clean p
    LEFT JOIN LATERAL (
        SELECT DISTINCT
               CASE
                 WHEN pbt.body_type_id IN (56, 57, 58, 59, 60, 61) THEN 'Тент'
                 WHEN pbt.body_type_id IN (4, 46, 47, 48) THEN 'Рефрижератор'
                 WHEN pbt.body_type_id = 2 THEN 'Изотерм'
                 WHEN pbt.body_type_id IN (1, 15) THEN 'Борт'
                 ELSE 'Прочие'
               END AS body_group
        FROM price_body_types pbt
        WHERE pbt.price_id = p.price_id
    ) bg ON TRUE
),
base AS (
    SELECT be.price_id,
           be.loading_city_gcid,
           be.unloading_city_gcid,
           be.distance,
           be.price_rub,
           be.price_type,
           be.organization_id,
           be.weight_category,
           be.body_group,
           date_trunc('month', pd.price_date)::date AS month
    FROM body_expanded be
    JOIN price_dates pd ON pd.price_id = be.price_id
    WHERE be.is_fact = TRUE
      AND be.complex = FALSE
      AND be.outlier_mark = FALSE
      AND be.price_rub > 0
      AND be.distance > 0
      AND pd.price_date <= %(as_of)s
),
agg AS (
    SELECT
        b.month,
        b.loading_city_gcid,
        b.unloading_city_gcid,
        b.body_group,
        b.weight_category,
        percentile_cont(0.25) WITHIN GROUP (ORDER BY b.price_rub) AS p25_trip,
        percentile_cont(0.50) WITHIN GROUP (ORDER BY b.price_rub) AS median_trip,
        percentile_cont(0.75) WITHIN GROUP (ORDER BY b.price_rub) AS p75_trip,
        avg(b.price_rub) AS avg_trip,
        percentile_cont(0.25) WITHIN GROUP (ORDER BY b.price_rub / NULLIF(b.distance, 0)) AS p25_km,
        percentile_cont(0.50) WITHIN GROUP (ORDER BY b.price_rub / NULLIF(b.distance, 0)) AS median_km,
        percentile_cont(0.75) WITHIN GROUP (ORDER BY b.price_rub / NULLIF(b.distance, 0)) AS p75_km,
        count(DISTINCT b.price_id) AS trips_count,
        count(DISTINCT b.organization_id) FILTER (WHERE b.price_type IN (3, 9)) AS carriers_count,
        CASE
          WHEN count(*) < 2 OR avg(b.price_rub) = 0 THEN NULL
          ELSE stddev_samp(b.price_rub) / NULLIF(avg(b.price_rub), 0)
        END AS cv_rate
    FROM base b
    GROUP BY 1, 2, 3, 4, 5
),
with_names AS (
    SELECT a.*,
           lc.name AS loading_city,
           uc.name AS unloading_city
    FROM agg a
    LEFT JOIN core.cities_dedup lc ON lc.gc_id = a.loading_city_gcid
    LEFT JOIN core.cities_dedup uc ON uc.gc_id = a.unloading_city_gcid
),
with_dynamics AS (
    SELECT w.*,
           CASE
             WHEN prev.median_trip IS NULL OR prev.median_trip = 0 THEN NULL
             ELSE (w.median_trip - prev.median_trip) / prev.median_trip * 100.0
           END AS mom_pct,
           CASE
             WHEN yoy.median_trip IS NULL OR yoy.median_trip = 0 THEN NULL
             ELSE (w.median_trip - yoy.median_trip) / yoy.median_trip * 100.0
           END AS yoy_pct,
           CASE
             WHEN w.trips_count >= 30
              AND w.carriers_count >= 5
              AND w.month >= date_trunc('month', %(as_of)s::date - INTERVAL '30 days')::date
             THEN 'HIGH'
             WHEN w.trips_count >= 10 THEN 'MEDIUM'
             ELSE 'LOW_DATA'
           END AS reliability_level
    FROM with_names w
    LEFT JOIN with_names prev
      ON prev.loading_city_gcid = w.loading_city_gcid
     AND prev.unloading_city_gcid = w.unloading_city_gcid
     AND prev.body_group = w.body_group
     AND prev.weight_category = w.weight_category
     AND prev.month = (w.month - INTERVAL '1 month')::date
    LEFT JOIN with_names yoy
      ON yoy.loading_city_gcid = w.loading_city_gcid
     AND yoy.unloading_city_gcid = w.unloading_city_gcid
     AND yoy.body_group = w.body_group
     AND yoy.weight_category = w.weight_category
     AND yoy.month = (w.month - INTERVAL '1 year')::date
)
INSERT INTO mart.mart_route_card (
    month, loading_city_gcid, unloading_city_gcid, loading_city, unloading_city,
    body_group, weight_category,
    p25_trip, median_trip, p75_trip, avg_trip,
    p25_km, median_km, p75_km,
    trips_count, carriers_count, cv_rate, mom_pct, yoy_pct,
    reliability_level, as_of, built_at
)
SELECT month, loading_city_gcid, unloading_city_gcid, loading_city, unloading_city,
       body_group, weight_category,
       p25_trip, median_trip, p75_trip, avg_trip,
       p25_km, median_km, p75_km,
       trips_count, carriers_count, cv_rate, mom_pct, yoy_pct,
       reliability_level, %(as_of)s::date, now()
FROM with_dynamics;
"""


def build_route_card(as_of: Optional[date] = None) -> dict:
    as_of = as_of or settings.as_of
    with pg_conn() as conn:
        conn.execute("TRUNCATE mart.mart_route_card")
        conn.execute(BUILD_ROUTE_CARD_SQL, {"as_of": as_of})
        row = conn.execute("SELECT count(*) AS cnt FROM mart.mart_route_card").fetchone()
    count = int(row["cnt"])
    logger.info("Built mart.mart_route_card: %s rows (as_of=%s)", count, as_of)
    return {"rows": count, "as_of": as_of.isoformat()}