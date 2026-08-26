#!/usr/bin/env python3
"""Audit a local SQLite database without mutating any data.

Usage:
    python scripts/audit_database_integrity.py data/dietary.db
"""

from __future__ import annotations

import json
import sqlite3
import sys
from pathlib import Path


CORE_TABLES = (
    "users",
    "meal_logs",
    "weekly_plans",
    "catalog_sources",
    "foods",
    "food_nutrients",
    "food_portions",
    "ingredients",
    "food_ingredients",
    "allergens",
    "ingredient_allergens",
    "food_allergens",
    "user_food_feedback",
)


def table_exists(connection: sqlite3.Connection, table: str) -> bool:
    return connection.execute(
        "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = ?", (table,)
    ).fetchone() is not None


def scalar(connection: sqlite3.Connection, query: str) -> int:
    return int(connection.execute(query).fetchone()[0])


def audit(database_path: Path) -> dict:
    connection = sqlite3.connect(database_path)
    connection.row_factory = sqlite3.Row
    try:
        all_tables = [
            row["name"]
            for row in connection.execute(
                "SELECT name FROM sqlite_master WHERE type = 'table' ORDER BY name"
            )
        ]
        counts = {
            table: scalar(connection, f"SELECT COUNT(*) FROM {table}")
            for table in CORE_TABLES
            if table_exists(connection, table)
        }
        versions = []
        if table_exists(connection, "alembic_version"):
            versions = [
                row["version_num"]
                for row in connection.execute("SELECT version_num FROM alembic_version")
            ]

        foreign_key_violations = [dict(row) for row in connection.execute("PRAGMA foreign_key_check")]
        findings: list[dict] = []

        if "foods" not in counts:
            findings.append({
                "severity": "critical",
                "code": "catalog_schema_missing",
                "message": "قاعدة البيانات لا تحتوي جدول foods الخاص بالكتالوج الموثق.",
            })
        elif counts["foods"] == 0:
            findings.append({
                "severity": "high",
                "code": "catalog_empty",
                "message": "جدول foods موجود لكنه فارغ؛ لا يمكن ربط مرشحي التوصية بدليل الحساسية الموثق.",
            })

        if "meal_logs" in counts and "foods" in counts:
            unmatched_logs = scalar(
                connection,
                """
                SELECT COUNT(*)
                FROM meal_logs AS log
                LEFT JOIN foods AS food ON CAST(food.external_id AS TEXT) = CAST(log.fdc_id AS TEXT)
                WHERE log.fdc_id IS NOT NULL AND TRIM(log.fdc_id) <> '' AND food.id IS NULL
                """,
            )
            if unmatched_logs:
                findings.append({
                    "severity": "medium",
                    "code": "meal_log_catalog_gap",
                    "count": unmatched_logs,
                    "message": "بعض MealLog.fdc_id لا يطابق Food.external_id؛ يبقى السجل صالحًا للاستهلاك اليومي لكنه غير مرتبط بكتالوج موثق.",
                })

        if "foods" in counts and "food_allergens" in counts:
            foods_without_allergen_evidence = scalar(
                connection,
                """
                SELECT COUNT(*)
                FROM foods AS food
                LEFT JOIN food_allergens AS evidence ON evidence.food_id = food.id
                WHERE food.is_active = 1 AND evidence.id IS NULL
                """,
            )
            if foods_without_allergen_evidence:
                findings.append({
                    "severity": "high",
                    "code": "missing_food_allergen_evidence",
                    "count": foods_without_allergen_evidence,
                    "message": "أطعمة نشطة لا تحمل أي دليل FoodAllergen؛ ستظهر كبيانات غير مكتملة للمستخدم ذي الحساسية المعلنة.",
                })

        if foreign_key_violations:
            findings.append({
                "severity": "critical",
                "code": "foreign_key_violations",
                "count": len(foreign_key_violations),
                "message": "تم العثور على انتهاكات مرجعية في SQLite؛ يجب إصلاحها قبل أي ترحيل بيانات.",
            })

        return {
            "database": str(database_path),
            "tables": all_tables,
            "alembic_versions": versions,
            "row_counts": counts,
            "foreign_key_violations": foreign_key_violations,
            "findings": findings,
        }
    finally:
        connection.close()


def main() -> None:
    database_path = Path(sys.argv[1] if len(sys.argv) > 1 else "data/dietary.db")
    if not database_path.is_file():
        raise SystemExit(f"Database file not found: {database_path}")
    print(json.dumps(audit(database_path), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
