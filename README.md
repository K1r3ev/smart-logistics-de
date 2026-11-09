# Smart Logistics — Middle Data Engineer Take-Home

Сквозной прототип аналитики и прогнозирования тарифов грузоперевозок для «Умной Логистики» ([ul.su](https://ul.su)).

Исходное ТЗ: [`docs/assignment.md`](docs/assignment.md). Продуктовые материалы: [`attachments/`](attachments/).

## Архитектура

```text
PostgreSQL 17 (schema.sql + synthetic.sql)
        │
        ▼
   ETL (Python) ──► core.prices_clean + core.dq_quarantine_prices
        │
        ├──────────► mart.mart_route_card          (PostgreSQL)
        │                   │
        │                   └── sync ──► deals_mart.mart_route_card (ClickHouse)
        │
        └──────────► ML (CatBoost) ──► mart.ml_price_predictions
                                            │
                                            └── sync ──► ClickHouse

Airflow DAG: extract_clean_load → build_marts_pg → sync_marts_clickhouse → ml_train_score
```

| Слой | Стек | Назначение |
| --- | --- | --- |
| Source / Core / Mart | PostgreSQL 17 | Операционка, очистка, витрины, ML-результаты |
| Analytics ★ | ClickHouse `ReplacingMergeTree` | OLAP-копия витрин |
| Orchestration ★ | Apache Airflow 2.9 | Ежедневный DAG поверх того же Python-кода |
| ETL / ML | Python 3.11, pandas, CatBoost, scikit-learn | DQ, идемпотентная загрузка, time-split, batch scoring |

Дата снимка: **`AS_OF=2026-10-26`**.

## Быстрый старт

```bash
cp .env.example .env
docker compose up --build
```

1. Postgres 17 + синтетический источник (`N_PRICES`, по умолчанию `50000`; в ТЗ — `300000`).
2. `db-init` загружает schema/synthetic и DDL core/mart.
3. `pipeline` прогоняет ETL → mart → ML → синк в ClickHouse.
4. Airflow UI: http://localhost:8080 (`admin` / `admin`), DAG `smart_logistics_rates_pipeline`.

Повторный прогон:

```bash
docker compose exec pipeline python -m scripts.run_pipeline
```

Тесты:

```bash
pip install -r requirements.txt
pytest -q
```

## Этап 1. ETL & Data Quality

Код: [`etl/pipeline.py`](etl/pipeline.py).

- DQ: `price <= 0`, для RUB также `price <= 1000`, `distance <= 0`, отрицательные вес/объём, неизвестный город, валюта без курса по `nearest_rate_date`.
- Карантин: `core.dq_quarantine_prices` + `reason_code`.
- Валюта → `price_rub` только по `nearest_rate_date` (без fallback на `loading_date`).
- Дозаполнение `weight_category` / `volume_category`.
- `outlier_mark` — входной флаг, в базовом решении не пересчитывается.
- Идемпотентность: `DELETE` окна дат + `COPY` в `core.prices_clean`.

Краевой случай источника: сделки за `2026-10-26` ещё без ночной разметки аномалий (`outlier_mark = false`).

## Этап 2. Mart Layer

Код: [`etl/marts.py`](etl/marts.py), DDL: [`sql/dwh/`](sql/dwh/).

- Дедуп городов: `DISTINCT ON (gc_id) ORDER BY id`.
- Группы кузова через `price_body_types` (Тент / Реф / Изотерм / Борт / Прочие / Не указан).
- Витрина `mart.mart_route_card`: месяц × города × `body_group` × `weight_category`.
- Метрики: P25/P50/P75/AVG (рейс и км), `trips_count`, `carriers_count`, `cv_rate`, `mom_pct`, `yoy_pct`, `reliability_level`.

Пример проверки: [`sql/dwh/004_route_card_query.sql`](sql/dwh/004_route_card_query.sql).

```sql
SELECT month, loading_city, unloading_city, body_group, weight_category,
       median_trip, p25_trip, p75_trip, median_km,
       trips_count, carriers_count, reliability_level
FROM mart.mart_route_card
ORDER BY trips_count DESC
LIMIT 20;
```

## Этап 3. ML Feature Engineering & Batch Scoring

Код: [`ml/`](ml/).

- Признаки: distance, вес/объём, lat/lon, регионы, body/weight/volume categories, sin/cos даты + year.
- Без leakage: `price_with_vat`, `price/distance`, `price_group_stats`, `outlier_mark` как feature.
- Time split: train `[2026-07-26, 2026-10-05)`, test `[2026-10-05, 2026-10-26]`.
- Primary model: CatBoostRegressor; сравнение с Ridge / DecisionTree в `data/models/metrics.json`.
- Batch scoring → `mart.ml_price_predictions` (`actual_* = NULL` для `loading_date > as_of`).

Пример метрик (`N_PRICES=50000`):

| Model | R² | MAPE % | RMSE | MAE |
| --- | ---: | ---: | ---: | ---: |
| CatBoostRegressor | 0.921 | 16.5 | 53314 | 28856 |

Витрины: `mart.mart_route_card` ≈ 43808 строк, `mart.ml_price_predictions` ≈ 3066; зеркало в ClickHouse.

## Бонусы

### ClickHouse

- DDL: [`sql/clickhouse/001_mart.sql`](sql/clickhouse/001_mart.sql)
- Синк: [`etl/clickhouse_sync.py`](etl/clickhouse_sync.py)

```bash
curl 'http://localhost:8123/?query=SELECT%20count()%20FROM%20deals_mart.mart_route_card'
```

### Apache Airflow

- DAG: [`dags/rates_pipeline_dag.py`](dags/rates_pipeline_dag.py)
- UI: http://localhost:8080
- Бизнес-логика не дублируется: DAG вызывает те же модули, что и `pipeline`.

## Структура

```text
etl/              # DQ, ETL, marts, ClickHouse sync
ml/               # features, train, batch score
sql/              # source DDL, synthetic, dwh, clickhouse
dags/             # Airflow DAG
scripts/          # entrypoint + run_pipeline
docker/           # init scripts, Airflow Dockerfile, CH users
tests/            # pytest
docs/             # original assignment
attachments/      # product / ML briefs + demo HTML
```

## Переменные окружения

См. [`.env.example`](.env.example).

| Variable | Default | Meaning |
| --- | --- | --- |
| `AS_OF` | `2026-10-26` | Snapshot date |
| `N_PRICES` | `50000` | Synthetic rows (`300000` — полный объём из ТЗ) |
| `ETL_START_DATE` / `ETL_END_DATE` | `2023-06-01` / `2027-03-31` | Окно ETL (end > as_of, чтобы захватить плановые погрузки) |
