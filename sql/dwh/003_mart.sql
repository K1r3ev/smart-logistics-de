-- Mart layer

CREATE TABLE IF NOT EXISTS mart.mart_route_card (
    month               date NOT NULL,
    loading_city_gcid   integer NOT NULL,
    unloading_city_gcid integer NOT NULL,
    loading_city        varchar(255),
    unloading_city      varchar(255),
    body_group          varchar(32) NOT NULL,
    weight_category     varchar(4) NOT NULL,
    p25_trip            double precision,
    median_trip         double precision,
    p75_trip            double precision,
    avg_trip            double precision,
    p25_km              double precision,
    median_km           double precision,
    p75_km              double precision,
    trips_count         bigint NOT NULL,
    carriers_count      bigint NOT NULL,
    cv_rate             double precision,
    mom_pct             double precision,
    yoy_pct             double precision,
    reliability_level   varchar(16) NOT NULL,
    as_of               date NOT NULL,
    built_at            timestamp NOT NULL DEFAULT now(),
    PRIMARY KEY (month, loading_city_gcid, unloading_city_gcid, body_group, weight_category)
);

CREATE INDEX IF NOT EXISTS mart_route_card_route_idx
    ON mart.mart_route_card (loading_city_gcid, unloading_city_gcid, month);

CREATE TABLE IF NOT EXISTS mart.ml_price_predictions (
    price_id                bigint PRIMARY KEY,
    loading_date            date NOT NULL,
    loading_city_gcid       integer NOT NULL,
    unloading_city_gcid     integer NOT NULL,
    body_group              varchar(32),
    actual_price_rub        double precision,
    predicted_price_rub     double precision NOT NULL,
    abs_error_rub           double precision,
    ape_pct                 double precision,
    model_name              varchar(64) NOT NULL,
    scored_at               timestamp NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS ml_pred_loading_date_idx
    ON mart.ml_price_predictions (loading_date);