from __future__ import annotations

import hashlib
import json
import sqlite3
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
DATABASE_PATH = ROOT / "data" / "catalog" / "food_catalog_reference.sqlite3"
MANIFEST_PATH = ROOT / "data" / "catalog" / "food_catalog_reference.manifest.json"
RUNTIME_TABLES = ("users", "meal_logs", "weekly_plans", "user_food_feedback")


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def test_reference_catalog_snapshot_is_reviewable_and_user_data_free() -> None:
    assert DATABASE_PATH.is_file()
    assert MANIFEST_PATH.is_file()

    manifest = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    assert manifest["format"] == "dietary-system-reference-food-catalog"
    assert manifest["database_file"] == "data/catalog/food_catalog_reference.sqlite3"
    assert manifest["database_sha256"] == sha256(DATABASE_PATH)
    assert manifest["foreign_key_violations"] == []
    assert manifest["runtime_user_table_counts"] == {
        "users": 0,
        "meal_logs": 0,
        "weekly_plans": 0,
        "user_food_feedback": 0,
    }

    with sqlite3.connect(DATABASE_PATH) as connection:
        connection.execute("PRAGMA foreign_keys = ON")
        table_counts = {
            table: int(connection.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0])
            for table in RUNTIME_TABLES
        }
        active_foods = int(
            connection.execute("SELECT COUNT(*) FROM foods WHERE is_active = 1").fetchone()[0]
        )
        foreign_key_violations = list(connection.execute("PRAGMA foreign_key_check"))

    assert table_counts == manifest["runtime_user_table_counts"]
    assert table_counts == {table: 0 for table in RUNTIME_TABLES}
    assert active_foods == manifest["active_row_counts"]["foods"]
    assert active_foods > 0
    assert foreign_key_violations == []
