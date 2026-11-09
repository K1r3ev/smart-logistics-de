from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

import joblib
import numpy as np
from catboost import CatBoostRegressor
from sklearn.compose import ColumnTransformer
from sklearn.impute import SimpleImputer
from sklearn.linear_model import Ridge
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler
from sklearn.tree import DecisionTreeRegressor

from etl.config import settings
from ml.features import FEATURE_COLS_CAT, FEATURE_COLS_NUM, load_feature_frame, time_split, xy

logger = logging.getLogger(__name__)


def _mape(y_true: np.ndarray, y_pred: np.ndarray) -> float:
    mask = y_true != 0
    if not mask.any():
        return float("nan")
    return float(np.mean(np.abs((y_true[mask] - y_pred[mask]) / y_true[mask])) * 100.0)


def metrics(y_true: np.ndarray, y_pred: np.ndarray) -> dict[str, float]:
    return {
        "r2": float(r2_score(y_true, y_pred)),
        "mape_pct": _mape(y_true, y_pred),
        "rmse": float(np.sqrt(mean_squared_error(y_true, y_pred))),
        "mae": float(mean_absolute_error(y_true, y_pred)),
    }


def _sklearn_pipeline(model) -> Pipeline:
    pre = ColumnTransformer(
        transformers=[
            (
                "num",
                Pipeline(
                    steps=[
                        ("imputer", SimpleImputer(strategy="median")),
                        ("scaler", StandardScaler()),
                    ]
                ),
                FEATURE_COLS_NUM,
            ),
            (
                "cat",
                Pipeline(
                    steps=[
                        ("imputer", SimpleImputer(strategy="most_frequent")),
                        (
                            "ohe",
                            OneHotEncoder(handle_unknown="ignore", sparse_output=False),
                        ),
                    ]
                ),
                FEATURE_COLS_CAT,
            ),
        ]
    )
    return Pipeline([("pre", pre), ("model", model)])


def train_models() -> dict[str, Any]:
    settings.models_dir.mkdir(parents=True, exist_ok=True)
    df = load_feature_frame(include_future=True)
    train_df, test_df = time_split(df)
    if train_df.empty or test_df.empty:
        raise RuntimeError(
            f"Empty train/test split: train={len(train_df)}, test={len(test_df)}. "
            "Increase N_PRICES or check ETL window."
        )

    X_train, y_train = xy(train_df)
    X_test, y_test = xy(test_df)

    cat_idx = list(range(len(FEATURE_COLS_NUM), len(FEATURE_COLS_NUM) + len(FEATURE_COLS_CAT)))
    cat_model = CatBoostRegressor(
        iterations=400,
        depth=8,
        learning_rate=0.08,
        loss_function="RMSE",
        random_seed=settings.random_seed,
        verbose=False,
        allow_writing_files=False,
    )
    cat_model.fit(
        X_train,
        y_train,
        cat_features=cat_idx,
        eval_set=(X_test, y_test),
        use_best_model=True,
    )
    cat_pred = cat_model.predict(X_test)
    cat_metrics = metrics(y_test, cat_pred)

    ridge = _sklearn_pipeline(Ridge(alpha=1.0))
    ridge.fit(X_train, y_train)
    ridge_metrics = metrics(y_test, ridge.predict(X_test))

    tree = _sklearn_pipeline(
        DecisionTreeRegressor(max_depth=12, random_state=settings.random_seed)
    )
    tree.fit(X_train, y_train)
    tree_metrics = metrics(y_test, tree.predict(X_test))

    model_path = settings.models_dir / "catboost_rates.cbm"
    cat_model.save_model(str(model_path))
    joblib.dump(
        {"feature_num": FEATURE_COLS_NUM, "feature_cat": FEATURE_COLS_CAT},
        settings.models_dir / "feature_meta.joblib",
    )

    report = {
        "train_rows": int(len(train_df)),
        "test_rows": int(len(test_df)),
        "train_window": "2026-07-26 inclusive .. 2026-10-05 exclusive",
        "test_window": "2026-10-05 .. 2026-10-26 inclusive",
        "models": {
            "CatBoostRegressor": cat_metrics,
            "Ridge": ridge_metrics,
            "DecisionTreeRegressor": tree_metrics,
        },
        "primary_model": "CatBoostRegressor",
        "model_path": str(model_path),
    }
    report_path = settings.models_dir / "metrics.json"
    report_path.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    logger.info("ML metrics: %s", json.dumps(report["models"], ensure_ascii=False))
    return report


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    print(json.dumps(train_models(), indent=2, ensure_ascii=False))