from __future__ import annotations

from copy import deepcopy
from datetime import datetime
from collections.abc import Generator

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from api.database import Base, get_db
from api.db_models import (
    Allergen,
    CatalogSource,
    Food,
    FoodAllergen,
    FoodIngredient,
    Ingredient,
    IngredientAllergen,
    User,
    WeeklyPlan,
)
from api.dependencies import get_current_user
from api.routes import recommendations as recommendation_routes


TARGETS = {
    "daily_calories": 2000.0,
    "meal_targets": {
        "breakfast": {"calories": 500.0},
        "lunch": {"calories": 700.0},
        "dinner": {"calories": 600.0},
        "snack": {"calories": 200.0},
    },
}


def _candidate(fdc_id: str) -> dict:
    return {
        "fdc_id": fdc_id,
        "name": f"طعام {fdc_id}",
        "category": "بروتين",
        "food_group": "بروتين",
        "slot": "بروتين",
        "portion_g": 100.0,
        "calories": 200.0,
        "protein": 25.0,
        "carbs": 2.0,
        "fat": 8.0,
        "hybrid_score": 0.9,
        "food_cluster": 0,
        "recommendation_reasons": ["مرشح اختبار مؤهل"],
        "recommendation_reason": "مرشح اختبار مؤهل",
        "diversity_applied": False,
    }


@pytest.fixture()
def allergy_client(tmp_path) -> Generator[tuple[TestClient, Session, User, WeeklyPlan], None, None]:
    db_engine = create_engine(
        f"sqlite:///{tmp_path / 'recommendation-allergy.db'}",
        connect_args={"check_same_thread": False},
    )
    Base.metadata.create_all(bind=db_engine)
    session = sessionmaker(autocommit=False, autoflush=False, bind=db_engine)()

    source = CatalogSource(code="fixture", name="Fixture", version="1")
    allergen = Allergen(code="allergen.milk", display_name_ar="الحليب")
    user = User(
        email="allergy-user@example.com",
        hashed_password="not-used",
        name="مستخدم الحساسية",
        age=30,
        gender="male",
        weight=75.0,
        height=175.0,
        activity_level=2,
        goal="maintain",
        allergies=["حليب"],
        dislikes=[],
        favorites=[],
    )
    session.add_all([source, allergen, user])
    session.flush()

    safe = Food(source_id=source.id, external_id="safe", display_name="آمن")
    direct_conflict = Food(source_id=source.id, external_id="blocked", display_name="محظور")
    ingredient_conflict = Food(
        source_id=source.id,
        external_id="ingredient-blocked",
        display_name="محظور بمكوّن",
    )
    unknown = Food(source_id=source.id, external_id="unknown", display_name="ناقص")
    ingredient = Ingredient(canonical_name="milk-fixture", display_name_ar="حليب")
    session.add_all([safe, direct_conflict, ingredient_conflict, unknown, ingredient])
    session.flush()
    session.add_all([
        FoodAllergen(
            food_id=safe.id,
            allergen_id=allergen.id,
            status="absent",
            source_id=source.id,
            reviewed_at=datetime.utcnow(),
        ),
        FoodAllergen(
            food_id=direct_conflict.id,
            allergen_id=allergen.id,
            status="present",
            source_id=source.id,
            reviewed_at=datetime.utcnow(),
        ),
        FoodIngredient(food_id=ingredient_conflict.id, ingredient_id=ingredient.id),
        IngredientAllergen(
            ingredient_id=ingredient.id,
            allergen_id=allergen.id,
            status="present",
            source_id=source.id,
            reviewed_at=datetime.utcnow(),
        ),
    ])
    plan = WeeklyPlan(
        user=user,
        plan_data={
            "الأحد": {
                "breakfast": [],
                "lunch": [_candidate("current")],
                "dinner": [],
                "snack": [],
            }
        },
    )
    session.add(plan)
    session.commit()
    session.refresh(user)
    session.refresh(plan)

    app = FastAPI()
    app.include_router(recommendation_routes.router)

    def override_db():
        yield session

    app.dependency_overrides[get_db] = override_db
    app.dependency_overrides[get_current_user] = lambda: session.get(User, user.id)

    with TestClient(app) as client:
        yield client, session, user, plan

    session.close()
    db_engine.dispose()


