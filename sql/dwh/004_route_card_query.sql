-- Reference SQL: route card / market corridor (same logic as etl/marts.py)
-- Useful for manual verification after pipeline run.

SELECT month,
       loading_city,
       unloading_city,
       body_group,
       weight_category,
       round(median_trip::numeric, 2) AS median_trip,
       round(p25_trip::numeric, 2) AS p25_trip,
       round(p75_trip::numeric, 2) AS p75_trip,
       round(median_km::numeric, 2) AS median_km,
       trips_count,
       carriers_count,
       round(cv_rate::numeric, 4) AS cv_rate,
       round(mom_pct::numeric, 2) AS mom_pct,
       round(yoy_pct::numeric, 2) AS yoy_pct,
       reliability_level
FROM mart.mart_route_card
WHERE loading_city_gcid = 1001
  AND unloading_city_gcid = 1003
ORDER BY month DESC, body_group, weight_category
LIMIT 50;