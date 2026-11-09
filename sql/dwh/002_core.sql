-- Core DWH tables (cleaned / normalized)

CREATE TABLE IF NOT EXISTS core.cities_dedup (
    gc_id           integer PRIMARY KEY,
    city_id         bigint NOT NULL,
    name            varchar(255) NOT NULL,
    full_name_local varchar(255) NOT NULL,
    region          varchar(255),
    latitude        double precision,
    longitude       double precision
);

CREATE TABLE IF NOT EXISTS core.body_type_map (
    body_type_id    integer PRIMARY KEY,
    std_id          integer,
    body_group      varchar(32) NOT NULL
);

CREATE TABLE IF NOT EXISTS core.dq_quarantine_prices (
    price_id        bigint NOT NULL,
    reason_code     varchar(64) NOT NULL,
    loading_date    date,
    currency_code   varchar(3),
    price           double precision,
    distance        double precision,
    details         text,
    quarantined_at  timestamp NOT NULL DEFAULT now(),
    PRIMARY KEY (price_id, reason_code)
);

CREATE TABLE IF NOT EXISTS core.prices_clean (
    price_id            bigint PRIMARY KEY,
    created_at          timestamp,
    loading_date        date NOT NULL,
    end_loading_date    date,
    loading_city_gcid   integer NOT NULL,
    unloading_city_gcid integer NOT NULL,
    distance            double precision NOT NULL,
    total_weight        double precision NOT NULL,
    total_volume        double precision NOT NULL,
    body_type           integer,
    body_group          varchar(32) NOT NULL,
    body_group_std_id   integer,
    price               double precision NOT NULL,
    currency_code       varchar(3) NOT NULL,
    price_rub           double precision NOT NULL,
    fx_rate             double precision NOT NULL,
    nearest_rate_date   date,
    complex             boolean NOT NULL,
    price_type          smallint NOT NULL,
    is_fact             boolean NOT NULL,
    organization_id     integer,
    outlier_mark        boolean NOT NULL,
    weight_category     varchar(4) NOT NULL,
    volume_category     varchar(4) NOT NULL,
    loaded_at           timestamp NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS prices_clean_loading_date_idx
    ON core.prices_clean (loading_date);
CREATE INDEX IF NOT EXISTS prices_clean_route_idx
    ON core.prices_clean (loading_city_gcid, unloading_city_gcid, loading_date);
CREATE INDEX IF NOT EXISTS prices_clean_fact_idx
    ON core.prices_clean (is_fact, complex, outlier_mark);

CREATE TABLE IF NOT EXISTS core.etl_runs (
    run_id          bigserial PRIMARY KEY,
    start_date      date NOT NULL,
    end_date        date NOT NULL,
    rows_read       bigint NOT NULL,
    rows_quarantine bigint NOT NULL,
    rows_loaded     bigint NOT NULL,
    started_at      timestamp NOT NULL,
    finished_at     timestamp NOT NULL
);