from __future__ import annotations

from datetime import date

import pandas as pd

from etl.config import settings
from etl.transforms import cyclical, parse_region

FEATURE_COLS_NUM = [
    "distance",
    "total_weight",
    "total_volume",
    "origin_lat",
    "origin_lon",
    "dest_lat",
    "dest_lon",
    "year",
    "month_sin",
    "month_cos",
    "dow_sin",
    "dow_cos",
    "doy_sin",
    "doy_cos",
]

FEATURE_COLS_CAT = [
    "origin_region",
    "destination_region",
    "body_group",
    "weight_category",
    "volume_category",
]

LEAKAGE_COLS = {
    "price",
    "price_rub",
    "price_with_vat",
    "price_km",
    "price_per_ton",
    "fx_rate",
    "outlier_mark",
    "price_group_id",
    "avg_price",
    "min_km_price",
    "max_km_price",
}


LOAD_SQL = """
SELECT p.price_id,
       p.loading_date,
       p.loading_city_gcid,
       p.unloading_city_gcid,
       p.distance,
       p.total_weight,
       p.total_volume,
       p.body_group,
       p.weight_category,
       p.volume_category,
       p.price_rub,
       p.is_fact,
       p.complex,
       p.outlier_mark,
       oc.full_name_local AS origin_full,
       oc.latitude AS origin_lat,
       oc.longitude AS origin_lon,
       dc.full_name_local AS dest_full,
       dc.latitude AS dest_lat,
       dc.longitude AS dest_lon
FROM core.prices_clean p
LEFT JOIN core.cities_dedup oc ON oc.gc_id = p.loading_city_gcid
LEFT JOIN core.cities_dedup dc ON dc.gc_id = p.unloading_city_gcid
WHERE p.complex = FALSE
  AND p.distance > 0
  AND p.price_rub > 0
"""


def load_feature_frame(include_future: bool = True) -> pd.DataFrame:
    from etl.db import pg_conn

    with pg_conn() as conn:
        rows = conn.execute(LOAD_SQL).fetchall()
    df = pd.DataFrame(rows)
    if df.empty:
        return df

    df["loading_date"] = pd.to_datetime(df["loading_date"]).dt.date
    as_of = settings.as_of

    hist = df[(df["is_fact"] == True) & (df["outlier_mark"] == False) & (df["loading_date"] <= as_of)].copy()  # noqa: E712
    if include_future:
        future = df[df["loading_date"] > as_of].copy()
        future["is_future"] = True
        hist["is_future"] = False
        out = pd.concat([hist, future], ignore_index=True)
    else:
        hist["is_future"] = False
        out = hist

    out["origin_region"] = out["origin_full"].map(parse_region)
    out["destination_region"] = out["dest_full"].map(parse_region)

    years, month_sin, month_cos, dow_sin, dow_cos, doy_sin, doy_cos = [], [], [], [], [], [], []
    for d in out["loading_date"]:
        d = date.fromisoformat(str(d)) if not isinstance(d, date) else d
        years.append(d.year)
        ms, mc = cyclical(d.month, 12)
        month_sin.append(ms)
        month_cos.append(mc)
        ds, dc = cyclical(d.weekday(), 7)
        dow_sin.append(ds)
        dow_cos.append(dc)
        doy = d.timetuple().tm_yday
        ys, yc = cyclical(doy, 365.25)
        doy_sin.append(ys)
        doy_cos.append(yc)

    out["year"] = years
    out["month_sin"] = month_sin
    out["month_cos"] = month_cos
    out["dow_sin"] = dow_sin
    out["dow_cos"] = dow_cos
    out["doy_sin"] = doy_sin
    out["doy_cos"] = doy_cos

    for col in FEATURE_COLS_NUM:
        out[col] = pd.to_numeric(out[col], errors="coerce")
    for col in FEATURE_COLS_CAT:
        out[col] = out[col].fillna("UNKNOWN").astype(str)

    assert not (LEAKAGE_COLS & set(FEATURE_COLS_NUM + FEATURE_COLS_CAT))
    return out


def time_split(df: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    as_of = settings.as_of
    train_start = date(2026, 7, 26)
    test_start = date(2026, 10, 5)

    hist = df[df["is_future"] == False].copy()  # noqa: E712
    train = hist[(hist["loading_date"] >= train_start) & (hist["loading_date"] < test_start)]
    test = hist[(hist["loading_date"] >= test_start) & (hist["loading_date"] <= as_of)]
    return train, test


def xy(df: pd.DataFrame):
    X = df[FEATURE_COLS_NUM + FEATURE_COLS_CAT].copy()
    y = df["price_rub"].astype(float).values
    return X, y