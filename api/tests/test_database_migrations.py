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

import pytest
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.exc import IntegrityError

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


def test_user_profile_sanity_constraints_reject_invalid_direct_database_writes(
    tmp_path: Path,
) -> None:
    """Database constraints protect user profiles even when API validation is bypassed."""
    database_url = f"sqlite:///{tmp_path / 'profile-constraints.db'}"
    run_alembic("upgrade", "head", database_url=database_url)

    engine = create_engine(database_url)
    try:
        checks = {check["name"] for check in inspect(engine).get_check_constraints("users")}
        assert {
            "ck_users_age_range",
            "ck_users_weight_range",
            "ck_users_height_range",
            "ck_users_activity_level_range",
            "ck_users_body_profile_bmi_sanity",
        } <= checks

        with engine.begin() as connection:
            with pytest.raises(IntegrityError):
                connection.execute(
                    text(
                        """
                        INSERT INTO users (
                            email, hashed_password, name, age, gender,
                            weight, height, activity_level, goal
                        ) VALUES (
                            :email, :hashed_password, :name, :age, :gender,
                            :weight, :height, :activity_level, :goal
                        )
                        """
                    ),
                    {
                        "email": "invalid-direct-write@example.com",
                        "hashed_password": "not-a-real-password",
                        "name": "اختبار قاعدة البيانات",
                        "age": 28,
                        "gender": "male",
                        "weight": 30.0,
                        "height": 200.0,
                        "activity_level": 3,
                        "goal": "maintain",
                    },
                )
    finally:
        engine.dispose()


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
