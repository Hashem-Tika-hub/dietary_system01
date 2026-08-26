from __future__ import annotations

from pathlib import Path
from collections.abc import Generator

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from api.database import Base, get_db
from api.db_models import Allergen, Food, FoodAllergen, FoodNutrient
from api.routes.foods import router as foods_router
from api.services.catalog_import import import_food_catalog
from api.services.catalog_readiness import catalog_readiness


CSV_HEADER = (
    "fdc_id,name,category,food_group,meal_type,source,calories,protein,carbs,fat,"
    "fiber,sugar,sodium,calcium,iron,health_score,is_high_protein,diabetic_friendly,low_sodium\n"
)
CSV_ROWS = (
    "SAFE1,دجاج مشوي,دواجن,بروتين,غداء، عشاء,قياسي,180,32,0,6,0,0,80,10,1,91,True,True,True\n"
    "SAFE2,أرز بني,نشويات,نشويات,غداء، عشاء,قياسي,220,5,46,2,4,1,10,20,1,75,False,True,True\n"
)


@pytest.fixture()
def catalog_csv(tmp_path: Path) -> Path:
    path = tmp_path / "foods.csv"
    path.write_text(CSV_HEADER + CSV_ROWS, encoding="utf-8-sig")
    return path


@pytest.fixture()
def catalog_session(tmp_path: Path) -> Generator[Session, None, None]:
    engine = create_engine(
        f"sqlite:///{tmp_path / 'catalog.db'}",
        connect_args={"check_same_thread": False},
    )
    Base.metadata.create_all(bind=engine)
    session = sessionmaker(autocommit=False, autoflush=False, bind=engine)()
    yield session
    session.close()
    engine.dispose()


def test_catalog_import_is_idempotent_and_preserves_unknown_allergen_evidence(
    catalog_session: Session, catalog_csv: Path
) -> None:
    first = import_food_catalog(catalog_session, catalog_csv)
    catalog_session.commit()
    second = import_food_catalog(catalog_session, catalog_csv)
    catalog_session.commit()

    assert first["imported_foods"] == 2
    assert first["created_foods"] == 2
    assert second["imported_foods"] == 2
    assert second["created_foods"] == 0
    assert catalog_session.query(Food).count() == 2
    assert catalog_session.query(FoodNutrient).count() == 18
    assert catalog_session.query(FoodAllergen).count() == 0
    assert catalog_session.query(Allergen).count() == 7
    readiness = catalog_readiness(catalog_session)
    assert readiness["catalog_loaded"] is True
    assert readiness["allergy_evidence_complete"] is False
    assert readiness["foods_missing_allergen_evidence"] == 2

    chicken = catalog_session.query(Food).filter(Food.external_id == "SAFE1").one()
    assert chicken.health_score == 91.0
    assert chicken.diabetic_friendly is True
    assert {nutrient.nutrient_code for nutrient in chicken.nutrients} >= {
        "energy_kcal",
        "protein_g",
        "carbs_g",
        "fat_g",
    }


def test_catalog_readiness_requires_reviewed_reference_evidence(
    catalog_session: Session, catalog_csv: Path
) -> None:
    import_food_catalog(catalog_session, catalog_csv)
    catalog_session.commit()

    foods = catalog_session.query(Food).order_by(Food.external_id).all()
    allergens = catalog_session.query(Allergen).order_by(Allergen.code).all()
    catalog_session.add(
        FoodAllergen(
            food_id=foods[0].id,
            allergen_id=allergens[0].id,
            status="unknown",
            is_derived=True,
        )
    )
    catalog_session.commit()

    incomplete = catalog_readiness(catalog_session)
    assert incomplete["foods_with_any_allergen_evidence"] == 1
    assert incomplete["foods_with_unknown_allergen_evidence"] == 1
    assert incomplete["foods_with_complete_reference_allergen_evidence"] == 0
    assert incomplete["allergy_evidence_complete"] is False

    for food in foods:
        for allergen in allergens:
            evidence = (
                catalog_session.query(FoodAllergen)
                .filter(
                    FoodAllergen.food_id == food.id,
                    FoodAllergen.allergen_id == allergen.id,
                )
                .one_or_none()
            )
            if evidence is None:
                evidence = FoodAllergen(
                    food_id=food.id,
                    allergen_id=allergen.id,
                    status="absent",
                    is_derived=False,
                )
                catalog_session.add(evidence)
            else:
                evidence.status = "absent"
                evidence.is_derived = False
    catalog_session.add(
        Allergen(code="allergen.custom", display_name_ar="اختبار", display_name_en="Test")
    )
    catalog_session.commit()

    ready = catalog_readiness(catalog_session)
    assert ready["reference_allergens"] == 7
    assert ready["foods_with_unknown_allergen_evidence"] == 0
    assert ready["foods_with_complete_reference_allergen_evidence"] == 2
    assert ready["allergy_evidence_complete"] is True
    assert ready["status"] == "ready"


def test_foods_api_queries_catalog_database_not_csv(
    catalog_session: Session, catalog_csv: Path
) -> None:
    import_food_catalog(catalog_session, catalog_csv)
    catalog_session.commit()

    app = FastAPI()
    app.include_router(foods_router)

    def override_db():
        yield catalog_session

    app.dependency_overrides[get_db] = override_db
    with TestClient(app) as client:
        filtered = client.get("/foods", params={"min_protein": 20, "low_sodium": True})
        assert filtered.status_code == 200
        payload = filtered.json()
        assert payload["total"] == 1
        assert payload["foods"][0]["fdc_id"] == "SAFE1"
        assert payload["foods"][0]["calories"] == 180.0

        item = client.get("/foods/SAFE2")
        assert item.status_code == 200
        assert item.json()["protein"] == 5.0

        readiness = client.get("/foods/readiness")
        assert readiness.status_code == 200
        assert readiness.json()["status"] == "catalog_ready_allergy_evidence_incomplete"


def test_foods_api_reports_unseeded_catalog_cleanly(catalog_session: Session) -> None:
    app = FastAPI()
    app.include_router(foods_router)

    def override_db():
        yield catalog_session

    app.dependency_overrides[get_db] = override_db
    with TestClient(app) as client:
        response = client.get("/foods")

    assert response.status_code == 503
    assert "كتالوج الطعام غير مستورد" in response.json()["detail"]
