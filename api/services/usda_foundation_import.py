"""Import USDA FoodData Central Foundation Foods into the relational catalog.

The importer accepts an official USDA CSV ZIP archive, not a live API response.
It preserves the release date and SHA-256 checksum in ``catalog_sources`` and
imports only ``foundation_food`` rows with energy, protein, carbohydrate, and
fat values.  It intentionally creates no FoodAllergen or IngredientAllergen
records: nutrient data do not prove allergen absence or presence.
"""

from __future__ import annotations

import csv
import hashlib
import re
import shutil
import tempfile
import zipfile
from datetime import UTC, datetime
from io import TextIOWrapper
from pathlib import Path
from urllib.request import Request, urlopen

from sqlalchemy.orm import Session

from api.db_models import CatalogSource, Food, FoodNutrient, FoodPortion
from api.services.catalog_import import CatalogImportError
from api.services.catalog_readiness import catalog_readiness, ensure_reference_allergens


USDA_FOUNDATION_CSV_URL = (
    "https://fdc.nal.usda.gov/fdc-datasets/"
    "FoodData_Central_foundation_food_csv_2026-04-30.zip"
)
USDA_FOUNDATION_SOURCE_CODE = "usda-fdc-foundation"
USDA_FOUNDATION_SOURCE_NAME = "USDA FoodData Central Foundation Foods"
USDA_CC0_LICENSE_URL = "https://creativecommons.org/publicdomain/zero/1.0/"

_ARCHIVE_RELEASE_PATTERN = re.compile(
    r"FoodData_Central_foundation_food_csv_(\d{4}-\d{2}-\d{2})"
)
_REQUIRED_ARCHIVE_FILES = ("food.csv", "food_nutrient.csv", "food_category.csv")

# USDA nutrient IDs documented in the Foundation Foods CSV export.  Energy is
# selected in priority order so one normalized energy_kcal value is retained.
_USDA_NUTRIENTS: dict[str, tuple[tuple[str, ...], str, str]] = {
    "energy_kcal": (("1008", "2047", "2048"), "energy_kcal", "kcal"),
    "protein_g": (("1003",), "protein_g", "g"),
    "carbs_g": (("1005",), "carbs_g", "g"),
    "fat_g": (("1004",), "fat_g", "g"),
    "fiber_g": (("1079",), "fiber_g", "g"),
    "sugar_g": (("2000", "1063"), "sugar_g", "g"),
    "sodium_mg": (("1093",), "sodium_mg", "mg"),
    "calcium_mg": (("1087",), "calcium_mg", "mg"),
    "iron_mg": (("1089",), "iron_mg", "mg"),
}
_REQUIRED_NUTRIENT_CODES = frozenset({"energy_kcal", "protein_g", "carbs_g", "fat_g"})
_USDA_NUTRIENT_LOOKUP = {
    nutrient_id: (code, priority, unit)
    for code, (nutrient_ids, _, unit) in _USDA_NUTRIENTS.items()
    for priority, nutrient_id in enumerate(nutrient_ids)
}


def download_usda_foundation_archive(
    destination: Path,
    *,
    url: str = USDA_FOUNDATION_CSV_URL,
) -> Path:
    """Download the public USDA archive atomically without storing an API key."""
    destination = Path(destination)
    destination.parent.mkdir(parents=True, exist_ok=True)
    request = Request(
        url,
        headers={"User-Agent": "dietary-system01-catalog-import/1.0"},
    )
    with tempfile.NamedTemporaryFile(
        mode="wb", delete=False, dir=destination.parent, suffix=".part"
    ) as temporary:
        temporary_path = Path(temporary.name)
        try:
            with urlopen(request, timeout=60) as response:
                if response.status != 200:
                    raise CatalogImportError(
                        f"تعذر تنزيل أرشيف USDA: HTTP {response.status}"
                    )
                shutil.copyfileobj(response, temporary)
            temporary.replace(destination)
        except Exception:
            temporary_path.unlink(missing_ok=True)
            raise
    return destination


def _archive_release_date(archive_path: Path, names: tuple[str, ...]) -> str:
    candidates = [archive_path.name, *names]
    for value in candidates:
        match = _ARCHIVE_RELEASE_PATTERN.search(value)
        if match:
            return match.group(1)
    raise CatalogImportError(
        "تعذر تحديد تاريخ إصدار USDA من اسم أرشيف Foundation Foods"
    )


