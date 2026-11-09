from __future__ import annotations

import logging
from datetime import datetime
from typing import Any

import pandas as pd
from catboost import CatBoostRegressor

from etl.config import settings
from etl.db import pg_conn
from ml.features import FEATURE_COLS_CAT, FEATURE_COLS_NUM, load_feature_frame, time_split, xy

logger = logging.getLogger(__name__)


def _load_model() -> CatBoostRegressor:
    path = settings.models_dir / "catboost_rates.cbm"
    model = CatBoostRegressor()
    model.load_model(str(path))
    return model


def batch_score(model: CatBoostRegressor | None = None) -> dict[str, Any]:
    model = model or _load_model()
    df = load_feature_frame(include_future=True)
    _, test_df = time_split(df)
    future_df = df[df["is_future"] == True].copy()  # noqa: E712

    score_df = pd.concat([test_df, future_df], ignore_index=True)
    if score_df.empty:
        logger.warning("Nothing to score")
        return {"scored_rows": 0}

    X, _ = xy(score_df)
    preds = model.predict(X)

    rows: list[tuple] = []
    now = datetime.utcnow()
    as_of = settings.as_of
    for i, row in score_df.reset_index(drop=True).iterrows():
        pred = float(preds[i])
        is_future = bool(row["is_future"]) or row["loading_date"] > as_of
        actual = None if is_future else float(row["price_rub"])
        abs_err = None if actual is None else abs(actual - pred)
        ape = None if actual in (None, 0) else abs(actual - pred) / actual * 100.0
        rows.append(
            (
                int(row["price_id"]),
                row["loading_date"],
                int(row["loading_city_gcid"]),
                int(row["unloading_city_gcid"]),
                row["body_group"],
                actual,
                pred,
                abs_err,
                ape,
                "CatBoostRegressor",
                now,
            )
        )

    with pg_conn() as conn:
        conn.execute("TRUNCATE mart.ml_price_predictions")
        with conn.cursor() as cur:
            with cur.copy(
                """
                COPY mart.ml_price_predictions (
                    price_id, loading_date, loading_city_gcid, unloading_city_gcid,
                    body_group, actual_price_rub, predicted_price_rub,
                    abs_error_rub, ape_pct, model_name, scored_at
                ) FROM STDIN
                """
            ) as copy:
                for row in rows:
                    copy.write_row(row)

    logger.info("Batch scored %s rows into mart.ml_price_predictions", len(rows))
    return {"scored_rows": len(rows), "test_rows": len(test_df), "future_rows": len(future_df)}


def train_and_score() -> dict[str, Any]:
    from ml.train import train_models

    report = train_models()
    score_stats = batch_score()
    return {**report, "scoring": score_stats}