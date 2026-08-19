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

    def fake_recommend(user_data, meal, top_k):
        captured["user_data"] = user_data
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
            }
        ]

    monkeypatch.setattr(recommendation_routes.engine, "recommend_meal", fake_recommend)
    monkeypatch.setattr(
        recommendation_routes.engine,
        "get_user_targets",
        lambda _: {"meal_targets": {"lunch": {"calories": 600.0}}},
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
    assert captured["user_data"]["interaction_count"] == 1
    assert captured["user_data"]["collaborative_signals_ready"] is False
    assert response.json()["ranking_basis"] == "content_based"
    assert response.json()["content_weight"] == 1.0
    assert response.json()["recommendations"][0]["fdc_id"] == "TEST-FOOD-1"