def _archive_members(archive: zipfile.ZipFile) -> dict[str, str]:
    members: dict[str, str] = {}
    for name in archive.namelist():
        if name.endswith("/"):
            continue
        base_name = Path(name).name
        if base_name in _REQUIRED_ARCHIVE_FILES:
            if base_name in members:
                raise CatalogImportError(
                    f"أرشيف USDA يحتوي أكثر من ملف باسم {base_name}"
                )
            members[base_name] = name
    missing = set(_REQUIRED_ARCHIVE_FILES) - set(members)
    if missing:
        raise CatalogImportError(
            "أرشيف USDA يفتقد الملفات المطلوبة: " + ", ".join(sorted(missing))
        )
    return members


def _read_csv_rows(archive: zipfile.ZipFile, member: str):
    with archive.open(member) as binary_handle:
        yield from csv.DictReader(TextIOWrapper(binary_handle, encoding="utf-8-sig", newline=""))


def _parse_amount(value: str | None, *, field: str, fdc_id: str) -> float:
    try:
        return float(value or "")
    except (TypeError, ValueError) as exc:
        raise CatalogImportError(
            f"قيمة USDA غير صالحة للحقل {field} للطعام {fdc_id}"
        ) from exc


def _source_checksum(archive_path: Path) -> str:
    digest = hashlib.sha256()
    with Path(archive_path).open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _upsert_source(
    db: Session,
    *,
    source_code: str,
    release_date: str,
    checksum: str,
) -> CatalogSource:
    source = db.query(CatalogSource).filter(CatalogSource.code == source_code).one_or_none()
    if source is None:
        source = CatalogSource(
            code=source_code,
            name=USDA_FOUNDATION_SOURCE_NAME,
            version=release_date,
            license_url=USDA_CC0_LICENSE_URL,
            checksum=checksum,
            imported_at=datetime.now(UTC),
        )
        db.add(source)
        db.flush()
        return source

    source.name = USDA_FOUNDATION_SOURCE_NAME
    source.version = release_date
    source.license_url = USDA_CC0_LICENSE_URL
    source.checksum = checksum
    source.imported_at = datetime.now(UTC)
    return source


def _load_foundation_rows(
    archive: zipfile.ZipFile,
    members: dict[str, str],
    *,
    limit: int | None,
) -> tuple[list[dict[str, object]], int, int]:
    categories = {
        str(row["id"]): str(row.get("description") or "").strip()
        for row in _read_csv_rows(archive, members["food_category.csv"])
    }
    foundation_foods = {
        str(row["fdc_id"]): row
        for row in _read_csv_rows(archive, members["food.csv"])
        if str(row.get("data_type") or "") == "foundation_food"
    }
    nutrient_values: dict[str, dict[str, tuple[int, float]]] = {}
    foods_with_invalid_selected_nutrients: set[str] = set()
    for row in _read_csv_rows(archive, members["food_nutrient.csv"]):
        fdc_id = str(row.get("fdc_id") or "")
        if fdc_id not in foundation_foods:
            continue
        mapping = _USDA_NUTRIENT_LOOKUP.get(str(row.get("nutrient_id") or ""))
        if mapping is None or not row.get("amount"):
            continue
        code, priority, _unit = mapping
        amount = _parse_amount(row.get("amount"), field=code, fdc_id=fdc_id)
        if amount < 0:
            # USDA carbohydrate-by-difference values can be slightly negative
            # after laboratory rounding.  Do not mutate the official value to
            # zero: exclude that food from a catalog that requires nonnegative
            # nutrients and report the omission to the caller instead.
            foods_with_invalid_selected_nutrients.add(fdc_id)
            continue
        existing = nutrient_values.setdefault(fdc_id, {}).get(code)
        if existing is None or priority < existing[0]:
            nutrient_values[fdc_id][code] = (priority, amount)

    selected: list[dict[str, object]] = []
    skipped_missing_required = 0
    skipped_invalid_selected_nutrients = 0
    for fdc_id in sorted(foundation_foods, key=int):
        if fdc_id in foods_with_invalid_selected_nutrients:
            skipped_invalid_selected_nutrients += 1
            continue
        nutrient_map = nutrient_values.get(fdc_id, {})
        if not _REQUIRED_NUTRIENT_CODES.issubset(nutrient_map):
            skipped_missing_required += 1
            continue
        food = foundation_foods[fdc_id]
        category = categories.get(str(food.get("food_category_id") or ""), "")
        selected.append(
            {
                "fdc_id": fdc_id,
                "name": str(food.get("description") or fdc_id).strip(),
                "category": category or None,
                "nutrients": {
                    code: amount
                    for code, (_priority, amount) in nutrient_map.items()
                },
            }
        )
        if limit is not None and len(selected) >= limit:
            break
    return selected, skipped_missing_required, skipped_invalid_selected_nutrients


