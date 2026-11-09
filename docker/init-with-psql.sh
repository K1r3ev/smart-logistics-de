#!/bin/bash
set -euo pipefail

export PGPASSWORD="${POSTGRES_PASSWORD:-postgres}"
HOST="${POSTGRES_HOST:-postgres}"
PORT="${POSTGRES_PORT:-5432}"
USER="${POSTGRES_USER:-postgres}"
DB="${POSTGRES_DB:-deals_bigdata}"
N_PRICES="${N_PRICES:-100000}"

echo "[db-init] Waiting for PostgreSQL..."
until pg_isready -h "$HOST" -p "$PORT" -U "$USER"; do
  sleep 2
done

psql -h "$HOST" -p "$PORT" -U "$USER" -d postgres -tc "SELECT 1 FROM pg_database WHERE datname='${DB}'" | grep -q 1 \
  || psql -h "$HOST" -p "$PORT" -U "$USER" -d postgres -c "CREATE DATABASE ${DB}"

psql -h "$HOST" -p "$PORT" -U "$USER" -d postgres -tc "SELECT 1 FROM pg_database WHERE datname='airflow'" | grep -q 1 \
  || psql -h "$HOST" -p "$PORT" -U "$USER" -d postgres -c "CREATE DATABASE airflow"

DONE=$(psql -h "$HOST" -p "$PORT" -U "$USER" -d "$DB" -Atc \
  "SELECT to_regclass('public._pipeline_init_done') IS NOT NULL")

if [ "$DONE" = "t" ]; then
  echo "[db-init] Source already initialized, skipping schema/synthetic."
else
  echo "[db-init] Loading schema..."
  psql -h "$HOST" -p "$PORT" -U "$USER" -d "$DB" -v ON_ERROR_STOP=1 -f /sql/schema.sql
  echo "[db-init] Generating synthetic data (n_prices=${N_PRICES})..."
  psql -h "$HOST" -p "$PORT" -U "$USER" -d "$DB" -v ON_ERROR_STOP=1 -v "n_prices=${N_PRICES}" -f /sql/synthetic.sql
  psql -h "$HOST" -p "$PORT" -U "$USER" -d "$DB" -c \
    "CREATE TABLE public._pipeline_init_done (initialized_at timestamptz NOT NULL DEFAULT now());"
fi

echo "[db-init] Applying DWH DDL..."
psql -h "$HOST" -p "$PORT" -U "$USER" -d "$DB" -v ON_ERROR_STOP=1 -f /sql/dwh/001_schemas.sql
psql -h "$HOST" -p "$PORT" -U "$USER" -d "$DB" -v ON_ERROR_STOP=1 -f /sql/dwh/002_core.sql
psql -h "$HOST" -p "$PORT" -U "$USER" -d "$DB" -v ON_ERROR_STOP=1 -f /sql/dwh/003_mart.sql
echo "[db-init] Done."