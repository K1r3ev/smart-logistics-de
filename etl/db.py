from __future__ import annotations

from contextlib import contextmanager
from typing import Iterator

import psycopg
from psycopg.rows import dict_row

from etl.config import settings


@contextmanager
def pg_conn() -> Iterator[psycopg.Connection]:
    conn = psycopg.connect(settings.pg_dsn, row_factory=dict_row)
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def execute_sql_file(path: str) -> None:
    with open(path, encoding="utf-8") as f:
        sql = f.read()
    with pg_conn() as conn:
        conn.execute(sql)