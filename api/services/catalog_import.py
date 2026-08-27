"""Idempotent import of the curated CSV into the catalog database tables.

The CSV remains a training/import input.  Runtime API queries use the catalog
schema after import.  This importer intentionally does not infer allergen
absence or presence from categories; allergen evidence requires its own
reviewed source.
"""

from __future__ import annotations

import csv
import hashlib
from datetime import UTC, datetime
from pathlib import Path
from typing import Iterable

from sqlalchemy.orm import Session

from api.db_models import CatalogSource, Food, FoodNutrient, FoodPortion
from api.services.catalog_readiness import catalog_readiness, ensure_reference_allergens
from api.services.halal_policy import explicit_non_halal_reasons


NUTRIENT_COLUMNS: dict[str, tuple[str, str]] = {
    "calories": ("energy_kcal", "kcal"),
    "protein": ("protein_g", "g"),
    "carbs": ("carbs_g", "g"),
    "fat": ("fat_g", "g"),
    "fiber": ("fiber_g", "g"),
    "sugar": ("sugar_g", "g"),
    "sodium": ("sodium_mg", "mg"),
    "calcium": ("calcium_mg", "mg"),
    "iron": ("iron_mg", "mg"),
}


class CatalogImportError(ValueError):
    """Raised when a catalog file cannot be imported safely."""


def _as_float(value: str | None, *, field: str, external_id: str) -> float:
    try:
        parsed = float(value or 0)
    except (TypeError, ValueError) as exc:
        raise CatalogImportError(
            f"القيمة الغذائية غير صالحة للحقل {field} في الطعام {external_id}"
        ) from exc
    if parsed < 0:
        raise CatalogImportError(
            f"القيمة الغذائية لا يمكن أن تكون سالبة للحقل {field} في الطعام {external_id}"
        )
    return parsed


def _as_bool(value: str | bool | None) -> bool:
    return str(value).strip().lower() in {"true", "1", "yes", "نعم"}


def _meal_tags(value: str | None) -> list[str]:
    return [tag.strip() for tag in str(value or "").split("،") if tag.strip()]


def _checksum(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _rows(path: Path) -> Iterable[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        required = {"fdc_id", "name", "calories", "protein", "carbs", "fat"}
        missing = required - set(reader.fieldnames or [])
        if missing:
            raise CatalogImportError(
                "ملف الكتالوج يفتقد الأعمدة المطلوبة: " + ", ".join(sorted(missing))
            )
        yield from reader


def import_food_catalog(
    db: Session,
    csv_path: Path,
    *,
    source_code: str = "curated-foods-csv",
    source_name: str = "Curated foods CSV import",
) -> dict[str, object]:
    """Upsert a curated food CSV into the relational catalog.

    The function flushes but does not commit.  The caller controls the
    transaction so a failed import cannot leave a partial catalog behind.
    """
    csv_path = Path(csv_path)
    if not csv_path.is_file():
        raise CatalogImportError(f"ملف الكتالوج غير موجود: {csv_path}")

    checksum = _checksum(csv_path)
    reference_allergens_created = ensure_reference_allergens(db)
    source = db.query(CatalogSource).filter(CatalogSource.code == source_code).one_or_none()
    if source is None:
        source = CatalogSource(
            code=source_code,
            name=source_name,
            version=checksum[:12],
            checksum=checksum,
            imported_at=datetime.now(UTC),
        )
        db.add(source)
        db.flush()
    else:
        source.name = source_name
        source.version = checksum[:12]
        source.checksum = checksum
        source.imported_at = datetime.now(UTC)

    existing_foods = {
        food.external_id: food
        for food in db.query(Food).filter(Food.source_id == source.id).all()
    }
    imported = 0
    created = 0
    nutrient_upserts = 0
    skipped_explicit_cultural_restrictions = 0
    seen_input_external_ids: set[str] = set()
    eligible_external_ids: set[str] = set()

    for row in _rows(csv_path):
        external_id = str(row["fdc_id"]).strip()
        if not external_id:
            raise CatalogImportError("يوجد صف بدون fdc_id في الكتالوج")
        if external_id in seen_input_external_ids:
            raise CatalogImportError(f"fdc_id مكرر في الكتالوج: {external_id}")
        seen_input_external_ids.add(external_id)
        if explicit_non_halal_reasons(row.get("name")):
            skipped_explicit_cultural_restrictions += 1
            continue
        eligible_external_ids.add(external_id)

        food = existing_foods.get(external_id)
        if food is None:
            food = Food(source_id=source.id, external_id=external_id, display_name="")
            db.add(food)
            db.flush()
            existing_foods[external_id] = food
            created += 1

        food.display_name = str(row.get("name") or external_id).strip()
        food.food_kind = "food"
        food.category = str(row.get("category") or "").strip() or None
        food.food_group = str(row.get("food_group") or "").strip() or None
        food.meal_tags = _meal_tags(row.get("meal_type"))
        food.basis_grams = 100.0
        food.data_quality = "estimated"
        food.is_active = True
        food.health_score = _as_float(row.get("health_score"), field="health_score", external_id=external_id)
        food.diabetic_friendly = _as_bool(row.get("diabetic_friendly"))
        food.low_sodium = _as_bool(row.get("low_sodium"))
        food.is_high_protein = _as_bool(row.get("is_high_protein"))

        nutrients = {nutrient.nutrient_code: nutrient for nutrient in food.nutrients}
        for csv_column, (nutrient_code, unit) in NUTRIENT_COLUMNS.items():
            amount = _as_float(row.get(csv_column), field=csv_column, external_id=external_id)
            nutrient = nutrients.get(nutrient_code)
            if nutrient is None:
                nutrient = FoodNutrient(
                    food_id=food.id,
                    nutrient_code=nutrient_code,
                    amount=amount,
                    unit=unit,
                    basis_grams=100.0,
                    data_quality="estimated",
                )
                db.add(nutrient)
            else:
                nutrient.amount = amount
                nutrient.unit = unit
                nutrient.basis_grams = 100.0
                nutrient.data_quality = "estimated"
            nutrient_upserts += 1

        if not any(portion.label == "100 g" for portion in food.portions):
            db.add(FoodPortion(food_id=food.id, label="100 g", grams=100.0, is_default=True))
        imported += 1

    # A source update should not leave retired rows exposed in search.
    for external_id, food in existing_foods.items():
        if external_id not in eligible_external_ids:
            food.is_active = False

    db.flush()
    return {
        "source_code": source_code,
        "checksum": checksum,
        "imported_foods": imported,
        "created_foods": created,
        "nutrient_upserts": nutrient_upserts,
        "skipped_explicit_cultural_restrictions": skipped_explicit_cultural_restrictions,
        "reference_allergens_created": reference_allergens_created,
        "readiness": catalog_readiness(db),
    }
