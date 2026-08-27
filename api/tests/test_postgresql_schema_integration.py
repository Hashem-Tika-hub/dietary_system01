"""Real PostgreSQL migration and catalog-seeding integration test.

Set POSTGRES_INTEGRATION_DATABASE_URL to run this test locally. GitHub Actions
provides a disposable PostgreSQL service, while the ordinary SQLite suite skips
this test without failing local development.
"""

from __future__ import annotations

import os
import sqlite3
import subprocess
import sys
from pathlib import Path

import pytest
from sqlalchemy import create_engine, inspect, text

PROJECT_ROOT = Path(__file__).resolve().parents[2]
REFERENCE_SNAPSHOT = PROJECT_ROOT / "data" / "catalog" / "food_catalog_reference.sqlite3"
POSTGRES_INTEGRATION_DATABASE_URL = os.getenv("POSTGRES_INTEGRATION_DATABASE_URL")
REQUIRED_TABLES = {
    "alembic_version",
    "users",
    "meal_logs",
    "weekly_plans",
    "user_food_feedback",
    "catalog_sources",
    "foods",
    "food_nutrients",
    "food_portions",
    "ingredients",
    "food_ingredients",
    "allergens",
    "ingredient_allergens",
    "food_allergens",
}


def _run(command: list[str], database_url: str) -> subprocess.CompletedProcess[str]:
    environment = os.environ.copy()
    environment["DATABASE_URL"] = database_url
    environment["SECRET_KEY"] = "test-secret-key-for-postgresql-integration"
    return subprocess.run(
        command,
        cwd=PROJECT_ROOT,
        env=environment,
        text=True,
        capture_output=True,
        check=True,
    )


def _reference_count(table_name: str) -> int:
    with sqlite3.connect(REFERENCE_SNAPSHOT) as connection:
        return int(connection.execute(f"SELECT COUNT(*) FROM {table_name}").fetchone()[0])


@pytest.mark.skipif(
    not POSTGRES_INTEGRATION_DATABASE_URL,
    reason="POSTGRES_INTEGRATION_DATABASE_URL is required for PostgreSQL integration testing.",
)
def test_postgresql_migrations_and_catalog_seed_are_compatible():
    database_url = str(POSTGRES_INTEGRATION_DATABASE_URL)
    assert database_url.startswith("postgresql+")

    _run([sys.executable, "-m", "alembic", "upgrade", "head"], database_url)
    seeded = _run([sys.executable, "scripts/seed_runtime_catalog.py"], database_url)
    assert "Runtime catalog synchronized" in seeded.stdout

    engine = create_engine(database_url, pool_pre_ping=True)
    try:
        assert REQUIRED_TABLES.issubset(set(inspect(engine).get_table_names()))
        with engine.connect() as connection:
            assert connection.execute(text("SELECT version_num FROM alembic_version")).scalar_one()
            assert connection.execute(text("SELECT COUNT(*) FROM users")).scalar_one() == 0
            assert connection.execute(text("SELECT COUNT(*) FROM foods")).scalar_one() == _reference_count("foods")
            assert (
                connection.execute(text("SELECT COUNT(*) FROM food_nutrients")).scalar_one()
                == _reference_count("food_nutrients")
            )
            assert (
                connection.execute(text("SELECT COUNT(*) FROM food_portions")).scalar_one()
                == _reference_count("food_portions")
            )
            assert connection.execute(text("SELECT COUNT(*) FROM catalog_sources")).scalar_one() == _reference_count(
                "catalog_sources"
            )
    finally:
        engine.dispose()
