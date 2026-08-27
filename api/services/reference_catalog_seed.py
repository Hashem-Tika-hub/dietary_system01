"""Seed a mutable runtime database from the reviewable food-catalog snapshot.

The SQLite snapshot is intentionally catalog-only and is tracked for review. This
module copies only catalog records into the database selected by DATABASE_URL;
it never copies, creates, or manages runtime user data.
"""

from __future__ import annotations

import json
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Any

from sqlalchemy.orm import Session

from api.db_models import (
    Allergen,
    CatalogSource,
    Food,
    FoodAllergen,
    FoodIngredient,
    FoodNutrient,
    FoodPortion,
    Ingredient,
    IngredientAllergen,
)
from config import REFERENCE_FOOD_CATALOG_PATH

RUNTIME_TABLES = frozenset({"users", "meal_logs", "weekly_plans", "user_food_feedback"})
SNAPSHOT_TABLES = frozenset(
    {
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
)


def _snapshot_connection(snapshot_path: Path) -> sqlite3.Connection:
    if not snapshot_path.is_file():
        raise FileNotFoundError(f"Reference catalog snapshot not found: {snapshot_path}")

    connection = sqlite3.connect(snapshot_path)
    connection.row_factory = sqlite3.Row
    table_names = {
        row[0]
        for row in connection.execute("SELECT name FROM sqlite_master WHERE type = 'table'")
    }
    missing_tables = SNAPSHOT_TABLES - table_names
    forbidden_tables = RUNTIME_TABLES & table_names
    if missing_tables or forbidden_tables:
        connection.close()
        details = []
        if missing_tables:
            details.append("missing: " + ", ".join(sorted(missing_tables)))
        if forbidden_tables:
            details.append("contains runtime tables: " + ", ".join(sorted(forbidden_tables)))
        raise ValueError("Invalid reference catalog snapshot (" + "; ".join(details) + ")")
    return connection


def _datetime(value: Any) -> datetime | None:
    if value is None or isinstance(value, datetime):
        return value
    if isinstance(value, str):
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    raise TypeError(f"Unsupported datetime value in reference snapshot: {value!r}")


def _json_list(value: Any) -> list[Any]:
    if value is None:
        return []
    if isinstance(value, list):
        return value
    if isinstance(value, str):
        decoded = json.loads(value)
        if isinstance(decoded, list):
            return decoded
    raise TypeError(f"Expected JSON list in reference snapshot, got {value!r}")


def _copy_catalog_sources(db: Session, source: sqlite3.Connection) -> dict[int, CatalogSource]:
    target_by_code = {row.code: row for row in db.query(CatalogSource).all()}
    mapping: dict[int, CatalogSource] = {}
    for row in source.execute("SELECT * FROM catalog_sources ORDER BY id"):
        target = target_by_code.get(row["code"])
        values = {
            "name": row["name"],
            "version": row["version"],
            "license_url": row["license_url"],
            "checksum": row["checksum"],
            "imported_at": _datetime(row["imported_at"]),
        }
        if target is None:
            target = CatalogSource(code=row["code"], **values)
            db.add(target)
            db.flush()
            target_by_code[target.code] = target
        else:
            for field, value in values.items():
                setattr(target, field, value)
        mapping[row["id"]] = target
    return mapping


def _copy_foods(
    db: Session, source: sqlite3.Connection, source_mapping: dict[int, CatalogSource]
) -> dict[int, Food]:
    target_by_key = {
        (row.source_id, row.external_id): row
        for row in db.query(Food).filter(Food.source_id.in_([item.id for item in source_mapping.values()])).all()
    }
    mapping: dict[int, Food] = {}
    for row in source.execute("SELECT * FROM foods ORDER BY id"):
        target_source = source_mapping[row["source_id"]]
        key = (target_source.id, row["external_id"])
        values = {
            "display_name": row["display_name"],
            "food_kind": row["food_kind"],
            "category": row["category"],
            "food_group": row["food_group"],
            "meal_tags": _json_list(row["meal_tags"]),
            "basis_grams": row["basis_grams"],
            "data_quality": row["data_quality"],
            "health_score": row["health_score"],
            "diabetic_friendly": bool(row["diabetic_friendly"]),
            "low_sodium": bool(row["low_sodium"]),
            "is_high_protein": bool(row["is_high_protein"]),
            "is_active": bool(row["is_active"]),
            "created_at": _datetime(row["created_at"]),
            "updated_at": _datetime(row["updated_at"]),
        }
        target = target_by_key.get(key)
        if target is None:
            target = Food(source_id=target_source.id, external_id=row["external_id"], **values)
            db.add(target)
            db.flush()
            target_by_key[key] = target
        else:
            for field, value in values.items():
                setattr(target, field, value)
        mapping[row["id"]] = target
    return mapping


def _copy_food_nutrients_and_portions(
    db: Session, source: sqlite3.Connection, food_mapping: dict[int, Food]
) -> None:
    target_food_ids = [food.id for food in food_mapping.values()]
    if target_food_ids:
        db.query(FoodNutrient).filter(FoodNutrient.food_id.in_(target_food_ids)).delete(
            synchronize_session=False
        )
        db.query(FoodPortion).filter(FoodPortion.food_id.in_(target_food_ids)).delete(
            synchronize_session=False
        )
    for row in source.execute("SELECT * FROM food_nutrients ORDER BY id"):
        db.add(
            FoodNutrient(
                food_id=food_mapping[row["food_id"]].id,
                nutrient_code=row["nutrient_code"],
                amount=row["amount"],
                unit=row["unit"],
                basis_grams=row["basis_grams"],
                data_quality=row["data_quality"],
            )
        )
    for row in source.execute("SELECT * FROM food_portions ORDER BY id"):
        db.add(
            FoodPortion(
                food_id=food_mapping[row["food_id"]].id,
                label=row["label"],
                grams=row["grams"],
                is_default=bool(row["is_default"]),
            )
        )


def _copy_ingredients_and_allergens(
    db: Session, source: sqlite3.Connection
) -> tuple[dict[int, Ingredient], dict[int, Allergen]]:
    target_ingredients = {row.canonical_name: row for row in db.query(Ingredient).all()}
    ingredient_mapping: dict[int, Ingredient] = {}
    for row in source.execute("SELECT * FROM ingredients ORDER BY id"):
        target = target_ingredients.get(row["canonical_name"])
        values = {
            "display_name_ar": row["display_name_ar"],
            "description": row["description"],
        }
        if target is None:
            target = Ingredient(canonical_name=row["canonical_name"], **values)
            db.add(target)
            db.flush()
            target_ingredients[target.canonical_name] = target
        else:
            for field, value in values.items():
                setattr(target, field, value)
        ingredient_mapping[row["id"]] = target

    target_allergens = {row.code: row for row in db.query(Allergen).all()}
    allergen_mapping: dict[int, Allergen] = {}
    for row in source.execute("SELECT * FROM allergens ORDER BY id"):
        target = target_allergens.get(row["code"])
        values = {
            "display_name_ar": row["display_name_ar"],
            "display_name_en": row["display_name_en"],
            "description": row["description"],
        }
        if target is None:
            target = Allergen(code=row["code"], **values)
            db.add(target)
            db.flush()
            target_allergens[target.code] = target
        else:
            for field, value in values.items():
                setattr(target, field, value)
        allergen_mapping[row["id"]] = target
    return ingredient_mapping, allergen_mapping


def _copy_catalog_links(
    db: Session,
    source: sqlite3.Connection,
    food_mapping: dict[int, Food],
    source_mapping: dict[int, CatalogSource],
    ingredient_mapping: dict[int, Ingredient],
    allergen_mapping: dict[int, Allergen],
) -> None:
    target_food_ids = [food.id for food in food_mapping.values()]
    if target_food_ids:
        db.query(FoodIngredient).filter(FoodIngredient.food_id.in_(target_food_ids)).delete(
            synchronize_session=False
        )
        db.query(FoodAllergen).filter(FoodAllergen.food_id.in_(target_food_ids)).delete(
            synchronize_session=False
        )
    target_ingredient_ids = [ingredient.id for ingredient in ingredient_mapping.values()]
    if target_ingredient_ids:
        db.query(IngredientAllergen).filter(
            IngredientAllergen.ingredient_id.in_(target_ingredient_ids)
        ).delete(synchronize_session=False)

    for row in source.execute("SELECT * FROM food_ingredients ORDER BY id"):
        db.add(
            FoodIngredient(
                food_id=food_mapping[row["food_id"]].id,
                ingredient_id=ingredient_mapping[row["ingredient_id"]].id,
                amount_g=row["amount_g"],
                role=row["role"],
                is_optional=bool(row["is_optional"]),
            )
        )
    for row in source.execute("SELECT * FROM ingredient_allergens ORDER BY id"):
        db.add(
            IngredientAllergen(
                ingredient_id=ingredient_mapping[row["ingredient_id"]].id,
                allergen_id=allergen_mapping[row["allergen_id"]].id,
                status=row["status"],
                source_id=(source_mapping[row["source_id"]].id if row["source_id"] else None),
                reviewed_at=_datetime(row["reviewed_at"]),
            )
        )
    for row in source.execute("SELECT * FROM food_allergens ORDER BY id"):
        db.add(
            FoodAllergen(
                food_id=food_mapping[row["food_id"]].id,
                allergen_id=allergen_mapping[row["allergen_id"]].id,
                status=row["status"],
                source_id=(source_mapping[row["source_id"]].id if row["source_id"] else None),
                reviewed_at=_datetime(row["reviewed_at"]),
            )
        )


def seed_reference_catalog(
    db: Session, snapshot_path: Path | str = REFERENCE_FOOD_CATALOG_PATH
) -> dict[str, int]:
    """Synchronize catalog-only records from a reviewed SQLite snapshot.

    The caller owns the transaction and must call ``commit`` or ``rollback``.
    Existing foods are matched by the stable ``(source, external_id)`` key.
    """

    connection = _snapshot_connection(Path(snapshot_path))
    try:
        source_mapping = _copy_catalog_sources(db, connection)
        food_mapping = _copy_foods(db, connection, source_mapping)
        _copy_food_nutrients_and_portions(db, connection, food_mapping)
        ingredient_mapping, allergen_mapping = _copy_ingredients_and_allergens(db, connection)
        _copy_catalog_links(
            db,
            connection,
            food_mapping,
            source_mapping,
            ingredient_mapping,
            allergen_mapping,
        )
        db.flush()
        return {
            "catalog_sources": len(source_mapping),
            "foods": len(food_mapping),
            "food_nutrients": int(
                connection.execute("SELECT COUNT(*) FROM food_nutrients").fetchone()[0]
            ),
            "food_portions": int(
                connection.execute("SELECT COUNT(*) FROM food_portions").fetchone()[0]
            ),
        }
    finally:
        connection.close()
