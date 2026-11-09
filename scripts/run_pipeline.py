from __future__ import annotations

import argparse
import json
import logging
import sys
from datetime import date
from pathlib import Path

# Ensure project root on path when launched as script
ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from etl.clickhouse_sync import sync_marts_to_clickhouse
from etl.config import settings
from etl.marts import build_route_card
from etl.pipeline import run_etl
from ml.score import train_and_score

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s [%(name)s] %(message)s",
)
logger = logging.getLogger("run_pipeline")


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Smart Logistics DE pipeline")
    p.add_argument("--start-date", type=date.fromisoformat, default=settings.etl_start_date)
    p.add_argument("--end-date", type=date.fromisoformat, default=settings.etl_end_date)
    p.add_argument("--skip-ml", action="store_true")
    p.add_argument("--skip-clickhouse", action="store_true")
    return p.parse_args()


def main() -> int:
    args = parse_args()
    logger.info("Starting pipeline as_of=%s window=%s..%s", settings.as_of, args.start_date, args.end_date)

    etl_stats = run_etl(args.start_date, args.end_date)
    mart_stats = build_route_card(settings.as_of)

    ml_stats = {}
    if not args.skip_ml:
        ml_stats = train_and_score()

    ch_stats = {}
    if not args.skip_clickhouse:
        try:
            ch_stats = sync_marts_to_clickhouse()
        except Exception as exc:  # noqa: BLE001
            logger.exception("ClickHouse sync failed: %s", exc)
            ch_stats = {"error": str(exc)}

    summary = {
        "etl": etl_stats,
        "mart": mart_stats,
        "ml": {
            "primary": ml_stats.get("models", {}).get("CatBoostRegressor"),
            "scoring": ml_stats.get("scoring"),
            "train_rows": ml_stats.get("train_rows"),
            "test_rows": ml_stats.get("test_rows"),
        }
        if ml_stats
        else {},
        "clickhouse": ch_stats,
    }
    out = settings.models_dir / "pipeline_summary.json"
    settings.models_dir.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(summary, indent=2, ensure_ascii=False, default=str), encoding="utf-8")
    logger.info("Pipeline summary written to %s", out)
    print(json.dumps(summary, indent=2, ensure_ascii=False, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())