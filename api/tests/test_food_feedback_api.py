"""API integration tests for explicit food-feedback endpoints."""

from __future__ import annotations

from collections.abc import Generator

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from api.database import Base, get_db
from api.db_models import CatalogSource, Food, User
from api.dependencies import get_current_user
from api.routes.users import router as users_router


@pytest.fixture()
def client_and_food(tmp_path) -> Generator[tuple[TestClient, int], None, None]:
    engine = create_engine(
        f"sqlite:///{tmp_path / 'feedback-api.db'}",
        connect_args={"check_same_thread": False},
    )
    testing_session = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    Base.metadata.create_all(bind=engine)
    db: Session = testing_session()

    user = User(
        email="feedback-api@example.com",
        hashed_password="not-used-by-this-route-test",
        name="مستخدم التفاعل",
        age=26,
        gender="male",
        weight=70.0,
        height=174.0,
        activity_level=3,
        goal="maintain",
        allergies=[],
        dislikes=[],
        favorites=[],
    )
    source = CatalogSource(code="test-feedback-source", name="Test", version="1")
    db.add_all([user, source])
    db.commit()
    db.refresh(user)
    db.refresh(source)
    food = Food(
        source_id=source.id,
        external_id="TEST-FEEDBACK-FOOD",
        display_name="طعام اختبار",
        meal_tags=["lunch"],
        basis_grams=100.0,
        data_quality="verified",
        is_active=True,
    )
    db.add(food)
    db.commit()
    db.refresh(food)

    app = FastAPI()
    app.include_router(users_router)

    def override_db():
        yield db

    def override_current_user():
        return db.get(User, user.id)

    app.dependency_overrides[get_db] = override_db
    app.dependency_overrides[get_current_user] = override_current_user

    with TestClient(app) as client:
        yield client, food.id

    db.close()
    engine.dispose()


def test_feedback_is_explicit_upsert_and_reports_cold_start(client_and_food) -> None:
    client, food_id = client_and_food

    created = client.post(
        "/users/food-feedback", json={"food_id": food_id, "event_type": "like"}
    )
    assert created.status_code == 201
    assert created.json()["score"] == 1.0

    updated = client.post(
        "/users/food-feedback",
        json={"food_id": food_id, "event_type": "not_interested"},
    )
    assert updated.status_code == 201
    assert updated.json()["id"] == created.json()["id"]
    assert updated.json()["score"] == -1.0

    readiness = client.get("/users/food-feedback/readiness")
    assert readiness.status_code == 200
    assert readiness.json()["ready"] is False
    assert readiness.json()["reason"] == "not_enough_explicit_feedback"


def test_feedback_rejects_unknown_catalog_food(client_and_food) -> None:
    client, _ = client_and_food

    response = client.post(
        "/users/food-feedback", json={"food_id": 999999, "event_type": "like"}
    )

    assert response.status_code == 404


def test_feedback_accepts_the_catalog_external_id_from_recommendations(
    client_and_food,
) -> None:
    client, _ = client_and_food

    response = client.post(
        "/users/food-feedback",
        json={"fdc_id": "TEST-FEEDBACK-FOOD", "event_type": "save"},
    )

    assert response.status_code == 201
    assert response.json()["event_type"] == "save"
    assert response.json()["score"] == 0.5


def test_feedback_rejects_ambiguous_food_identifiers(client_and_food) -> None:
    client, food_id = client_and_food

    response = client.post(
        "/users/food-feedback",
        json={
            "food_id": food_id,
            "fdc_id": "TEST-FEEDBACK-FOOD",
            "event_type": "like",
        },
    )

    assert response.status_code == 422
