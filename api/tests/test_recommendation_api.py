"""API integration tests for recommendation response contracts."""

from __future__ import annotations

from collections.abc import Generator

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from api.database import Base, get_db
from api.db_models import MealLog, User
from api.dependencies import get_current_user
from api.routes import recommendations as recommendation_routes


@pytest.fixture()
def client_and_db(tmp_path) -> Generator[tuple[TestClient, Session], None, None]:
    engine = create_engine(
        f"sqlite:///{tmp_path / 'recommendation-api.db'}",
        connect_args={"check_same_thread": False},
    )
    testing_session = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    Base.metadata.create_all(bind=engine)
    db = testing_session()
    user = User(
        email="recommendation-api@example.com",
        hashed_password="not-used-by-this-route-test",
        name="مستخدم التوصية",
        age=30,
        gender="female",
        weight=65.0,
        height=165.0,
        activity_level=2,
        goal="maintain",
        allergies=[],
        dislikes=[],
        favorites=[],
    )
    db.add(user)
    db.add(
        MealLog(
            user=user,
            meal_type="lunch",
            food_name="سجل سابق",
            calories=200,
            protein=10,
            carbs=20,
            fat=5,
        )
    )
    db.commit()
    db.refresh(user)

    app = FastAPI()
    app.include_router(recommendation_routes.router)

    def override_db():
        yield db

    def override_current_user():
        return db.get(User, user.id)

    app.dependency_overrides[get_db] = override_db
    app.dependency_overrides[get_current_user] = override_current_user

    with TestClient(app) as client:
        yield client, db

    db.close()
    engine.dispose()


def test_meal_recommendation_exposes_active_ranking_policy(
    client_and_db, monkeypatch
) -> None:
    client, _ = client_and_db
    captured = {}

    def fake_recommend(user_data, meal, top_k, meal_target_calories=None):
        captured["user_data"] = user_data
        captured["meal_target_calories"] = meal_target_calories
        assert meal == "lunch"
        assert top_k == 3
        return [
            {
                "fdc_id": "TEST-FOOD-1",
                "name": "وجبة اختبار",
                "category": "دواجن",
                "food_group": "بروتين",
                "slot": "بروتين",
                "calories": 250.0,
                "protein": 30.0,
                "carbs": 5.0,
                "fat": 8.0,
                "portion_g": 150.0,
                "hybrid_score": 0.91,
                "food_cluster": 2,
                "recommendation_reason": "يتوافق مع هدف المحافظة.",
                "recommendation_reasons": ["يتوافق مع هدف المحافظة."],
                "diversity_applied": True,
            }
        ]

    monkeypatch.setattr(recommendation_routes.engine, "recommend_meal", fake_recommend)
    monkeypatch.setattr(
        recommendation_routes.engine,
        "get_user_targets",
        lambda _: {
            "daily_calories": 2000.0,
            "meal_targets": {"lunch": {"calories": 600.0}},
        },
    )
    monkeypatch.setattr(
        recommendation_routes.engine,
        "get_ranking_metadata",
        lambda _: {
            "ranking_basis": "content_based",
            "content_weight": 1.0,
            "collaborative_weight": 0.0,
        },
    )

    response = client.post("/recommendations/meal", json={"meal": "lunch", "top_k": 3})

    assert response.status_code == 200
    # A meal log is consumption history, not explicit preference evidence.
    assert captured["user_data"]["interaction_count"] == 0
    assert captured["user_data"]["collaborative_signals_ready"] is False
    assert response.json()["ranking_basis"] == "content_based"
    assert response.json()["collaborative_weight"] == 0.0
    assert captured["meal_target_calories"] == 600.0
    assert response.json()["planned_target_calories"] == 600.0
    assert response.json()["consumed_today_calories"] == 200.0
    assert response.json()["remaining_daily_calories"] == 1800.0
    assert response.json()["budget_adjusted"] is False
    recommendation = response.json()["recommendations"][0]
    assert recommendation["fdc_id"] == "TEST-FOOD-1"
    assert recommendation["food_cluster"] == 2
    assert recommendation["recommendation_reason"] == "يتوافق مع هدف المحافظة."
    assert recommendation["diversity_applied"] is True


