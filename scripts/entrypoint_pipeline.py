from __future__ import annotations

import logging
import os
import subprocess
import sys
import time
import urllib.request

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger("entrypoint")


def wait_clickhouse(retries: int = 90) -> None:
    host = os.getenv("CLICKHOUSE_HOST", "clickhouse")
    port = os.getenv("CLICKHOUSE_PORT", "8123")
    url = f"http://{host}:{port}/ping"
    for i in range(retries):
        try:
            with urllib.request.urlopen(url, timeout=3) as resp:
                if resp.status == 200:
                    logger.info("ClickHouse is up")
                    return
        except Exception as exc:  # noqa: BLE001
            logger.info("Waiting for ClickHouse (%s/%s): %s", i + 1, retries, exc)
            time.sleep(2)
    raise RuntimeError("ClickHouse did not become ready")


def main() -> int:
    wait_clickhouse()
    logger.info("Running end-to-end pipeline (ETL → Mart → ML → ClickHouse)...")
    subprocess.check_call([sys.executable, "-m", "scripts.run_pipeline"])
    logger.info("Pipeline complete. Container stays up for inspection.")
    while True:
        time.sleep(3600)


if __name__ == "__main__":
    raise SystemExit(main())