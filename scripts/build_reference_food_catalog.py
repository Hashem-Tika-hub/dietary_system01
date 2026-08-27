#!/usr/bin/env python3
"""Build a reviewable SQLite food-catalog snapshot for version control.

The output contains only schema, catalog sources, foods, nutrients, portions, and
reference allergen codes. It must never contain users, meal logs, plans, feedback,
or manufactured allergen evidence. It is a review artifact, not the runtime DB.

Example:
    python scripts/build_reference_food_catalog.py \
        --usda-archive /tmp/foundation.zip

To fetch the USDA archive only for this build:
    python scripts/build_reference_food_catalog.py --download-usda
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import sqlite3
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUTPUT = ROOT / "data" / "catalog" / "food_catalog_reference.sqlite3"
DEFAULT_MANIFEST = ROOT / "data" / "catalog" / "food_catalog_reference.manifest.json"
RUNTIME_TABLES = ("users", "meal_logs", "weekly_plans", "user_food_feedback")


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def run(command: list[str], environment: dict[str, str]) -> None:
    subprocess.run(command, cwd=ROOT, env=environment, check=True)


def query_scalar(connection: sqlite3.Connection, query: str) -> int:
    return int(connection.execute(query).fetchone()[0])


def build_manifest(database_path: Path, output_path: Path) -> dict[str, Any]:
    with sqlite3.connect(database_path) as connection:
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        foreign_key_violations = [
            dict(row) for row in connection.execute("PRAGMA foreign_key_check")
        ]
        runtime_counts = {
            table: query_scalar(connection, f"SELECT COUNT(*) FROM {table}")
            for table in RUNTIME_TABLES
        }
        if any(runtime_counts.values()):
            raise RuntimeError(
                "Reference snapshot contains runtime/user records: "
                + json.dumps(runtime_counts, ensure_ascii=False)
            )
        if foreign_key_violations:
            raise RuntimeError("Reference snapshot has foreign-key violations")

        sources = [
            dict(row)
            for row in connection.execute(
                """
                SELECT code, name, version, license_url, checksum
                FROM catalog_sources
                ORDER BY code
                """
            )
        ]
        counts = {
            "catalog_sources": query_scalar(connection, "SELECT COUNT(*) FROM catalog_sources"),
            "foods": query_scalar(connection, "SELECT COUNT(*) FROM foods WHERE is_active = 1"),
            "food_nutrients": query_scalar(connection, "SELECT COUNT(*) FROM food_nutrients"),
            "food_portions": query_scalar(connection, "SELECT COUNT(*) FROM food_portions"),
            "allergens": query_scalar(connection, "SELECT COUNT(*) FROM allergens"),
            "ingredients": query_scalar(connection, "SELECT COUNT(*) FROM ingredients"),
            "food_ingredients": query_scalar(connection, "SELECT COUNT(*) FROM food_ingredients"),
            "food_allergens": query_scalar(connection, "SELECT COUNT(*) FROM food_allergens"),
        }
        revision = connection.execute("SELECT version_num FROM alembic_version").fetchone()[0]

    return {
        "format": "dietary-system-reference-food-catalog",
        "format_version": 1,
        "database_file": str(output_path.relative_to(ROOT)),
        "database_sha256": sha256(database_path),
        "alembic_revision": revision,
        "catalog_sources": sources,
        "active_row_counts": counts,
        "runtime_user_table_counts": runtime_counts,
        "foreign_key_violations": foreign_key_violations,
        "review_notes": [
            "This snapshot is a food-catalog review artifact. Do not configure it as the mutable runtime database.",
            "No FoodAllergen or IngredientAllergen evidence is manufactured by this build.",
            "The halal policy removes only configured explicit pork/alcohol indicators; this is not halal certification.",
        ],
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="بناء نسخة SQLite مرجعية قابلة للمراجعة لكتالوج الأطعمة فقط"
    )
    source_group = parser.add_mutually_exclusive_group(required=True)
    source_group.add_argument(
        "--usda-archive",
        type=Path,
        help="مسار أرشيف USDA Foundation Foods CSV ZIP المحمل مسبقًا",
    )
    source_group.add_argument(
        "--download-usda",
        action="store_true",
        help="تنزيل أرشيف USDA الرسمي مؤقتًا لهذا البناء فقط",
    )
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    output_path = args.output.resolve()
    manifest_path = args.manifest.resolve()
    output_path.parent.mkdir(parents=True, exist_ok=True)
    manifest_path.parent.mkdir(parents=True, exist_ok=True)

    with tempfile.TemporaryDirectory(prefix="dietary-reference-catalog-") as temporary_dir:
        temporary = Path(temporary_dir)
        build_db = temporary / "food_catalog_reference.sqlite3"
        usda_archive = args.usda_archive.resolve() if args.usda_archive else temporary / "foundation.zip"
        if args.usda_archive and not usda_archive.is_file():
            raise SystemExit(f"USDA archive not found: {usda_archive}")

        environment = os.environ.copy()
        environment["DATABASE_URL"] = f"sqlite:///{build_db}"
        run([sys.executable, "-m", "alembic", "upgrade", "head"], environment)

        usda_command = [
            sys.executable,
            "scripts/import_usda_foundation_catalog.py",
            "--limit",
            "0",
        ]
        if args.download_usda:
            usda_command.extend(["--download-to", str(usda_archive)])
        else:
            usda_command.extend(["--archive", str(usda_archive)])
        run(usda_command, environment)
        run([sys.executable, "scripts/import_food_catalog.py"], environment)

        with sqlite3.connect(build_db) as connection:
            connection.execute("VACUUM")

        manifest = build_manifest(build_db, output_path)
        shutil.copy2(build_db, output_path)
        manifest["database_sha256"] = sha256(output_path)
        manifest_path.write_text(
            json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )

    print(json.dumps(manifest, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
