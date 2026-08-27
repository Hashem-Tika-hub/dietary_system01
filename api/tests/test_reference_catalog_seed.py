"""Tests for loading the catalog-only Git snapshot into a runtime database."""

from __future__ import annotations

import os
import sqlite3
import subprocess
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
REFERENCE_SNAPSHOT = PROJECT_ROOT / "data" / "catalog" / "food_catalog_reference.sqlite3"
RUNTIME_TABLES = {"users", "meal_logs", "weekly_plans", "user_food_feedback"}


def _run(command: list[str], database_url: str) -> subprocess.CompletedProcess[str]:
    environment = os.environ.copy()
    environment["DATABASE_URL"] = database_url
    environment["SECRET_KEY"] = "test-secret-key-for-catalog-seeding"
    return subprocess.run(
        command,
        cwd=PROJECT_ROOT,
        env=environment,
        text=True,
        capture_output=True,
        check=True,
    )


def _snapshot_count(table_name: str) -> int:
    with sqlite3.connect(REFERENCE_SNAPSHOT) as connection:
        return int(connection.execute(f"SELECT COUNT(*) FROM {table_name}").fetchone()[0])


def test_reference_catalog_seeds_empty_runtime_database_idempotently(tmp_path: Path):
    runtime_database = tmp_path / "runtime.sqlite3"
    database_url = f"sqlite:///{runtime_database}"

    _run([sys.executable, "-m", "alembic", "upgrade", "head"], database_url)
    first_run = _run([sys.executable, "scripts/seed_runtime_catalog.py"], database_url)
    second_run = _run([sys.executable, "scripts/seed_runtime_catalog.py"], database_url)

    assert "Runtime catalog synchronized" in first_run.stdout
    assert "Runtime catalog synchronized" in second_run.stdout

    with sqlite3.connect(runtime_database) as connection:
        assert int(connection.execute("SELECT COUNT(*) FROM users").fetchone()[0]) == 0
        assert int(connection.execute("SELECT COUNT(*) FROM foods").fetchone()[0]) == _snapshot_count("foods")
        assert int(connection.execute("SELECT COUNT(*) FROM food_nutrients").fetchone()[0]) == _snapshot_count("food_nutrients")
        assert int(connection.execute("SELECT COUNT(*) FROM food_portions").fetchone()[0]) == _snapshot_count("food_portions")
        assert connection.execute("PRAGMA foreign_key_check").fetchall() == []


def test_reference_snapshot_remains_catalog_only():
    with sqlite3.connect(REFERENCE_SNAPSHOT) as connection:
        tables = {
            row[0]
            for row in connection.execute("SELECT name FROM sqlite_master WHERE type = 'table'")
        }

    assert RUNTIME_TABLES.isdisjoint(tables)
