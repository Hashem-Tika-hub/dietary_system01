from __future__ import annotations

import csv
import io
import zipfile
from collections.abc import Generator
from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from api.database import Base, get_db
from api.db_models import CatalogSource, Food, FoodAllergen, FoodNutrient, FoodPortion
from api.routes.foods import router as foods_router
from api.services.catalog_import import CatalogImportError
from api.services.usda_foundation_import import import_usda_foundation_catalog


ARCHIVE_ROOT = "FoodData_Central_foundation_food_csv_2026-04-30"


def _csv_text(fieldnames: list[str], rows: list[dict[str, str]]) -> str:
    output = io.StringIO()
    writer = csv.DictWriter(output, fieldnames=fieldnames)
    writer.writeheader()
    writer.writerows(rows)
    return output.getvalue()


@pytest.fixture()
def catalog_session(tmp_path: Path) -> Generator[Session, None, None]:
    engine = create_engine(f"sqlite:///{tmp_path / 'catalog.db'}")
    Base.metadata.create_all(bind=engine)
    session = sessionmaker(autocommit=False, autoflush=False, bind=engine)()
    yield session
    session.close()
    engine.dispose()


@pytest.fixture()
def usda_foundation_archive(tmp_path: Path) -> Path:
    archive_path = tmp_path / "FoodData_Central_foundation_food_csv_2026-04-30.zip"
    food_rows = [
        {
            "fdc_id": "900001",
            "data_type": "foundation_food",
            "description": "USDA Test Lentils",
            "food_category_id": "11",
            "publication_date": "2026-04-30",
        },
        {
            "fdc_id": "900002",
            "data_type": "foundation_food",
            "description": "USDA Test Yogurt",
            "food_category_id": "1",
            "publication_date": "2026-04-30",
        },
        {
            "fdc_id": "900003",
            "data_type": "foundation_food",
            "description": "Incomplete USDA Food",
            "food_category_id": "11",
            "publication_date": "2026-04-30",
        },
        {
            "fdc_id": "900004",
            "data_type": "sample_food",
            "description": "Not a final foundation food",
            "food_category_id": "11",
            "publication_date": "2026-04-30",
        },
    ]
    nutrient_rows = []
    for fdc_id in ("900001", "900002"):
        nutrient_rows.extend(
            [
                {"id": f"{fdc_id}a", "fdc_id": fdc_id, "nutrient_id": "2047", "amount": "999"},
                {"id": f"{fdc_id}b", "fdc_id": fdc_id, "nutrient_id": "1008", "amount": "200"},
                {"id": f"{fdc_id}c", "fdc_id": fdc_id, "nutrient_id": "1003", "amount": "18"},
                {"id": f"{fdc_id}d", "fdc_id": fdc_id, "nutrient_id": "1004", "amount": "4"},
                {"id": f"{fdc_id}e", "fdc_id": fdc_id, "nutrient_id": "1005", "amount": "30"},
                {"id": f"{fdc_id}f", "fdc_id": fdc_id, "nutrient_id": "1079", "amount": "8"},
                {"id": f"{fdc_id}g", "fdc_id": fdc_id, "nutrient_id": "2000", "amount": "2"},
                {"id": f"{fdc_id}h", "fdc_id": fdc_id, "nutrient_id": "1093", "amount": "40"},
            ]
        )
    nutrient_rows.extend(
        [
            {"id": "900003a", "fdc_id": "900003", "nutrient_id": "1008", "amount": "120"},
            {"id": "900003b", "fdc_id": "900003", "nutrient_id": "1003", "amount": "4"},
            {"id": "900003c", "fdc_id": "900003", "nutrient_id": "1005", "amount": "20"},
        ]
    )
    with zipfile.ZipFile(archive_path, "w") as archive:
        archive.writestr(
            f"{ARCHIVE_ROOT}/food.csv",
            _csv_text(
                ["fdc_id", "data_type", "description", "food_category_id", "publication_date"],
                food_rows,
            ),
        )
        archive.writestr(
            f"{ARCHIVE_ROOT}/food_category.csv",
            _csv_text(
                ["id", "description"],
                [
                    {"id": "1", "description": "Dairy and Egg Products"},
                    {"id": "11", "description": "Vegetables and Vegetable Products"},
                ],
            ),
        )
        archive.writestr(
            f"{ARCHIVE_ROOT}/food_nutrient.csv",
            _csv_text(
                ["id", "fdc_id", "nutrient_id", "amount"], nutrient_rows
            ),
        )
    return archive_path


def test_usda_foundation_import_is_idempotent_and_keeps_allergies_unknown(
    catalog_session: Session, usda_foundation_archive: Path
) -> None:
    first = import_usda_foundation_catalog(catalog_session, usda_foundation_archive)
    catalog_session.commit()
    second = import_usda_foundation_catalog(catalog_session, usda_foundation_archive)
    catalog_session.commit()

    assert first["source_code"] == "usda-fdc-foundation"
    assert first["release_date"] == "2026-04-30"
    assert first["imported_foods"] == 2
    assert first["created_foods"] == 2
    assert first["skipped_missing_required_nutrients"] == 1
    assert first["skipped_invalid_selected_nutrients"] == 0
    assert second["created_foods"] == 0
    assert catalog_session.query(CatalogSource).count() == 1
    assert catalog_session.query(Food).count() == 2
    assert catalog_session.query(FoodAllergen).count() == 0
    assert catalog_session.query(FoodPortion).count() == 2

    lentils = catalog_session.query(Food).filter(Food.external_id == "900001").one()
    nutrients = {record.nutrient_code: record.amount for record in lentils.nutrients}
    assert lentils.data_quality == "verified"
    assert lentils.category == "Vegetables and Vegetable Products"
    assert nutrients["energy_kcal"] == 200.0
    assert nutrients["protein_g"] == 18.0
    assert nutrients["fiber_g"] == 8.0
    assert nutrients["sodium_mg"] == 40.0


def test_usda_foundation_foods_are_available_through_foods_api(
    catalog_session: Session, usda_foundation_archive: Path
) -> None:
    import_usda_foundation_catalog(catalog_session, usda_foundation_archive)
    catalog_session.commit()
    app = FastAPI()
    app.include_router(foods_router)

    def override_db():
        yield catalog_session

    app.dependency_overrides[get_db] = override_db
    with TestClient(app) as client:
        response = client.get("/foods/900001")

    assert response.status_code == 200
    assert response.json()["name"] == "USDA Test Lentils"
    assert response.json()["source"] == "USDA FoodData Central Foundation Foods"


def test_usda_foundation_import_rejects_active_fdc_id_from_other_source(
    catalog_session: Session, usda_foundation_archive: Path
) -> None:
    legacy_source = CatalogSource(
        code="legacy-source",
        name="Legacy catalog",
        version="1",
    )
    catalog_session.add(legacy_source)
    catalog_session.flush()
    catalog_session.add(
        Food(
            source_id=legacy_source.id,
            external_id="900001",
            display_name="Existing food with same FDC ID",
        )
    )
    catalog_session.commit()

    with pytest.raises(CatalogImportError, match="معرفات FDC نشطة"):
        import_usda_foundation_catalog(catalog_session, usda_foundation_archive)


def test_usda_foundation_import_rejects_invalid_limit(
    catalog_session: Session, usda_foundation_archive: Path
) -> None:
    with pytest.raises(CatalogImportError, match="حد استيراد USDA"):
        import_usda_foundation_catalog(
            catalog_session, usda_foundation_archive, limit=0
        )
