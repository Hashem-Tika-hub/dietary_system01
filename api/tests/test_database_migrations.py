"""Integration tests for the Alembic migration foundation.

These tests use a new SQLite file for every case. They never touch the local
``data/dietary.db`` development database.
"""

from __future__ import annotations

import importlib
import os
import subprocess
import sys
from pathlib import Path

from sqlalchemy import create_engine, inspect

PROJECT_ROOT = Path(__file__).resolve().parents[2]
ALEMBIC_COMMAND = [sys.executable, "-m", "alembic"]
EXPECTED_TABLES = {"alembic_version", "users", "meal_logs", "weekly_plans"}


def run_alembic(*arguments: str, database_url: str) -> None:
    """Run Alembic with an isolated database URL."""

    environment = os.environ.copy()
    environment["DATABASE_URL"] = database_url
    subprocess.run(
        [*ALEMBIC_COMMAND, *arguments],
        cwd=PROJECT_ROOT,
        env=environment,
        check=True,
        capture_output=True,
        text=True,
    )


def table_names(database_url: str) -> set[str]:
    engine = create_engine(database_url)
    try:
        return set(inspect(engine).get_table_names())
    finally:
        engine.dispose()


def import_database_module(database_url: str):
    """Import api.database with a test-specific DATABASE_URL."""

    os.environ["DATABASE_URL"] = database_url
    sys.modules.pop("api.database", None)
    return importlib.import_module("api.database")


def test_upgrade_creates_versioned_schema(tmp_path: Path) -> None:
    database_url = f"sqlite:///{tmp_path / 'migrated.db'}"

    run_alembic("upgrade", "head", database_url=database_url)

    assert EXPECTED_TABLES <= table_names(database_url)


def test_downgrade_base_removes_application_tables(tmp_path: Path) -> None:
    database_url = f"sqlite:///{tmp_path / 'rollback.db'}"

    run_alembic("upgrade", "head", database_url=database_url)
    run_alembic("downgrade", "base", database_url=database_url)

    assert not ({"users", "meal_logs", "weekly_plans"} & table_names(database_url))


def test_schema_check_rejects_database_without_migrations(tmp_path: Path) -> None:
    database_url = f"sqlite:///{tmp_path / 'unmanaged.db'}"
    database = import_database_module(database_url)

    try:
        database.assert_database_schema_is_current()
    except database.DatabaseMigrationRequiredError as error:
        assert "alembic upgrade head" in str(error)
    else:
        raise AssertionError("An unmanaged database must be rejected at startup")


def test_schema_check_accepts_migrated_database(tmp_path: Path) -> None:
    database_url = f"sqlite:///{tmp_path / 'checked.db'}"
    run_alembic("upgrade", "head", database_url=database_url)

    database = import_database_module(database_url)
    database.assert_database_schema_is_current()