def import_usda_foundation_catalog(
    db: Session,
    archive_path: Path,
    *,
    limit: int | None = None,
    source_code: str = USDA_FOUNDATION_SOURCE_CODE,
) -> dict[str, object]:
    """Upsert eligible USDA Foundation Foods from an official CSV ZIP archive.

    The importer flushes but never commits.  ``limit`` is intended for staged
    rollouts and is deterministic by ascending FDC ID.  Existing items from
    the source are not deactivated by a limited import.
    """
    if limit is not None and limit <= 0:
        raise CatalogImportError("حد استيراد USDA يجب أن يكون عددًا موجبًا")
    archive_path = Path(archive_path)
    if not archive_path.is_file():
        raise CatalogImportError(f"أرشيف USDA غير موجود: {archive_path}")

    checksum = _source_checksum(archive_path)
    try:
        with zipfile.ZipFile(archive_path) as archive:
            members = _archive_members(archive)
            release_date = _archive_release_date(
                archive_path, tuple(archive.namelist())
            )
            (
                rows,
                skipped_missing_required,
                skipped_invalid_selected_nutrients,
            ) = _load_foundation_rows(archive, members, limit=limit)
    except zipfile.BadZipFile as exc:
        raise CatalogImportError("ملف USDA ليس أرشيف ZIP صالحًا") from exc

    if not rows:
        raise CatalogImportError("لا توجد أطعمة USDA مكتملة بالمغذيات المطلوبة")

    reference_allergens_created = ensure_reference_allergens(db)
    source = _upsert_source(
        db,
        source_code=source_code,
        release_date=release_date,
        checksum=checksum,
    )
    external_ids = {str(row["fdc_id"]) for row in rows}
    conflicting_active_ids = {
        external_id
        for (external_id,) in db.query(Food.external_id)
        .filter(
            Food.is_active.is_(True),
            Food.source_id != source.id,
            Food.external_id.in_(external_ids),
        )
        .all()
    }
    if conflicting_active_ids:
        raise CatalogImportError(
            "لا يمكن استيراد USDA لأن معرفات FDC نشطة موجودة في مصدر آخر: "
            + ", ".join(sorted(conflicting_active_ids)[:5])
        )

    existing_foods = {
        food.external_id: food
        for food in db.query(Food).filter(Food.source_id == source.id).all()
    }

    created_foods = 0
    nutrient_upserts = 0
    for row in rows:
        external_id = str(row["fdc_id"])
        food = existing_foods.get(external_id)
        if food is None:
            food = Food(source_id=source.id, external_id=external_id, display_name="")
            db.add(food)
            db.flush()
            existing_foods[external_id] = food
            created_foods += 1

        food.display_name = str(row["name"])
        food.food_kind = "food"
        food.category = row["category"]
        food.food_group = row["category"]
        food.meal_tags = []
        food.basis_grams = 100.0
        food.data_quality = "verified"
        # USDA nutrient profiles do not themselves establish health claims.
        food.health_score = 0.0
        food.diabetic_friendly = False
        food.low_sodium = False
        food.is_high_protein = False
        food.is_active = True

        existing_nutrients = {
            nutrient.nutrient_code: nutrient for nutrient in food.nutrients
        }
        for code, (_ids, nutrient_code, unit) in _USDA_NUTRIENTS.items():
            amount = row["nutrients"].get(code)
            if amount is None:
                continue
            nutrient = existing_nutrients.get(nutrient_code)
            if nutrient is None:
                nutrient = FoodNutrient(
                    food_id=food.id,
                    nutrient_code=nutrient_code,
                    amount=float(amount),
                    unit=unit,
                    basis_grams=100.0,
                    data_quality="verified",
                )
                db.add(nutrient)
            else:
                nutrient.amount = float(amount)
                nutrient.unit = unit
                nutrient.basis_grams = 100.0
                nutrient.data_quality = "verified"
            nutrient_upserts += 1

        if not any(portion.label == "100 g" for portion in food.portions):
            db.add(FoodPortion(food_id=food.id, label="100 g", grams=100.0, is_default=True))

    db.flush()
    return {
        "source_code": source.code,
        "release_date": release_date,
        "checksum": checksum,
        "imported_foods": len(rows),
        "created_foods": created_foods,
        "nutrient_upserts": nutrient_upserts,
        "skipped_missing_required_nutrients": skipped_missing_required,
        "skipped_invalid_selected_nutrients": skipped_invalid_selected_nutrients,
        "reference_allergens_created": reference_allergens_created,
        "readiness": catalog_readiness(db),
    }
