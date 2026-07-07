# -*- coding: utf-8 -*-
"""US-021: PostgreSQL 전환 — URL 정규화 + 모델 호환성 검증."""
import os

import pytest
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.dialects import postgresql
from sqlalchemy.schema import CreateTable

from config import _normalize_db_url
from models import db

EXPECTED_TABLES = {
    "users", "products", "reviews", "counsel_logs", "saju_readings", "payments",
}


# ---- DATABASE_URL 정규화 ------------------------------------------------

def test_postgres_prefix_is_normalized():
    url = _normalize_db_url("postgres://u:p@host.neon.tech/db?sslmode=require")
    assert url == "postgresql://u:p@host.neon.tech/db?sslmode=require"


def test_postgresql_url_passes_through():
    url = "postgresql://u:p@host.neon.tech/db?sslmode=require"
    assert _normalize_db_url(url) == url


def test_sqlite_url_passes_through():
    assert _normalize_db_url("sqlite:///saju.db") == "sqlite:///saju.db"


# ---- 모델 스키마가 PostgreSQL 방언으로 컴파일되는지 ----------------------

def test_all_models_compile_on_postgresql_dialect():
    dialect = postgresql.dialect()
    tables = {t.name for t in db.metadata.sorted_tables}
    assert tables == EXPECTED_TABLES
    for table in db.metadata.sorted_tables:
        ddl = str(CreateTable(table).compile(dialect=dialect))
        assert f"CREATE TABLE {table.name}" in ddl


# ---- 실 Postgres 라운드트립 (TEST_DATABASE_URL 있을 때만) -----------------

@pytest.mark.skipif(
    not os.environ.get("TEST_DATABASE_URL"),
    reason="TEST_DATABASE_URL 미설정 — 실 Postgres 검증은 선택 실행",
)
def test_live_postgres_create_all_and_crud_roundtrip():
    """실제 Postgres에 create_all 후 User 삽입/조회/삭제 라운드트립."""
    url = _normalize_db_url(os.environ["TEST_DATABASE_URL"])
    engine = create_engine(url)
    try:
        db.metadata.create_all(engine)
        assert EXPECTED_TABLES <= set(inspect(engine).get_table_names())

        email = "us021-roundtrip@test.local"
        with engine.begin() as conn:
            conn.execute(text("DELETE FROM users WHERE email = :e"), {"e": email})
            conn.execute(
                text("INSERT INTO users (email, password_hash) VALUES (:e, :p)"),
                {"e": email, "p": "x"},
            )
            row = conn.execute(
                text("SELECT email FROM users WHERE email = :e"), {"e": email}
            ).fetchone()
            assert row is not None and row[0] == email
            conn.execute(text("DELETE FROM users WHERE email = :e"), {"e": email})
    finally:
        engine.dispose()