def _patch_catalog_candidates(monkeypatch) -> None:
    monkeypatch.setattr(
        recommendation_routes.engine,
        "catalog_candidate_fdc_ids",
        lambda: {"safe", "blocked", "ingredient-blocked", "unknown"},
    )
    monkeypatch.setattr(recommendation_routes.engine, "get_user_targets", lambda _: TARGETS)
    monkeypatch.setattr(
        recommendation_routes.engine,
        "get_ranking_metadata",
        lambda _: {"ranking_basis": "content", "content_weight": 1.0, "collaborative_weight": 0.0},
    )


def test_meal_api_passes_only_catalog_eligible_ids_to_ranker(allergy_client, monkeypatch) -> None:
    client, _, _, _ = allergy_client
    _patch_catalog_candidates(monkeypatch)
    captured: dict[str, set[str] | None] = {}

    def fake_recommend(user_data, meal, top_k, **kwargs):
        captured["eligible"] = kwargs["eligible_fdc_ids"]
        return [_candidate("safe")]

    monkeypatch.setattr(recommendation_routes.engine, "recommend_meal", fake_recommend)

    response = client.post("/recommendations/meal", json={"meal": "lunch", "top_k": 3})

    assert response.status_code == 200
    assert captured["eligible"] == {"safe"}
    assert [item["fdc_id"] for item in response.json()["recommendations"]] == ["safe"]


def test_alternatives_api_passes_only_catalog_eligible_ids_to_ranker(allergy_client, monkeypatch) -> None:
    client, _, _, plan = allergy_client
    _patch_catalog_candidates(monkeypatch)
    captured: dict[str, set[str] | None] = {}

    def fake_alternatives(user_data, meal, slot, current_fdc_id, **kwargs):
        captured["eligible"] = kwargs["eligible_fdc_ids"]
        return [_candidate("safe")]

    monkeypatch.setattr(recommendation_routes.engine, "get_swap_alternatives", fake_alternatives)

    response = client.post(
        "/recommendations/weekly/alternatives",
        json={"plan_id": plan.id, "day": "الأحد", "meal": "lunch", "slot": "بروتين"},
    )

    assert response.status_code == 200
    assert captured["eligible"] == {"safe"}
    assert [item["fdc_id"] for item in response.json()] == ["safe"]


def test_swap_api_rejects_catalog_conflict_before_persisting_plan(allergy_client, monkeypatch) -> None:
    client, session, _, plan = allergy_client
    _patch_catalog_candidates(monkeypatch)
    captured: dict[str, set[str] | None] = {}

    def fake_swap(plan_data, day, meal, slot, new_fdc_id, user_data, **kwargs):
        captured["eligible"] = kwargs["eligible_fdc_ids"]
        if new_fdc_id not in kwargs["eligible_fdc_ids"]:
            raise ValueError("food is not eligible for this meal: blocked")
        updated = deepcopy(plan_data)
        updated[day][meal][0] = _candidate(new_fdc_id)
        return updated

    monkeypatch.setattr(recommendation_routes.engine, "swap_meal_item", fake_swap)

    response = client.post(
        "/recommendations/weekly/swap",
        json={
            "plan_id": plan.id,
            "day": "الأحد",
            "meal": "lunch",
            "slot": "بروتين",
            "new_fdc_id": "blocked",
        },
    )

    assert response.status_code == 400
    assert captured["eligible"] == {"safe"}
    assert session.get(WeeklyPlan, plan.id).plan_data["الأحد"]["lunch"][0]["fdc_id"] == "current"
