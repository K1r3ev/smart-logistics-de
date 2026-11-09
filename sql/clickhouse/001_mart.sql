CREATE DATABASE IF NOT EXISTS deals_mart;

CREATE TABLE IF NOT EXISTS deals_mart.mart_route_card
(
    month               Date,
    loading_city_gcid   Int32,
    unloading_city_gcid Int32,
    loading_city        String,
    unloading_city      String,
    body_group          String,
    weight_category     String,
    p25_trip            Nullable(Float64),
    median_trip         Nullable(Float64),
    p75_trip            Nullable(Float64),
    avg_trip            Nullable(Float64),
    p25_km              Nullable(Float64),
    median_km           Nullable(Float64),
    p75_km              Nullable(Float64),
    trips_count         UInt64,
    carriers_count      UInt64,
    cv_rate             Nullable(Float64),
    mom_pct             Nullable(Float64),
    yoy_pct             Nullable(Float64),
    reliability_level   String,
    as_of               Date,
    built_at            DateTime
)
ENGINE = ReplacingMergeTree(built_at)
ORDER BY (month, loading_city_gcid, unloading_city_gcid, body_group, weight_category);

CREATE TABLE IF NOT EXISTS deals_mart.ml_price_predictions
(
    price_id            UInt64,
    loading_date        Date,
    loading_city_gcid   Int32,
    unloading_city_gcid Int32,
    body_group          String,
    actual_price_rub    Nullable(Float64),
    predicted_price_rub Float64,
    abs_error_rub       Nullable(Float64),
    ape_pct             Nullable(Float64),
    model_name          String,
    scored_at           DateTime
)
ENGINE = ReplacingMergeTree(scored_at)
ORDER BY price_id;