def _recommendation_item() -> list[dict]:
    return [
        {
            "fdc_id": "BUDGET-FOOD",
            "name": "وجبة الميزانية",
            "category": "اختبار",
            "food_group": "بروتين",
            "slot": "بروتين",
            "calories": 300.0,
            "protein": 25.0,
            "carbs": 10.0,
            "fat": 8.0,
            "portion_g": 150.0,
            "hybrid_score": 0.8,
            "food_cluster": 1,
            "recommendation_reason": "توصية اختبار الميزانية.",
            "recommendation_reasons": ["توصية اختبار الميزانية."],
            "diversity_applied": False,
        }
    ]


def _budget_targets() -> dict:
    return {
        "daily_calories": 2000.0,
        "meal_targets": {"dinner": {"calories": 600.0}},
    }


def test_recommendation_caps_meal_target_at_remaining_daily_calories(
    client_and_db, monkeypatch
) -> None:
    client, db = client_and_db
    user = db.query(User).one()
    db.add(
        MealLog(
            user_id=user.id,
            meal_type="breakfast",
            food_name="استهلاك اليوم",
            calories=1500.0,
            protein=0,
            carbs=0,
            fat=0,
        )
    )
    db.commit()
    captured = {}

    def fake_recommend(user_data, meal, top_k, meal_target_calories=None):
        captured["target"] = meal_target_calories
        captured["user_data"] = user_data
        return _recommendation_item()

    monkeypatch.setattr(recommendation_routes.engine, "recommend_meal", fake_recommend)
    monkeypatch.setattr(recommendation_routes.engine, "get_user_targets", lambda _: _budget_targets())
    monkeypatch.setattr(
        recommendation_routes.engine,
        "get_ranking_metadata",
        lambda _: {"ranking_basis": "content_based", "content_weight": 1.0, "collaborative_weight": 0.0},
    )

    response = client.post("/recommendations/meal", json={"meal": "dinner"})

    assert response.status_code == 200
    # Existing fixture log (200) + this log (1500) leaves 300 calories today.
    assert captured["target"] == 300.0
    assert captured["user_data"]["collaborative_signals_ready"] is False
    payload = response.json()
    assert payload["target_calories"] == 300.0
    assert payload["planned_target_calories"] == 600.0
    assert payload["consumed_today_calories"] == 1700.0
    assert payload["remaining_daily_calories"] == 300.0
    assert payload["budget_adjusted"] is True
    assert payload["daily_budget_exhausted"] is False


def test_recommendation_does_not_create_extra_meal_when_daily_budget_is_exhausted(
    client_and_db, monkeypatch
) -> None:
    client, db = client_and_db
    user = db.query(User).one()
    db.add(
        MealLog(
            user_id=user.id,
            meal_type="breakfast",
            food_name="تجاوز هدف اليوم",
            calories=1900.0,
            protein=0,
            carbs=0,
            fat=0,
        )
    )
    db.commit()

    monkeypatch.setattr(
        recommendation_routes.engine,
        "recommend_meal",
        lambda *args, **kwargs: pytest.fail("engine must not run after daily budget is exhausted"),
    )
    monkeypatch.setattr(recommendation_routes.engine, "get_user_targets", lambda _: _budget_targets())
    monkeypatch.setattr(
        recommendation_routes.engine,
        "get_ranking_metadata",
        lambda _: {"ranking_basis": "content_based", "content_weight": 1.0, "collaborative_weight": 0.0},
    )

    response = client.post("/recommendations/meal", json={"meal": "dinner"})

    assert response.status_code == 200
    payload = response.json()
    assert payload["recommendations"] == []
    assert payload["target_calories"] == 0.0
    assert payload["remaining_daily_calories"] == 0.0
    assert payload["budget_adjusted"] is True
    assert payload["daily_budget_exhausted"] is True
