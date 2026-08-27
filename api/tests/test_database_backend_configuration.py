"""Configuration tests for the supported runtime database backends."""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]


def _database_process(database_url: str) -> subprocess.CompletedProcess[str]:
    environment = os.environ.copy()
    environment["DATABASE_URL"] = database_url
    return subprocess.run(
        [
            sys.executable,
            "-c",
            "from api.database import DATABASE_BACKEND, engine_options; "
            "print(DATABASE_BACKEND); print(engine_options.get('pool_pre_ping', False))",
        ],
        cwd=PROJECT_ROOT,
        env=environment,
        text=True,
        capture_output=True,
        check=False,
    )


def test_sqlite_is_supported_without_postgresql_connection_pooling(tmp_path: Path):
    result = _database_process(f"sqlite:///{tmp_path / 'local.sqlite3'}")

    assert result.returncode == 0
    assert result.stdout.splitlines() == ["sqlite", "False"]


def test_postgresql_is_supported_with_connection_pre_ping():
    result = _database_process(
        "postgresql+psycopg://dietary:nonsecret@localhost:5432/dietary_test"
    )

    assert result.returncode == 0
    assert result.stdout.splitlines() == ["postgresql", "True"]


def test_unsupported_database_backend_does_not_echo_credentials():
    secret_url = "mysql+pymysql://dietary:very-secret-password@localhost/dietary"
    result = _database_process(secret_url)

    assert result.returncode != 0
    assert "محرك قاعدة البيانات غير مدعوم" in result.stderr
    assert secret_url not in result.stderr
    assert "very-secret-password" not in result.stderr
