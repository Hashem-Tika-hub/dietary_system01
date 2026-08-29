from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import pytest
from sqlalchemy import create_engine, inspect, text

PROJECT_ROOT = Path(__file__).resolve().parents[2]
POSTGRES_TEST_URL = os.getenv("POSTGRES_TEST_URL")
pytestmark = pytest.mark.skipif(
    not POSTGRES_TEST_URL,
    reason="POSTGRES_TEST_URL is not configured",
)


def test_postgresql_migrations_create_normalized_food_architecture() -> None:
    assert POSTGRES_TEST_URL is not None
    environment = os.environ.copy()
    environment["DATABASE_URL"] = POSTGRES_TEST_URL
    migration = subprocess.run(
        [sys.executable, "-m", "alembic", "upgrade", "head"],
        cwd=PROJECT_ROOT,
        env=environment,
        capture_output=True,
        text=True,
    )
    if migration.returncode != 0:
        pytest.fail(
            "Alembic PostgreSQL migration failed:\n"
            f"stdout:\n{migration.stdout}\n"
            f"stderr:\n{migration.stderr}"
        )

    engine = create_engine(POSTGRES_TEST_URL)
    try:
        tables = set(inspect(engine).get_table_names())
        assert {
            "users",
            "foods",
            "food_categories",
            "food_meal_types",
            "dietary_tags",
            "food_dietary_tags",
            "meals",
            "meal_ingredients",
            "user_food_preferences",
            "user_dietary_preferences",
            "recommendations",
            "user_interactions",
        } <= tables
        with engine.begin() as connection:
            connection.execute(
                text(
                    """
                    INSERT INTO meals (name, description, is_active, created_at, updated_at)
                    VALUES ('PostgreSQL architecture test', 'rollback-safe integration fixture', TRUE, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
                    """
                )
            )
            assert connection.execute(
                text("SELECT count(*) FROM meals WHERE name = 'PostgreSQL architecture test'")
            ).scalar_one() == 1
    finally:
        engine.dispose()
